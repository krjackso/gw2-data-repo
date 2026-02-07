"""Tests for config module."""

from pathlib import Path

from gw2_data.config import Settings, reload_settings


def test_settings_defaults():
    settings = Settings()

    assert settings.api_timeout == 30.0
    assert settings.cache_dir == Path(".cache/gw2")
    assert settings.log_level == "INFO"


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("GW2_API_TIMEOUT", "60.0")
    monkeypatch.setenv("GW2_CACHE_DIR", "/tmp/custom_cache")
    monkeypatch.setenv("GW2_LOG_LEVEL", "DEBUG")

    settings = reload_settings()

    assert settings.api_timeout == 60.0
    assert settings.cache_dir == Path("/tmp/custom_cache")
    assert settings.log_level == "DEBUG"


def test_settings_ignores_extra_env_vars(monkeypatch):
    monkeypatch.setenv("GW2_UNKNOWN_VAR", "value")

    settings = reload_settings()

    assert not hasattr(settings, "unknown_var")
