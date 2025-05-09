"""Set up configuration variables."""

import logging
import pathlib
from pathlib import Path

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class Settings(BaseSettings):
    """Define the settings we need."""

    # Default values
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    UPDATE_INTERVAL_SECONDS: int = 60
    PAUSE_TIMEOUT_SECONDS: int = 300
    LASTFM_USERNAME: str = None

    # Required values (no defaults)
    LASTFM_API_KEY: str = None
    LASTFM_API_SECRET: str = None
    LASTFM_SESSION_KEY: str | None = None

    class Config:
        """Define our settings file."""
        env_file = str(Path("lastfm-data/.env") if Path("lastfm-data/.env").exists() else Path(".env"))

settings = Settings()