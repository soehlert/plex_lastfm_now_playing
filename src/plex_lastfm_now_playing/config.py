"""Set up configuration variables."""

import logging
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Define the settings we need."""

    # Default values
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    UPDATE_INTERVAL_SECONDS: int = 30
    PAUSE_TIMEOUT_SECONDS: int = 60
    LASTFM_USERNAME: str = None

    # Required values (no defaults)
    LASTFM_API_KEY: str = None
    LASTFM_API_SECRET: str = None
    LASTFM_SESSION_KEY: str | None = None

    class Config:
        """Define our settings file."""

        env_file = str(Path("lastfm-data/.env") if Path("lastfm-data/.env").exists() else Path(".env"))


settings = Settings()

logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format="%(levelname)s:%(name)s:%(message)s",
    force=True,  # Overrides any previously configured root loggers
)

logger = logging.getLogger(__name__)
