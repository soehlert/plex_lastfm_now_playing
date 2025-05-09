"""Define the models needed."""

from pydantic import BaseModel


class PlexMetadata(BaseModel):
    """Represent metadata for the media item."""
    parentTitle: str | None = None  # Album artist
    grandparentTitle: str | None = None # Artist
    parentStudio: str | None = None # Fallback artist if grandparentTitle missing
    title: str | None = None # Track title
    parentIndex: int | None = None # Disc number
    index: int | None = None # Track number
    type: str | None = None # e.g., 'track'
    duration: int | None = None # Duration in ms

class PlexAccount(BaseModel):
    """Represent the Plex account triggering the webhook."""
    title: str | None = None # Username

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

class AuthResponse(BaseModel):
    auth_url: str
    message: str
