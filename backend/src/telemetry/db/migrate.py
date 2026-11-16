"""Plain-SQL migration runner (ADR-0006).

Applies `migrations/NNNN_*.sql` in order, each once, recording them in `schema_migrations`,
then sets the `telemetry_app` role password (GOV-005). Runs as the owner role in `init`.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import psycopg
from psycopg import sql

from telemetry import logs

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

log = logging.getLogger(__name__)


def migrate(database_url: str, *, app_password: str | None) -> list[str]:
    """Apply pending migrations; return the versions applied by this run."""
    applied: list[str] = []
    with psycopg.connect(database_url) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version text PRIMARY KEY,"
            " applied_at timestamptz NOT NULL DEFAULT now())"
        )
        done = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.stem in done:
                continue
            conn.execute(path.read_bytes())
            conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.stem,))
            applied.append(path.stem)
        if app_password:
            conn.execute(
                sql.SQL("ALTER ROLE telemetry_app WITH PASSWORD {}").format(
                    sql.Literal(app_password)
                )
            )
    log.info("migrations complete", extra={"applied": applied, "skipped": sorted(done)})
    return applied


def main() -> None:
    logs.configure(os.environ.get("LOG_LEVEL", "INFO"))
    migrate(os.environ["DATABASE_URL"], app_password=os.environ.get("APP_DB_PASSWORD"))
