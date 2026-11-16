"""Configuration from environment variables (SPEC §8)."""

import pytest

from telemetry.config import Settings


def test_settings_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u@h/db")
    monkeypatch.setenv("DB_TIMEOUT_S", "0.5")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    assert Settings.from_env() == Settings(
        database_url="postgresql://u@h/db", db_timeout_s=0.5, log_level="DEBUG"
    )


def test_missing_database_url_fails_with_a_pointer_to_env_example(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match=r"\.env\.example"):
        Settings.from_env()
