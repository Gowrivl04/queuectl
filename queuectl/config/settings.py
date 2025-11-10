"""Settings configuration."""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings loaded from environment variables."""

    libsql_dsn: str = "libsql://local.db"
    max_retries: int = 3
    dashboard_host: str = "0.0.0.0"
    dashboard_port: int = 8080  # Changed from 8000 to 8080
    max_jobs_per_query: int = 100

    model_config = SettingsConfigDict(
        env_prefix="queuectl_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

settings = Settings()
