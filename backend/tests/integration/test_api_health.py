"""GET /api/v1/health end to end against a real database (SPEC §6.3)."""

import pytest
from fastapi.testclient import TestClient

from telemetry.api.app import create_app
from telemetry.config import Settings
from tests.conftest import Database


@pytest.mark.req("NFR-011")
def test_nfr_011_health_reports_database_ok(database: Database) -> None:
    app = create_app(Settings(database_url=database.app_url))

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "dataset_loaded": False}


@pytest.mark.req("NFR-011")
def test_nfr_011_health_is_200_and_degraded_when_database_unreachable() -> None:
    app = create_app(
        Settings(database_url="postgresql://nobody:wrong@127.0.0.1:1/none", db_timeout_s=1.0)
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "database": "unavailable",
        "dataset_loaded": False,
    }


@pytest.mark.req("NFR-011")
def test_nfr_011_unknown_route_returns_problem_details() -> None:
    app = create_app(Settings(database_url="postgresql://nobody@127.0.0.1:1/none"))

    with TestClient(app) as client:
        response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["status"] == 404
    assert body["type"].endswith("/not-found")
