"""Write a generated dataset as `readings.csv` + `manifest.json` (SPEC §3.3, §3.6)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from telemetry.domain.catalogue import SENSORS
from telemetry.generator.core import GENERATOR_VERSION, Dataset

READINGS = "readings.csv"
MANIFEST = "manifest.json"


def iso(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def readings_csv(dataset: Dataset) -> bytes:
    stamps = [iso(dataset.start + timedelta(minutes=m)) for m in range(dataset.minutes)]
    lines = ["seq,sensor_id,ts,value"]
    lines += [
        f"{seq},{SENSORS[r.sensor_index].id},{stamps[r.minute]},{r.value:.3f}"
        for seq, r in enumerate(dataset.records, 1)
    ]
    return ("\n".join(lines) + "\n").encode()


def manifest(dataset: Dataset, readings: bytes) -> dict[str, Any]:
    return {
        "generator_version": GENERATOR_VERSION,
        "seed": dataset.seed,
        "period_start": iso(dataset.start),
        "period_end": iso(dataset.end),
        "readings_sha256": hashlib.sha256(readings).hexdigest(),
        "record_count": len(dataset.records),
        "expected_flags": dataset.expected_flags,
        "missing_slots": dataset.missing_slots,
        "events": [
            {
                "id": e.id,
                "sensor_ids": sorted(e.sensor_ids),
                "start": iso(e.start),
                "end": iso(e.end),
            }
            for e in dataset.events
        ],
    }


def write_dataset(dataset: Dataset, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    readings = readings_csv(dataset)
    meta = manifest(dataset, readings)
    (out_dir / READINGS).write_bytes(readings)
    (out_dir / MANIFEST).write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    return meta
