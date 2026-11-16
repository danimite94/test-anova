"""Schema migrations and database roles (SPEC §5.1, §8; GOV-005)."""

import psycopg
import pytest

from telemetry.db.migrate import migrate
from tests.conftest import APP_PASSWORD, Database

EXPECTED_TABLES = {"asset", "sensor", "dataset", "reading", "schema_migrations"}
EXPECTED_SENSORS = {"TT-101", "TT-102", "PT-101", "VT-101", "FT-101"}


def test_migrations_create_schema_and_seed_catalogue(database: Database) -> None:
    with psycopg.connect(database.owner_url) as conn:
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            )
        }
        sensors = {r[0] for r in conn.execute("SELECT id FROM sensor")}

    assert tables >= EXPECTED_TABLES
    assert sensors == EXPECTED_SENSORS


def test_migrations_are_idempotent(database: Database) -> None:
    migrate(database.owner_url, app_password=APP_PASSWORD)  # second run

    with psycopg.connect(database.owner_url) as conn:
        row = conn.execute("SELECT count(*) FROM schema_migrations").fetchone()
        versions = conn.execute("SELECT version FROM schema_migrations").fetchall()

    assert row is not None
    assert row[0] == len(versions) == len({v[0] for v in versions})


@pytest.mark.req("GOV-005")
def test_gov_005_app_role_can_read(database: Database) -> None:
    with psycopg.connect(database.app_url) as conn:
        row = conn.execute("SELECT count(*) FROM sensor").fetchone()

    assert row == (5,)


@pytest.mark.req("GOV-005")
@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE reading SET value = 0",
        "DELETE FROM reading",
        "TRUNCATE reading",
        "UPDATE sensor SET alarm_high = 999",
        "DROP TABLE reading",
    ],
)
def test_gov_005_app_role_cannot_alter_evidence(database: Database, statement: str) -> None:
    with psycopg.connect(database.app_url) as conn, pytest.raises(psycopg.errors.Error):
        conn.execute(statement)
