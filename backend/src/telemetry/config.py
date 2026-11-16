"""Configuration from environment variables (SPEC §8)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    db_timeout_s: float = 2.0
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> Settings:
        try:
            database_url = os.environ["DATABASE_URL"]
        except KeyError:
            raise RuntimeError("DATABASE_URL is not set (see .env.example)") from None
        return cls(
            database_url=database_url,
            db_timeout_s=float(os.environ.get("DB_TIMEOUT_S", "2.0")),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
        )
