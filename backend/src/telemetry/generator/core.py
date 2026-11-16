"""Deterministic synthetic week of pump-skid readings (PRD FR-001, SPEC §3).

Pipeline: signals (§3.4) → scripted events → quality injection in SPEC order: dropouts, gaps,
outliers, late deliveries, duplicates (§3.5) → records in arrival order.
Time is handled as integer minutes from the period start until the files are written.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import numpy as np
from numpy.typing import NDArray

from telemetry.domain.catalogue import SENSORS, Sensor

GENERATOR_VERSION = "1.0.0"
DEFAULT_START = datetime(2026, 11, 2, tzinfo=UTC)
MINUTES_PER_WEEK = 7 * 24 * 60

# §3.5 counts and rates
SINGLE_GAPS = 20
RUN_GAPS = 5
RUN_LENGTH = (2, 10)  # inclusive
OUTLIERS_PER_SENSOR = 10
LATE_RATE = 0.005
DUPLICATE_RATE = 0.002
MAX_DELAY_MIN = 30

Floats = NDArray[np.float64]
Mask = NDArray[np.bool_]


@dataclass(frozen=True)
class Event:
    id: str
    sensor_ids: tuple[str, ...]
    start: datetime
    end: datetime  # exclusive


EVENTS: tuple[Event, ...] = (
    Event(
        "EV-1",
        ("TT-102", "VT-101"),
        datetime(2026, 11, 4, 8, tzinfo=UTC),
        datetime(2026, 11, 4, 14, tzinfo=UTC),
    ),
    Event(
        "EV-2",
        ("FT-101", "PT-101"),
        datetime(2026, 11, 5, 3, tzinfo=UTC),
        datetime(2026, 11, 5, 3, 20, tzinfo=UTC),
    ),
    Event(
        "EV-3",
        ("PT-101",),
        datetime(2026, 11, 6, 15, tzinfo=UTC),
        datetime(2026, 11, 6, 15, 1, tzinfo=UTC),
    ),
)
DROPOUTS: dict[str, tuple[datetime, datetime]] = {
    "FT-101": (datetime(2026, 11, 7, 10, tzinfo=UTC), datetime(2026, 11, 7, 11, 30, tzinfo=UTC)),
    "TT-101": (datetime(2026, 11, 3, 22, tzinfo=UTC), datetime(2026, 11, 3, 22, 20, tzinfo=UTC)),
}


@dataclass(frozen=True)
class Record:
    """One delivery. Times are minutes from the period start."""

    sensor_index: int
    minute: int
    value: float
    arrival: int
    delayed: bool = False
    duplicate: bool = False

    def sort_key(self) -> tuple[int, bool, bool, int, int]:
        # SPEC §3.5 arrival order: time, on-time first, original first, ts, catalogue order.
        return (self.arrival, self.delayed, self.duplicate, self.minute, self.sensor_index)


@dataclass(frozen=True)
class Dataset:
    seed: int
    start: datetime
    minutes: int
    records: tuple[Record, ...]  # arrival order
    expected_flags: dict[str, int]
    missing_slots: dict[str, int]
    events: tuple[Event, ...] = field(default=EVENTS)

    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=self.minutes)


class _Period:
    def __init__(self, start: datetime, minutes: int) -> None:
        self.start, self.minutes = start, minutes

    def span(self, a: datetime, b: datetime) -> slice:
        def index(ts: datetime) -> int:
            return int((ts - self.start).total_seconds() // 60)

        return slice(max(0, index(a)), max(0, min(self.minutes, index(b))))

    def mask(self, windows: list[tuple[datetime, datetime]], pad: int = 0) -> Mask:
        mask = np.zeros(self.minutes, dtype=bool)
        for a, b in windows:
            s = self.span(a, b)
            if s.start < s.stop:
                mask[max(0, s.start - pad) : min(self.minutes, s.stop + pad)] = True
        return mask


def _signals(period: _Period, rngs: dict[str, np.random.Generator]) -> dict[str, Floats]:
    """SPEC §3.4 baseline models with scripted events applied."""
    n = period.minutes
    t = np.arange(n, dtype=np.float64)
    offset = (period.start - period.start.replace(hour=0, minute=0)).total_seconds() / 60
    minute_of_day = (offset + t) % 1440
    hour = minute_of_day / 60
    ev1, ev2, ev3 = (period.span(e.start, e.end) for e in EVENTS)

    flow = np.interp(minute_of_day, [0, 360, 375, 1320, 1335, 1440], [80, 80, 120, 120, 80, 80])
    flow = flow + rngs["FT-101"].normal(0, 2.0, n)
    flow[ev2] = rngs["FT-101"].uniform(0, 0.5, len(flow[ev2]))

    pressure = 2.0 + 0.033 * flow + rngs["PT-101"].normal(0, 0.05, n)
    pressure[ev2] = rngs["PT-101"].uniform(0.45, 0.55, len(pressure[ev2]))
    pressure[ev3] += 1.2

    inlet = 25 + 3 * np.sin(2 * np.pi * (hour - 9) / 24) + rngs["TT-101"].normal(0, 0.3, n)
    outlet = inlet + 6 + 0.015 * flow + rngs["TT-102"].normal(0, 0.3, n)
    outlet[ev1] += np.linspace(0, 32, len(outlet[ev1]), endpoint=False)

    vibration = 2.0 + rngs["VT-101"].normal(0, 0.1, n)
    vibration[ev1] += np.linspace(0, 6.0, len(vibration[ev1]))
    vibration = np.clip(vibration, 0, None)

    return {
        "TT-101": inlet,
        "TT-102": outlet,
        "PT-101": pressure,
        "VT-101": vibration,
        "FT-101": flow,
    }


def _place_gaps(present: Mask, blocked: Mask, rng: np.random.Generator) -> None:
    """20 single + 5 runs, never touching each other or blocked slots (SPEC §3.5)."""
    n = len(present)
    runs = rng.integers(RUN_LENGTH[0], RUN_LENGTH[1] + 1, RUN_GAPS)
    for length in [1] * SINGLE_GAPS + [int(x) for x in runs]:
        while True:
            s = int(rng.integers(1, n - length - 1))
            if not blocked[s - 1 : s + length + 1].any():
                break
        present[s : s + length] = False
        blocked[s - 1 : s + length + 1] = True


def _outlier_value(sensor: Sensor, rng: np.random.Generator) -> float:
    return float([-999.0, 9999.0, 10 * sensor.valid_max][int(rng.integers(0, 3))])


def generate(seed: int, start: datetime = DEFAULT_START, weeks: int = 1) -> Dataset:
    if start.tzinfo is None:
        raise ValueError("start must be timezone-aware (UTC)")
    if weeks < 1:
        raise ValueError("weeks must be >= 1")
    start = start.astimezone(UTC)
    period = _Period(start, weeks * MINUTES_PER_WEEK)
    n = period.minutes
    end = start + timedelta(minutes=n)

    # One child stream per sensor, then one per injection step, in a fixed order (§3.2).
    children = np.random.SeedSequence(seed).spawn(len(SENSORS) + 4)
    rngs = {s.id: np.random.default_rng(c) for s, c in zip(SENSORS, children, strict=False)}
    gap_rng, outlier_rng, late_rng, dup_rng = (
        np.random.default_rng(c) for c in children[len(SENSORS) :]
    )

    values = _signals(period, rngs)
    windows = {s.id: [(e.start, e.end) for e in EVENTS if s.id in e.sensor_ids] for s in SENSORS}
    own_events = {s.id: period.mask(windows[s.id]) for s in SENSORS}

    # Dropouts, then gaps.
    present: dict[str, Mask] = {}
    for sensor in SENSORS:
        dropouts = [DROPOUTS[sensor.id]] if sensor.id in DROPOUTS else []
        alive = ~period.mask(dropouts)
        _place_gaps(alive, period.mask(windows[sensor.id] + dropouts, pad=1), gap_rng)
        present[sensor.id] = alive

    # Outliers.
    outlier: dict[str, Mask] = {}
    for sensor in SENSORS:
        candidates = np.flatnonzero(present[sensor.id] & ~own_events[sensor.id])
        chosen = sorted(
            int(x) for x in outlier_rng.choice(candidates, OUTLIERS_PER_SENSOR, replace=False)
        )
        outlier[sensor.id] = np.zeros(n, dtype=bool)
        outlier[sensor.id][chosen] = True
        for i in chosen:
            values[sensor.id][i] = _outlier_value(sensor, outlier_rng)

    non_outliers = sum(int(present[s.id].sum() - outlier[s.id].sum()) for s in SENSORS)
    n_late = round(LATE_RATE * non_outliers)
    n_dup = round(DUPLICATE_RATE * non_outliers)

    # Late deliveries: the next slot must be present and on time, so the reading is `late`.
    pool = [
        (k, int(i))
        for k, s in enumerate(SENSORS)
        for i in np.flatnonzero(present[s.id] & ~outlier[s.id] & ~own_events[s.id])
        if i + 1 < n
    ]
    delay: dict[tuple[int, int], int] = {}
    for idx in late_rng.permutation(len(pool)):
        if len(delay) == n_late:
            break
        k, i = pool[int(idx)]
        if present[SENSORS[k].id][i + 1] and (k, i + 1) not in delay and (k, i - 1) not in delay:
            delay[(k, i)] = int(late_rng.integers(1, MAX_DELAY_MIN + 1))

    # Duplicates of on-time, non-outlier readings.
    dup_pool = [(k, i) for k, i in pool if (k, i) not in delay]
    duplicates: list[Record] = []
    for idx in sorted(int(x) for x in dup_rng.choice(len(dup_pool), n_dup, replace=False)):
        k, i = dup_pool[idx]
        value = round(float(values[SENSORS[k].id][i] * (1 + dup_rng.uniform(-0.01, 0.01))), 3)
        lag = int(dup_rng.integers(0, MAX_DELAY_MIN + 1))
        duplicates.append(Record(k, i, value, i + lag, duplicate=True))

    def originals() -> Iterator[Record]:
        for k, sensor in enumerate(SENSORS):
            series = values[sensor.id]
            for raw in np.flatnonzero(present[sensor.id]):
                i = int(raw)
                d = delay.get((k, i), 0)
                yield Record(k, i, round(float(series[i]), 3), i + d, delayed=d > 0)

    records = sorted([*originals(), *duplicates], key=Record.sort_key)
    total_present = sum(int(present[s.id].sum()) for s in SENSORS)
    n_outliers = OUTLIERS_PER_SENSOR * len(SENSORS)
    return Dataset(
        seed=seed,
        start=start,
        minutes=n,
        records=tuple(records),
        expected_flags={
            "ok": total_present - n_outliers - len(delay),
            "late": len(delay),
            "outlier": n_outliers,
            "duplicate": len(duplicates),
        },
        missing_slots={s.id: n - int(present[s.id].sum()) for s in SENSORS},
        events=tuple(e for e in EVENTS if e.start < end and e.end > start),
    )
