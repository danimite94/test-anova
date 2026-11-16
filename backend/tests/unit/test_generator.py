"""Synthetic data generator (PRD FR-001, SPEC §3).

Tests read the written files — `readings.csv` and `manifest.json` are the contract the loader
consumes — and check them with independent re-implementations of the SPEC rules.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from telemetry.domain.catalogue import SENSORS
from telemetry.generator import GENERATOR_VERSION, generate, write_dataset
from telemetry.generator.cli import main

START = datetime(2026, 11, 2, tzinfo=UTC)
END = START + timedelta(days=7)
SLOTS_PER_SENSOR = 7 * 24 * 60
SENSOR_IDS = [s.id for s in SENSORS]
BY_ID = {s.id: s for s in SENSORS}

EV1 = (datetime(2026, 11, 4, 8, tzinfo=UTC), datetime(2026, 11, 4, 14, tzinfo=UTC))
EV2 = (datetime(2026, 11, 5, 3, tzinfo=UTC), datetime(2026, 11, 5, 3, 20, tzinfo=UTC))
EV3 = datetime(2026, 11, 6, 15, tzinfo=UTC)
EVENT_WINDOWS = {
    "VT-101": [EV1],
    "TT-102": [EV1],
    "FT-101": [EV2],
    "PT-101": [EV2, (EV3, EV3 + timedelta(minutes=1))],
}


@dataclass(frozen=True)
class Row:
    seq: int
    sensor_id: str
    ts: datetime
    value: float


@dataclass(frozen=True)
class Output:
    directory: Path
    rows: list[Row]
    manifest: dict[str, Any]


def read_output(directory: Path) -> Output:
    with (directory / "readings.csv").open(newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == ["seq", "sensor_id", "ts", "value"]
        rows = [
            Row(
                int(r["seq"]),
                r["sensor_id"],
                datetime.fromisoformat(r["ts"].replace("Z", "+00:00")),
                float(r["value"]),
            )
            for r in reader
        ]
    return Output(directory, rows, json.loads((directory / "manifest.json").read_text()))


def generate_to(directory: Path, seed: int = 42, weeks: int = 1) -> Output:
    write_dataset(generate(seed=seed, weeks=weeks), directory)
    return read_output(directory)


@pytest.fixture(scope="module")
def out(tmp_path_factory: pytest.TempPathFactory) -> Output:
    return generate_to(tmp_path_factory.mktemp("seed42"))


def first_copies(rows: list[Row]) -> Iterator[Row]:
    seen: set[tuple[str, datetime]] = set()
    for row in rows:
        if (row.sensor_id, row.ts) not in seen:
            seen.add((row.sensor_id, row.ts))
            yield row


def in_range(row: Row) -> bool:
    sensor = BY_ID[row.sensor_id]
    return sensor.valid_min <= row.value <= sensor.valid_max


def in_any_event(sensor_id: str, ts: datetime) -> bool:
    return any(a <= ts < b for a, b in EVENT_WINDOWS.get(sensor_id, []))


def present_slots(rows: list[Row]) -> dict[str, set[datetime]]:
    slots: dict[str, set[datetime]] = defaultdict(set)
    for row in rows:
        slots[row.sensor_id].add(row.ts)
    return slots


def missing_runs(present: set[datetime]) -> list[int]:
    """Lengths of consecutive missing-slot runs, in minutes."""
    runs, run = [], 0
    for i in range(SLOTS_PER_SENSOR):
        if START + timedelta(minutes=i) in present:
            if run:
                runs.append(run)
            run = 0
        else:
            run += 1
    return [*runs, run] if run else runs


def reference_flags(rows: list[Row]) -> Counter[str]:
    """SPEC §4.1 classifier, re-implemented independently as the test oracle."""
    seen: set[tuple[str, datetime]] = set()
    latest: dict[str, datetime] = {}
    flags: Counter[str] = Counter()
    for row in sorted(rows, key=lambda r: r.seq):
        key = (row.sensor_id, row.ts)
        if key in seen:
            flags["duplicate"] += 1
        else:
            if not in_range(row):
                flags["outlier"] += 1
            elif row.sensor_id in latest and row.ts < latest[row.sensor_id]:
                flags["late"] += 1
            else:
                flags["ok"] += 1
            latest[row.sensor_id] = max(latest.get(row.sensor_id, row.ts), row.ts)
        seen.add(key)
    return flags


# --- PRD FR-001 acceptance criteria -----------------------------------------------------


@pytest.mark.req("FR-001", "NFR-006")
def test_fr_001_same_seed_and_version_produce_identical_output(tmp_path: Path) -> None:
    generate_to(tmp_path / "a")
    generate_to(tmp_path / "b")

    for name in ("readings.csv", "manifest.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


@pytest.mark.req("FR-001")
def test_fr_001_different_seeds_produce_different_output(tmp_path: Path) -> None:
    a = generate_to(tmp_path / "a", seed=42)
    b = generate_to(tmp_path / "b", seed=43)

    assert a.manifest["readings_sha256"] != b.manifest["readings_sha256"]


@pytest.mark.req("FR-001")
def test_fr_001_every_sensor_has_a_gap(out: Output) -> None:
    present = present_slots(out.rows)

    for sensor_id in SENSOR_IDS:
        assert len(present[sensor_id]) < SLOTS_PER_SENSOR, sensor_id


@pytest.mark.req("FR-001")
def test_fr_001_a_dropout_of_at_least_15_minutes_exists(out: Output) -> None:
    present = present_slots(out.rows)

    longest = max(max(missing_runs(present[s]), default=0) for s in SENSOR_IDS)

    assert longest >= 15


@pytest.mark.req("FR-001")
def test_fr_001_out_of_order_duplicate_and_outlier_deliveries_exist(out: Output) -> None:
    flags = reference_flags(out.rows)

    assert flags["late"] >= 1
    assert flags["duplicate"] >= 1
    assert flags["outlier"] >= 1


@pytest.mark.req("FR-001")
def test_fr_001_timestamps_are_utc_whole_minutes_inside_the_week(out: Output) -> None:
    raw = (out.directory / "readings.csv").read_text().splitlines()[1:]

    assert all(line.split(",")[2].endswith("Z") for line in raw)
    assert all(START <= r.ts < END and r.ts.second == 0 and r.ts.microsecond == 0 for r in out.rows)


# --- SPEC §3.3: file format -------------------------------------------------------------


def test_seq_is_one_based_gap_free_arrival_order(out: Output) -> None:
    assert [r.seq for r in out.rows] == list(range(1, len(out.rows) + 1))


def test_values_have_at_most_three_decimals(out: Output) -> None:
    raw = (out.directory / "readings.csv").read_text().splitlines()[1:]

    assert all(len(line.rsplit(",", 1)[1].partition(".")[2]) <= 3 for line in raw)


# --- SPEC §3.6: manifest is an exact oracle ---------------------------------------------


@pytest.mark.req("FR-001")
def test_manifest_describes_the_file(out: Output) -> None:
    m = out.manifest
    digest = hashlib.sha256((out.directory / "readings.csv").read_bytes()).hexdigest()

    assert m["generator_version"] == GENERATOR_VERSION
    assert m["seed"] == 42
    assert m["period_start"] == "2026-11-02T00:00:00Z"
    assert m["period_end"] == "2026-11-09T00:00:00Z"
    assert m["readings_sha256"] == digest
    assert m["record_count"] == len(out.rows)


@pytest.mark.req("FR-001")
def test_manifest_missing_slots_match_the_data(out: Output) -> None:
    present = present_slots(out.rows)

    expected = {s: SLOTS_PER_SENSOR - len(present[s]) for s in SENSOR_IDS}

    assert out.manifest["missing_slots"] == expected


@pytest.mark.req("FR-001")
def test_manifest_expected_flags_match_an_independent_classification(out: Output) -> None:
    assert out.manifest["expected_flags"] == dict(reference_flags(out.rows))


@pytest.mark.req("FR-001")
def test_manifest_lists_the_scripted_events(out: Output) -> None:
    events = {e["id"]: e for e in out.manifest["events"]}

    assert set(events) == {"EV-1", "EV-2", "EV-3"}
    assert events["EV-1"]["sensor_ids"] == ["TT-102", "VT-101"]
    assert events["EV-1"]["start"] == "2026-11-04T08:00:00Z"
    assert events["EV-1"]["end"] == "2026-11-04T14:00:00Z"


# --- SPEC §3.5: injection counts and placement ------------------------------------------


@pytest.mark.req("FR-001")
def test_injection_counts_follow_the_spec(out: Output) -> None:
    outliers = Counter(r.sensor_id for r in first_copies(out.rows) if not in_range(r))
    present = present_slots(out.rows)
    flags = reference_flags(out.rows)
    non_outliers = sum(len(present[s]) for s in SENSOR_IDS) - flags["outlier"]

    assert outliers == dict.fromkeys(SENSOR_IDS, 10)
    assert flags["late"] == round(0.005 * non_outliers)
    assert flags["duplicate"] == round(0.002 * non_outliers)


def test_scripted_dropouts_are_missing(out: Output) -> None:
    present = present_slots(out.rows)
    ft = [datetime(2026, 11, 7, 10, tzinfo=UTC) + timedelta(minutes=i) for i in range(90)]
    tt = [datetime(2026, 11, 3, 22, tzinfo=UTC) + timedelta(minutes=i) for i in range(20)]

    assert not present["FT-101"] & set(ft)
    assert not present["TT-101"] & set(tt)


def test_event_windows_are_complete_and_free_of_outliers(out: Output) -> None:
    present = present_slots(out.rows)
    for sensor_id, windows in EVENT_WINDOWS.items():
        for a, b in windows:
            minutes = int((b - a).total_seconds() // 60)  # window end is exclusive
            slots = {a + timedelta(minutes=i) for i in range(minutes)}
            assert slots <= present[sensor_id], (sensor_id, a)
    for row in first_copies(out.rows):
        if in_any_event(row.sensor_id, row.ts):
            assert in_range(row), row


def test_gaps_are_separated_from_each_other(out: Output) -> None:
    present = present_slots(out.rows)
    for sensor_id in SENSOR_IDS:
        runs = missing_runs(present[sensor_id])
        dropouts = {"FT-101": 1, "TT-101": 1}.get(sensor_id, 0)
        assert len(runs) == 25 + dropouts, sensor_id  # 20 single + 5 runs, never merged


# --- SPEC §3.4: signals and scripted events ---------------------------------------------


def valid_series(rows: list[Row], sensor_id: str) -> dict[datetime, float]:
    return {r.ts: r.value for r in first_copies(rows) if r.sensor_id == sensor_id and in_range(r)}


def window(series: dict[datetime, float], a: datetime, b: datetime) -> list[float]:
    return [v for t, v in series.items() if a <= t < b]


def test_ev1_bearing_degradation_crosses_warning_then_alarm(out: Output) -> None:
    vt = window(valid_series(out.rows, "VT-101"), *EV1)
    tt = window(valid_series(out.rows, "TT-102"), *EV1)

    assert min(vt) < 4.5 < 7.1 < max(vt)
    assert min(tt) < 55 < 65 < max(tt)


def test_ev2_pump_trip_breaches_low_alarms_without_outliers(out: Output) -> None:
    ft = window(valid_series(out.rows, "FT-101"), *EV2)
    pt = window(valid_series(out.rows, "PT-101"), *EV2)

    assert len(ft) == len(pt) == 20
    assert all(0 <= v <= 0.5 for v in ft)
    assert all(0.45 <= v <= 0.55 for v in pt)


def test_ev3_pressure_spike_is_unusual_but_inside_limits(out: Output) -> None:
    pt = valid_series(out.rows, "PT-101")
    before = window(pt, EV3 - timedelta(minutes=60), EV3)
    mean = sum(before) / len(before)

    assert mean + 0.9 < pt[EV3] < 8.5


def test_no_limit_breaches_outside_scripted_events(out: Output) -> None:
    for sensor in SENSORS:
        series = valid_series(out.rows, sensor.id)
        for ts, value in series.items():
            if in_any_event(sensor.id, ts):
                continue
            assert sensor.warn_low is None or value >= sensor.warn_low, (sensor.id, ts, value)
            assert sensor.warn_high is None or value <= sensor.warn_high, (sensor.id, ts, value)


# --- SPEC §3.1: interface ----------------------------------------------------------------


@pytest.mark.req("FR-001")
def test_weeks_extends_the_period(tmp_path: Path) -> None:
    two = generate_to(tmp_path, weeks=2)

    assert two.manifest["period_end"] == "2026-11-16T00:00:00Z"
    assert len(present_slots(two.rows)["VT-101"]) > SLOTS_PER_SENSOR


@pytest.mark.req("FR-001")
def test_cli_writes_both_files(tmp_path: Path) -> None:
    code = main(["--seed", "7", "--out", str(tmp_path)])

    assert code == 0
    assert read_output(tmp_path).manifest["seed"] == 7


def test_cli_rejects_a_start_without_utc_offset(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--out", str(tmp_path), "--start", "2026-11-02T00:00:00"])

    assert exc.value.code == 2
