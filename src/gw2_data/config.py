"""
Configuration management for GW2 data extraction.

Loads settings from environment variables and config file, with sensible defaults.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GW2_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_timeout: float = Field(default=30.0, description="HTTP request timeout in seconds")
    cache_dir: Path = Field(
        default_factory=lambda: Path(".cache/gw2"),
        description="Cache storage directory",
    )
    log_level: str = Field(default="INFO", description="Logging level")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    global _settings
    _settings = Settings()
    return _settings
