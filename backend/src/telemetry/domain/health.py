"""Health status rules (SPEC §6.3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class HealthReport:
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable"]
    dataset_loaded: bool


def evaluate_health(*, database_ok: bool, dataset_loaded: bool) -> HealthReport:
    """The API is up whenever this runs; only the database part can degrade."""
    if not database_ok:
        return HealthReport(status="degraded", database="unavailable", dataset_loaded=False)
    return HealthReport(status="ok", database="ok", dataset_loaded=dataset_loaded)
