"""Set up configuration variables."""

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Define the settings we need."""
    LASTFM_API_KEY: str
    LASTFM_API_SECRET: str
    LASTFM_USERNAME:str
    LASTFM_PASSWORD_HASH: str  # Generate using pylast.md5('your_password')
    UPDATE_INTERVAL_SECONDS: int = 60
    PAUSE_TIMEOUT_SECONDS: float = 10.0

    class Config:
        """Define our settings file."""
        env_file = ".env"

settings = Settings()