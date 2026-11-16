"""`telemetry-generate` (SPEC §3.1)."""

from __future__ import annotations

import argparse
import logging
import os
import time
from datetime import datetime
from pathlib import Path

from telemetry import logs
from telemetry.generator.core import DEFAULT_START, generate
from telemetry.generator.files import write_dataset

log = logging.getLogger("telemetry.generator")


def _utc_start(value: str) -> datetime:
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an ISO 8601 timestamp: {value!r}") from None
    if ts.tzinfo is None:
        raise argparse.ArgumentTypeError("start must include a UTC offset, e.g. ...T00:00:00Z")
    if ts.second or ts.microsecond:
        raise argparse.ArgumentTypeError("start must be a whole minute")
    return ts


def _positive(value: str) -> int:
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="telemetry-generate", description=__doc__)
    parser.add_argument("--seed", type=int, default=int(os.environ.get("GENERATOR_SEED", "42")))
    parser.add_argument("--out", type=Path, default=Path("data/generated"))
    parser.add_argument(
        "--weeks", type=_positive, default=int(os.environ.get("GENERATOR_WEEKS", "1"))
    )
    parser.add_argument(
        "--start",
        type=_utc_start,
        default=_utc_start(os.environ.get("GENERATOR_START", DEFAULT_START.isoformat())),
    )
    args = parser.parse_args(argv)

    logs.configure(os.environ.get("LOG_LEVEL", "INFO"))
    started = time.perf_counter()
    meta = write_dataset(generate(seed=args.seed, start=args.start, weeks=args.weeks), args.out)
    log.info(
        "dataset generated",
        extra={
            "out": str(args.out),
            "seed": meta["seed"],
            "generator_version": meta["generator_version"],
            "record_count": meta["record_count"],
            "expected_flags": meta["expected_flags"],
            "duration_s": round(time.perf_counter() - started, 2),
        },
    )
    return 0
