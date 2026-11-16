"""The generated OpenAPI document must equal the committed contract (ADR-0007).

API changes are therefore always deliberate: regenerate with `make openapi` and review the diff.
"""

import json
from pathlib import Path

import pytest

from telemetry.api.app import create_app
from telemetry.config import Settings

CONTRACT = Path(__file__).resolve().parents[3] / "docs" / "openapi.json"


@pytest.mark.req("NFR-009")
def test_nfr_009_openapi_matches_committed_contract() -> None:
    generated = create_app(Settings(database_url="postgresql://unused@localhost/x")).openapi()

    assert CONTRACT.exists(), "docs/openapi.json missing — run `make openapi`"
    assert generated == json.loads(CONTRACT.read_text()), (
        "API differs from docs/openapi.json — if intended, run `make openapi` and review the diff"
    )
