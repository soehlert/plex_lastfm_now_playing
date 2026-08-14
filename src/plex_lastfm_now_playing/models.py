"""Define the models needed."""

from pydantic import BaseModel


class PlexMetadata(BaseModel):
    """Represent metadata for the media item."""

    originalTitle: str | None = None  # Track Artist
    grandparentTitle: str | None = None  # Album Artist
    parentTitle: str | None = None  # Album Name
    title: str | None = None  # Track title
    parentIndex: int | None = None  # Disc number
    index: int | None = None  # Track number
    type: str | None = None  # e.g., 'track'
    duration: int | None = None  # Duration in ms
    librarySectionType: str | None = None  # "artist", "show", "movie"


class PlexAccount(BaseModel):
    """Represent the Plex account triggering the webhook."""

    title: str | None = None  # Username


class PlexPlayer(BaseModel):
    """Represent the Plex player."""

    uuid: str | None = None
    name: str | None = None


class PlexWebhookPayload(BaseModel):
    """Represent the overall structure of the parsed Plex webhook JSON."""

    event: str
    Metadata: PlexMetadata | None = None
    Account: PlexAccount | None = None
    Player: PlexPlayer | None = None
    user: bool | None = False
    owner: bool | None = False


class AuthResponse(BaseModel):
    """Represent the authorization response."""

    auth_url: str
    message: str
