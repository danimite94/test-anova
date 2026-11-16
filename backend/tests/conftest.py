"""Shared test configuration.

- Applies the level marker (unit/integration/contract/e2e/perf) from the test's directory.
- Validates `@pytest.mark.req(...)` IDs so traceability (GOV-016) can't silently break.
- Provides a real PostgreSQL 16 database via testcontainers (ADR-0007): no database mocks.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

LEVELS = ("unit", "integration", "contract", "e2e", "perf")
REQ_ID = re.compile(r"^(FR|NFR|GOV)-\d{3}$")

POSTGRES_IMAGE = "postgres:16-alpine"
APP_PASSWORD = "test-app-password"  # noqa: S105  justified: throwaway test container credential


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        parts = Path(str(item.path)).parts
        for level in LEVELS:
            if level in parts:
                item.add_marker(getattr(pytest.mark, level))
        for mark in item.iter_markers(name="req"):
            bad = [i for i in mark.args if not isinstance(i, str) or not REQ_ID.match(i)]
            if bad or not mark.args:
                raise pytest.UsageError(f"{item.nodeid}: invalid requirement IDs {bad or '()'}")


@dataclass(frozen=True)
class Database:
    owner_url: str
    app_url: str


@pytest.fixture(scope="session")
def database() -> Iterator[Database]:
    """A migrated PostgreSQL database, shared by the session."""
    from testcontainers.community.postgres import PostgresContainer

    from telemetry.db.migrate import migrate

    os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "false")
    with PostgresContainer(POSTGRES_IMAGE, driver=None) as pg:
        owner_url = pg.get_connection_url()
        migrate(owner_url, app_password=APP_PASSWORD)
        app_url = owner_url.replace(
            f"{pg.username}:{pg.password}@", f"telemetry_app:{APP_PASSWORD}@", 1
        )
        yield Database(owner_url=owner_url, app_url=app_url)
