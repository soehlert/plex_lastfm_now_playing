"""Scrobble now playing info from Plex to Last.fm."""

import asyncio
import logging.config
from contextlib import suppress
from pathlib import Path
from typing import Any

import pylast
from pylast import SessionKeyGenerator

from .config import settings
from .exceptions import LastFMConfigError
from .models import PlexMetadata, PlexWebhookPayload

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class LastFmUpdater:
    """Handle communication with the Last.fm API."""

    def __init__(self) -> None:
        """Initialize the Last.fm network connection."""
        self.network: pylast.LastFMNetwork | None = None
        self.setup_mode = False
        self.skg = None
        self.setup_url = None

        try:
            api_key = settings.LASTFM_API_KEY
            api_secret = settings.LASTFM_API_SECRET
            username = settings.LASTFM_USERNAME
            session_key = settings.LASTFM_SESSION_KEY

            if not all([api_key, api_secret, username]):
                self.setup_mode = True

            # Attempt to authenticate and initialize self.network otherwise fall back into set up mode
            if session_key and username:
                self.network = pylast.LastFMNetwork(
                    api_key=api_key, api_secret=api_secret, username=username, session_key=session_key
                )
                self.network.enable_caching()
                logger.info("Last.fm network initialized for user %s using session key.", username)
            else:
                logger.warning("No session key found. Entering setup mode.")
                self.setup_mode = True
                # This is enough for pylast to request an authentication token later,
                # but not enough to make authenticated calls like scrobbling.
                self.network = pylast.LastFMNetwork(api_key=api_key, api_secret=api_secret)
        except (pylast.WSError, pylast.NetworkError, ValueError):
            logger.exception("Failed to initialize Last.fm network")
            self.network = None

    def is_ready(self) -> bool:
        """Check if the Last.fm updater is ready for normal operation."""
        return self.network is not None and not self.setup_mode

    def generate_auth_url(self, network: pylast.LastFMNetwork) -> tuple[SessionKeyGenerator, str]:
        """Generate an authentication token and URL for Last.fm authorization."""
        if not self.setup_mode or not self.network:
            msg = "Not in setup mode or network not initialized"
            raise ValueError(msg)

        try:
            self.skg = pylast.SessionKeyGenerator(network)
            self.setup_url = self.skg.get_web_auth_url()
        except (pylast.WSError, pylast.NetworkError) as e:
            msg = f"Failed to generate auth token: {e}"
            raise ValueError(msg) from e
        else:
            return self.skg, self.setup_url

    async def complete_auth(self, username: str) -> str:
        """Complete the authentication process and get a session key."""
        if not self.setup_mode or not self.network:
            msg = "Not in setup mode, network not initialized, or no token generated"
            raise ValueError(msg)

        session_key = self.skg.get_web_auth_session_key(self.setup_url)

        try:
            # Now reinitialize the network with the session key and username
            self.network = pylast.LastFMNetwork(
                api_key=settings.LASTFM_API_KEY,
                api_secret=settings.LASTFM_API_SECRET,
                username=settings.LASTFM_USERNAME,
                session_key=session_key,
            )
            self.network.enable_caching()

            # Exit setup mode
            self.setup_mode = False
            self.setup_url = None

            self._update_env_file(session_key, username)

            logger.info("Last.fm authentication completed successfully for user %s", settings.LASTFM_USERNAME)
        except (pylast.WSError, pylast.NetworkError) as e:
            msg = f"Failed to complete authentication: {e}"
            raise ValueError(msg) from e
        else:
            return session_key

    @staticmethod
    def _update_env_file(session_key: str, username: str) -> None:
        """Update the .env file with the new session key and username."""
        # Get the path to the .env file (assuming it's in the project root)
        env_path = Path.cwd() / "lastfm-data" / ".env"

        try:
            env_path.parent.mkdir(parents=True, exist_ok=True)

            if env_path.exists():
                lines = env_path.read_text().splitlines(keepends=True)
            else:
                lines = []

            session_key_found = False
            username_found = False

            for i, line in enumerate(lines):
                if line.startswith("LASTFM_SESSION_KEY="):
                    lines[i] = f"LASTFM_SESSION_KEY={session_key}\n"
                    session_key_found = True
                elif line.startswith("LASTFM_USERNAME="):
                    lines[i] = f"LASTFM_USERNAME={username}\n"
                    username_found = True

            if not session_key_found:
                lines.append(f"LASTFM_SESSION_KEY={session_key}\n")

            if not username_found:
                lines.append(f"LASTFM_USERNAME={username}\n")

            env_path.write_text("".join(lines))

            logger.info("Updated .env file with Last.fm session key and username.")
        except (OSError, PermissionError) as e:
            error_msg = f"ERROR: Cannot write Last.fm session key to {env_path}. Please fix permissions: {e!s}"
            raise LastFMConfigError(error_msg) from e

    async def update_now_playing(
        self, artist: str, title: str, album: str | None = None, album_artist: str | None = None
    ) -> None:
        """Send the now playing update to Last.fm."""
        if not self.network:
            logger.warning("Last.fm network not available, skipping Now Playing update.")
            return

        logger.info("Updating Now Playing: Artist=%s, Title=%s, Album=%s", artist, title, album)
        try:
            # Run blocking network I/O in a separate thread
            await asyncio.to_thread(
                self.network.update_now_playing,
                artist=artist,
                title=title,
                album=album,
                album_artist=album_artist,
            )
            logger.debug("Successfully updated Now Playing on Last.fm.")
        except (pylast.WSError, pylast.NetworkError, pylast.MalformedResponseError):
            logger.exception("Failed to update Last.fm Now Playing")


class PlexWebhookHandler:
    """Manage state and logic for processing Plex webhooks and updating Last.fm."""

    def __init__(self, lastfm_updater: LastFmUpdater) -> None:
        """Initialize the Plex webhook handler."""
        self.lastfm_updater: LastFmUpdater = lastfm_updater
        self._lock = asyncio.Lock()
        self._current_track_key: str | None = None
        self._current_track_details: dict[str, Any] | None = None
        self._now_playing_task: asyncio.Task[None] | None = None
        self._pause_timer_handle: asyncio.TimerHandle | None = None

    @staticmethod
    def _generate_track_key(metadata: PlexMetadata) -> str | None:
        """Generate a simple key to identify a track."""
        # Use artist and title as the key. Fall back to parentStudio (often artist for compilations), then just title.
        if metadata.grandparentTitle and metadata.title:
            return f"{metadata.grandparentTitle}_{metadata.title}"
        if metadata.parentStudio and metadata.title:
            return f"{metadata.parentStudio}_{metadata.title}"
        if metadata.title:
            return f"_{metadata.title}"
        return None

    async def shutdown(self, reason: str) -> None:
        """Gracefully shutdown the handler and stop any running tasks."""
        await self._stop_periodic_update(reason=reason)

    async def _stop_periodic_update(self, reason: str) -> None:
        """Stop the periodic now playing update task and clear state."""
        task_to_cancel = None

        async with self._lock:
            if self._now_playing_task and not self._now_playing_task.done():
                task_to_cancel = self._now_playing_task
                self._cancellation_reason = reason

        if task_to_cancel:
            task_to_cancel.cancel()
            if reason == "CancelledError:":
                logger.info("Cancelled periodic update task intentionally due to a stop or next song.")
            else:
                logger.info("Cancelled periodic Now Playing task. Reason: %s", reason)

            with suppress(asyncio.CancelledError):
                await task_to_cancel

        async with self._lock:
            self._now_playing_task = None
            self._current_track_key = None
            self._current_track_details = None
            self._cancel_pause_timer_internal()
            logger.debug("Periodic update state cleared.")

    def _cancel_pause_timer_internal(self) -> None:
        """Cancel the pause timer if it's active."""
        if self._pause_timer_handle:
            self._pause_timer_handle.cancel()
            self._pause_timer_handle = None
            logger.debug("Cancelled pause timer.")

    async def _handle_pause_timeout(self) -> None:
        """Stop updates if still paused."""
        logger.info("Pause timer expired. Stopping periodic updates.")
        await self._stop_periodic_update(reason="Pause timer expired. Stopping periodic updates.")

    async def _periodic_update_loop(self) -> None:
        """Define the core loop that periodically sends now playing updates."""
        try:
            while True:
                # Lock is acquired before starting the loop in process_webhook
                # Re-check details within the loop in case state changed between intervals
                async with self._lock:
                    if not self._current_track_details:
                        logger.warning("Periodic update loop running without track details. Stopping.")
                        break
                    # Copy details to a local var while we hold the lock
                    details = self._current_track_details.copy()

                try:
                    logger.debug("Periodic update loop: Sending update for %s", details.get("title", "N/A"))
                    await self.lastfm_updater.update_now_playing(
                        artist=details["artist"],
                        title=details["title"],
                        album=details.get("album"),
                        album_artist=details.get("album_artist"),
                    )
                    await asyncio.sleep(settings.UPDATE_INTERVAL_SECONDS)
                except ConnectionError as e:
                    logger.debug("Periodic update loop connection error: %s", e)
                    await asyncio.sleep(settings.UPDATE_INTERVAL_SECONDS)
                    continue
                except (KeyError, ValueError):
                    logger.exception("Error in periodic update")
                    break
        # This is an asyncio-ism, we need to make sure the cancellederror explicitly makes it back up the stack
        # ruff: noqa: TRY302
        except asyncio.CancelledError:
            raise
        finally:
            logger.info("Periodic update loop finished for %s.", self._current_track_key)

    async def process_webhook(self, payload: PlexWebhookPayload) -> None:
        """Process the incoming webhook payload."""
        event = payload.event
        metadata = payload.Metadata
        logger.debug("Processing webhook event: %s", event)

        if event in ["media.play", "media.resume"]:
            await self._handle_play_event(metadata)
        elif event == "media.pause":
            await self._handle_pause_event()
        elif event == "media.stop":
            await self._handle_stop_event()
        else:
            logger.debug("Ignoring irrelevant event: %s", event)

    async def _handle_play_event(self, metadata: PlexMetadata | None) -> None:
        """Handle media.play and media.resume events."""
        if not metadata or not metadata.title or not (metadata.grandparentTitle or metadata.parentStudio):
            logger.warning("Received 'media.play' event with missing metadata. Skipping.")
            return

        artist = metadata.grandparentTitle or metadata.parentStudio
        title = metadata.title
        album = metadata.parentTitle
        track_key = self._generate_track_key(metadata)

        if not track_key:
            logger.warning("Could not generate track key for 'media.play'. Skipping.")
            return

        async with self._lock:
            # Cancel any pending pause timer immediately on play/resume
            self._cancel_pause_timer_internal()

            # Check if it's the same track resuming
            if self._current_track_key == track_key and self._now_playing_task and not self._now_playing_task.done():
                logger.info("Resuming periodic updates for already playing track: %s", title)
                return

            logger.info("Received 'media.play' for new track: Artist=%s, Title=%s", artist, title)

            if self._now_playing_task:
                if not self._now_playing_task.done():
                    # immediately cancel the now playing task
                    logger.info("Cancelling update loop for %s", self._current_track_key)
                    self._now_playing_task.cancel()
                self._now_playing_task = None

            self._current_track_key = track_key
            self._current_track_details = {
                "artist": artist,
                "title": title,
                "album": album,
                "album_artist": artist,
            }

            # Send an initial update to lastfm right now
            await self.lastfm_updater.update_now_playing(artist=artist, title=title, album=album, album_artist=artist)

            # Sleep so we don't double scrobble right away
            await asyncio.sleep(settings.UPDATE_INTERVAL_SECONDS)

            # Set up the periodic updates
            logger.debug("Starting periodic Now Playing task for: %s", title)
            self._now_playing_task = asyncio.create_task(self._periodic_update_loop())

    async def _handle_pause_event(self) -> None:
        """Handle media.pause event."""
        async with self._lock:
            if self._now_playing_task and not self._now_playing_task.done() and not self._pause_timer_handle:
                logger.debug("Received 'media.pause'. Starting %s sec timeout.", settings.PAUSE_TIMEOUT_SECONDS)
                loop = asyncio.get_running_loop()
                self._pause_timer_handle = loop.call_later(
                    settings.PAUSE_TIMEOUT_SECONDS, lambda: asyncio.create_task(self._handle_pause_timeout())
                )
            elif self._pause_timer_handle:
                logger.debug("Received 'media.pause' but pause timer already active.")
            else:
                logger.debug("Received 'media.pause' but no active Now Playing task.")

    async def _handle_stop_event(self) -> None:
        """Handle media.stop event."""
        logger.info("Received 'media.stop'. Stopping periodic updates.")
        await self._stop_periodic_update(reason="media.stop event")
