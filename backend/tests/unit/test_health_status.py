"""Health status rules (SPEC §6.3)."""

import pytest

from telemetry.domain.health import HealthReport, evaluate_health


@pytest.mark.req("NFR-011")
def test_nfr_011_healthy_when_database_reachable() -> None:
    report = evaluate_health(database_ok=True, dataset_loaded=True)

    assert report == HealthReport(status="ok", database="ok", dataset_loaded=True)


@pytest.mark.req("NFR-011")
def test_nfr_011_degraded_not_failed_when_database_down() -> None:
    """The API stays up and says so, so healthchecks can tell API and DB failures apart."""
    report = evaluate_health(database_ok=False, dataset_loaded=False)

    assert report == HealthReport(status="degraded", database="unavailable", dataset_loaded=False)


@pytest.mark.req("NFR-011")
def test_nfr_011_dataset_unknown_when_database_down_is_reported_as_not_loaded() -> None:
    report = evaluate_health(database_ok=False, dataset_loaded=True)

    assert report.dataset_loaded is False
