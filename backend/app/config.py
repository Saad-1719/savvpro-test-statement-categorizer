"""All settings in one place, read from environment variables (or backend/.env).

Every setting has a safe default, so the app runs with no configuration at all.
See .env.example in the repository root for the variable names.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    frontend_origin: str = "http://localhost:3000"  # the only origin CORS allows
    max_upload_mb: float = Field(default=5, gt=0)
    session_ttl_minutes: int = Field(default=120, gt=0)  # idle sessions are dropped after this
    max_sessions: int = Field(default=100, gt=0)  # oldest idle session is dropped beyond this
    log_level: str = "INFO"

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)


settings = Settings()
