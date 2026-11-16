"""CI/pre-commit governance checks (scripts/governance/)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from tests.unit.governance.conftest import REPO, load

suppressions = load("scripts/governance/check_suppressions.py")
thresholds = load("scripts/governance/check_thresholds.py")
workflows = load("scripts/governance/check_workflows.py")
req_coverage = load("scripts/governance/req_coverage.py")

NOQA = "# no" + "qa"

THRESHOLD_FILES = (
    "backend/pyproject.toml",
    "frontend/tsconfig.json",
    "frontend/eslint.config.js",
    "frontend/package.json",
)


# --- GOV-012: suppressions --------------------------------------------------------------


@pytest.mark.req("GOV-012")
def test_gov_012_unjustified_suppression_rejected() -> None:
    found = suppressions.violations("backend/src/x.py", f"import os  {NOQA}: F401\n")

    assert len(found) == 1


@pytest.mark.req("GOV-012")
def test_gov_012_justified_suppression_accepted() -> None:
    line = f"KEY = 'x'  {NOQA}: S105  justified: throwaway test credential\n"

    assert suppressions.violations("backend/tests/conftest.py", line) == []


@pytest.mark.req("GOV-012")
def test_gov_012_too_short_justification_rejected() -> None:
    assert suppressions.violations("x.py", f"a = 1  {NOQA}  justified: ok\n")


@pytest.mark.req("GOV-012")
def test_gov_012_repository_has_no_unjustified_suppressions() -> None:
    tracked = [
        p
        for p in REPO.rglob("*")
        if p.is_file()
        and p.suffix in {".py", ".ts", ".tsx", ".js"}
        and not {"node_modules", ".venv", "dist"} & set(p.parts)
    ]
    found = [
        v for p in tracked for v in suppressions.violations(str(p.relative_to(REPO)), p.read_text())
    ]

    assert found == []


# --- GOV-012 / NFR-010: threshold floors -------------------------------------------------


@pytest.mark.req("GOV-012", "NFR-010")
def test_gov_012_current_thresholds_meet_floors() -> None:
    assert thresholds.check(REPO) == []


@pytest.mark.req("GOV-012", "NFR-010")
@pytest.mark.parametrize(
    ("file", "old", "new", "expected"),
    [
        ("backend/pyproject.toml", "fail_under = 85", "fail_under = 80", "coverage"),
        ("backend/pyproject.toml", "strict = true", "strict = false", "mypy"),
        ("backend/pyproject.toml", '"S", "PT"', '"PT"', "ruff lint.select"),
        ("backend/pyproject.toml", '["S101"]', '["S101", "E501"]', "per-file-ignores"),
        ("frontend/tsconfig.json", '"strict": true', '"strict": false', "tsconfig"),
        ("frontend/package.json", "--max-warnings 0", "--max-warnings 10", "max-warnings"),
    ],
)
def test_gov_012_lowered_thresholds_detected(
    repo_copy: Callable[..., Path], file: str, old: str, new: str, expected: str
) -> None:
    root = repo_copy(*THRESHOLD_FILES)
    path = root / file
    assert old in path.read_text()
    path.write_text(path.read_text().replace(old, new, 1))

    problems = thresholds.check(root)

    assert any(expected in p for p in problems), problems


# --- GOV-009 / GOV-010: workflows and pins ----------------------------------------------


@pytest.mark.req("GOV-009", "GOV-010")
def test_gov_010_repository_actions_and_images_are_pinned() -> None:
    assert workflows.check_workflows(REPO) + workflows.check_images(REPO) == []


@pytest.mark.req("GOV-009")
def test_gov_009_workflow_without_permissions_rejected(tmp_path: Path) -> None:
    wf = tmp_path / ".github/workflows/x.yml"
    wf.parent.mkdir(parents=True)
    wf.write_text("on: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n")

    assert any("GOV-009" in p for p in workflows.check_workflows(tmp_path))


@pytest.mark.req("GOV-010")
def test_gov_010_tag_pinned_action_and_unpinned_image_rejected(tmp_path: Path) -> None:
    wf = tmp_path / ".github/workflows/x.yml"
    wf.parent.mkdir(parents=True)
    wf.write_text(
        "permissions:\n  contents: read\n"
        "jobs:\n  a:\n    steps:\n      - uses: actions/checkout@v5\n"
    )
    (tmp_path / "svc").mkdir()
    (tmp_path / "svc/Dockerfile").write_text("FROM python:3.12-slim AS build\nFROM build\n")

    problems = workflows.check_workflows(tmp_path) + workflows.check_images(tmp_path)

    assert len(problems) == 2  # the action and the first FROM; `FROM build` is a stage


# --- GOV-016: traceability ---------------------------------------------------------------


@pytest.mark.req("GOV-016", "NFR-009")
def test_gov_016_repository_traceability_passes() -> None:
    assert req_coverage.build_report(REPO).errors == []


@pytest.mark.req("GOV-016")
def test_gov_016_requirement_without_test_or_status_fails(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/PRD.md").write_text(
        "**FR-001 — A** · M\n**FR-002 — B** · C\n| NFR-001 | x |\n"
    )
    (tmp_path / "docs/GOVERNANCE.md").write_text("| **GOV-001** | rule |\n")
    tests = tmp_path / "backend/tests"
    tests.mkdir(parents=True)
    (tests / "test_a.py").write_text('@pytest.mark.req("FR-001", "NFR-001")\n')
    (tmp_path / "frontend/tests").mkdir(parents=True)

    report = req_coverage.build_report(tmp_path)

    assert report.errors == ["GOV-001: no test and no status entry"]
    assert report.warnings == ["FR-002: (Should/Could) no test and no status entry"]
