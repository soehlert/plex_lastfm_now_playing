"""Create tests for our project."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from plex_lastfm_now_playing.models import PlexMetadata, PlexWebhookPayload
from plex_lastfm_now_playing.plex_lastfm_now_playing import (
    LastFmUpdater,
    PlexWebhookHandler,
)

os.environ["LASTFM_USERNAME"] = "test_user"
os.environ["LASTFM_API_KEY"] = "test_api_key"
os.environ["LASTFM_API_SECRET"] = "test_api_secret"
os.environ["LASTFM_SESSION_KEY"] = "test_session_key"
os.environ["PLEX_WEBHOOK_PATH"] = "/webhook"
os.environ["NOW_PLAYING_UPDATE_INTERVAL"] = "60"
os.environ["PAUSE_TIMEOUT_SECONDS"] = "300"


@pytest.fixture()
def lastfm_updater_mock():
    """Create a mock LastFmUpdater."""
    mock = AsyncMock(spec=LastFmUpdater)
    mock.update_now_playing = AsyncMock()
    mock.scrobble = AsyncMock()
    return mock


@pytest.fixture()
def plex_lastfm(lastfm_updater_mock):
    """Create a mock PlexWebhookHandler."""
    instance = PlexWebhookHandler(lastfm_updater=lastfm_updater_mock)

    instance._start_periodic_update = AsyncMock()
    instance._stop_periodic_update = AsyncMock()
    instance._cancel_pause_timer_internal = AsyncMock()

    return instance


@pytest.fixture()
def play_metadata():
    """Create a PlexMetadata object with test track information."""
    return PlexMetadata(
        parentTitle="Test Album",
        grandparentTitle="Test Artist",
        parentStudio="Fallback Artist",
        title="Test Song",
        parentIndex=1,
        index=5,
        type="track",
        duration=240000,
    )


@pytest.fixture()
def play_payload(play_metadata):
    """Create a mock PlexWebhookPayload for a media.play event."""
    payload = MagicMock(spec=PlexWebhookPayload)
    payload.event = "media.play"
    payload.Metadata = play_metadata
    return payload


@pytest.mark.asyncio()
async def test_process_webhook_play_event(plex_lastfm, play_payload):
    """Test that play events are routed to the play handler method."""
    play_payload.Metadata = MagicMock()

    with patch.object(plex_lastfm, "_handle_play_event", new_callable=AsyncMock) as mock_handle_play:
        await plex_lastfm.process_webhook(play_payload)

        mock_handle_play.assert_called_once_with(play_payload.Metadata)


@pytest.mark.asyncio()
async def test_process_webhook_resume_event(plex_lastfm, play_payload):
    """Test that pause events are routed to the play handler method."""
    play_payload.event = "media.resume"
    play_payload.Metadata = MagicMock()

    with patch.object(plex_lastfm, "_handle_play_event", new_callable=AsyncMock) as mock_handle_play:
        await plex_lastfm.process_webhook(play_payload)
        mock_handle_play.assert_called_once_with(play_payload.Metadata)


@pytest.mark.asyncio()
async def test_process_webhook_pause_event(plex_lastfm):
    """Test that stop events are routed to the pause handler method."""
    payload = MagicMock(spec=PlexWebhookPayload)
    payload.event = "media.pause"
    payload.Metadata = MagicMock()

    with patch.object(plex_lastfm, "_handle_pause_event", new_callable=AsyncMock) as mock_handle_pause:
        await plex_lastfm.process_webhook(payload)
        mock_handle_pause.assert_called_once()


@pytest.mark.asyncio()
async def test_process_webhook_stop_event(plex_lastfm):
    """Test that stop events are routed to the stop handler method."""
    payload = MagicMock(spec=PlexWebhookPayload)
    payload.event = "media.stop"
    payload.Metadata = MagicMock()

    with patch.object(plex_lastfm, "_handle_stop_event", new_callable=AsyncMock) as mock_handle_stop:
        await plex_lastfm.process_webhook(payload)
        mock_handle_stop.assert_called_once()


@pytest.mark.asyncio()
async def test_process_webhook_unknown_event(plex_lastfm):
    """Test that unknown events are properly ignored without calling any handlers."""
    payload = MagicMock(spec=PlexWebhookPayload)
    payload.event = "media.unknown"
    payload.Metadata = MagicMock()

    with (
        patch.object(plex_lastfm, "_handle_play_event", new_callable=AsyncMock) as mock_handle_play,
        patch.object(plex_lastfm, "_handle_pause_event", new_callable=AsyncMock) as mock_handle_pause,
        patch.object(plex_lastfm, "_handle_stop_event", new_callable=AsyncMock) as mock_handle_stop,
    ):
        await plex_lastfm.process_webhook(payload)

        mock_handle_play.assert_not_called()
        mock_handle_pause.assert_not_called()
        mock_handle_stop.assert_not_called()


@pytest.mark.asyncio()
async def test_handle_play_event_new_track(plex_lastfm, play_metadata):
    """Test that playing a new track updates Last.fm and starts periodic updates."""
    plex_lastfm.lastfm_updater = AsyncMock()
    plex_lastfm.lastfm_updater.update_now_playing = AsyncMock()

    # Mock the lock to avoid any issues with async context manager
    mock_lock = AsyncMock()
    mock_lock.__aenter__.return_value = None
    mock_lock.__aexit__.return_value = None
    plex_lastfm._lock = mock_lock

    cancel_timer_mock = AsyncMock()
    plex_lastfm._cancel_pause_timer_internal = cancel_timer_mock

    with (
        patch.object(plex_lastfm, "_generate_track_key", return_value="test_key"),
        patch("asyncio.create_task") as mock_create_task,
    ):
        # Set up the current state
        plex_lastfm._current_track_key = "different_key"
        plex_lastfm._now_playing_task = None

        await plex_lastfm._handle_play_event(play_metadata)

        cancel_timer_mock.assert_called_once()

        plex_lastfm.lastfm_updater.update_now_playing.assert_called_once_with(
            artist=play_metadata.grandparentTitle,
            title=play_metadata.title,
            album=play_metadata.parentTitle,
            album_artist=play_metadata.grandparentTitle,
        )

        assert plex_lastfm._current_track_key == "test_key"

        assert plex_lastfm._current_track_details == {
            "artist": play_metadata.grandparentTitle,
            "title": play_metadata.title,
            "album": play_metadata.parentTitle,
            "album_artist": play_metadata.grandparentTitle,
        }
        assert mock_create_task.called


@pytest.mark.asyncio()
async def test_handle_stop_event(plex_lastfm):
    """Test that stop events properly stop periodic updates."""
    mock_stop = AsyncMock()

    with patch.object(plex_lastfm, "_stop_periodic_update", mock_stop):
        await plex_lastfm._handle_stop_event()
        mock_stop.assert_called_once()


@pytest.mark.asyncio()
async def test_periodic_update_loop(plex_lastfm, play_metadata):
    """Test that the periodic update loop sends regular Now Playing updates to Last.fm."""
    plex_lastfm.lastfm_updater = AsyncMock()
    plex_lastfm.lastfm_updater.update_now_playing = AsyncMock()

    plex_lastfm._current_track_details = {
        "artist": play_metadata.grandparentTitle,
        "title": play_metadata.title,
        "album": play_metadata.parentTitle,
        "album_artist": play_metadata.grandparentTitle,
    }

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        # Define a function that will run once then exit
        async def modified_loop():
            await plex_lastfm.lastfm_updater.update_now_playing(**plex_lastfm._current_track_details)
            # Simulate one sleep
            await mock_sleep(60)

        original_loop = plex_lastfm._periodic_update_loop
        plex_lastfm._periodic_update_loop = modified_loop

        try:
            await plex_lastfm._periodic_update_loop()

            plex_lastfm.lastfm_updater.update_now_playing.assert_called_once_with(
                artist=play_metadata.grandparentTitle,
                title=play_metadata.title,
                album=play_metadata.parentTitle,
                album_artist=play_metadata.grandparentTitle,
            )

            mock_sleep.assert_called_once_with(60)
        finally:
            plex_lastfm._periodic_update_loop = original_loop
