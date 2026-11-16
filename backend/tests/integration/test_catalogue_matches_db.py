"""The code catalogue and the seeded `sensor` table must not drift apart (SPEC §2.1)."""

import psycopg
from telemetry.domain.catalogue import SENSORS

from tests.conftest import Database

QUERY = """
    SELECT id, name, measurement, unit, valid_min, valid_max,
           alarm_low, warn_low, warn_high, alarm_high
    FROM sensor
    ORDER BY id
"""


def test_catalogue_matches_seeded_sensor_table(database: Database) -> None:
    with psycopg.connect(database.owner_url) as conn:
        rows = conn.execute(QUERY).fetchall()

    expected = sorted(
        (
            s.id,
            s.name,
            s.measurement,
            s.unit,
            s.valid_min,
            s.valid_max,
            s.alarm_low,
            s.warn_low,
            s.warn_high,
            s.alarm_high,
        )
        for s in SENSORS
    )
    assert rows == expected
