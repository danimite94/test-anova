"""Agent file guard (.claude/hooks/guard_paths.py)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.unit.governance.conftest import REPO, load

guard = load(".claude/hooks/guard_paths.py")

NOQA = "# no" + "qa"  # built so this file itself carries no suppression token
SKIP = "pytest.mark." + "skip"


def event(tool: str, path: str, **tool_input: Any) -> dict[str, Any]:
    return {"tool_name": tool, "tool_input": {"file_path": path, **tool_input}}


@pytest.mark.req("GOV-008")
@pytest.mark.parametrize("tool", ["Read", "Write", "Edit"])
@pytest.mark.parametrize("path", [".env", "backend/.env", ".env.local", ".env.production"])
def test_gov_008_env_files_blocked_for_any_file_tool(tool: str, path: str) -> None:
    reason = guard.decide(event(tool, path, content="X=1"), REPO)

    assert reason is not None
    assert "GOV-008" in reason


@pytest.mark.req("GOV-008")
def test_gov_008_env_example_is_allowed() -> None:
    assert guard.decide(event("Read", ".env.example"), REPO) is None


@pytest.mark.req("GOV-013")
@pytest.mark.parametrize(
    "path",
    [
        ".github/workflows/ci.yml",
        ".claude/settings.json",
        ".claude/hooks/guard_paths.py",
        "scripts/governance/check_thresholds.py",
        ".pre-commit-config.yaml",
        "frontend/tsconfig.json",
        "frontend/eslint.config.js",
    ],
)
def test_gov_013_protected_paths_blocked(path: str) -> None:
    reason = guard.decide(event("Write", path, content="anything"), REPO)

    assert reason is not None
    assert "GOV-013" in reason


@pytest.mark.req("GOV-013")
def test_gov_013_absolute_paths_are_normalised() -> None:
    reason = guard.decide(event("Write", str(REPO / ".github" / "x.yml"), content=""), REPO)

    assert reason is not None


@pytest.mark.req("GOV-013")
def test_gov_013_tool_config_in_pyproject_blocked_but_dependencies_allowed() -> None:
    lower = event(
        "Edit", "backend/pyproject.toml", old_string="fail_under = 85", new_string="fail_under = 50"
    )
    add_dep = event(
        "Edit",
        "backend/pyproject.toml",
        old_string='    "pydantic>=2.9",',
        new_string='    "pydantic>=2.9",\n    "numpy>=2.0",',
    )

    assert "GOV-013" in (guard.decide(lower, REPO) or "")
    assert guard.decide(add_dep, REPO) is None


@pytest.mark.req("GOV-013")
def test_gov_013_accepted_adrs_are_immutable_new_adrs_are_not() -> None:
    accepted = "docs/adr/0001-postgresql-for-time-series-storage.md"

    assert "GOV-013" in (guard.decide(event("Write", accepted, content="x"), REPO) or "")
    assert guard.decide(event("Write", "docs/adr/0099-new-decision.md", content="x"), REPO) is None


@pytest.mark.req("GOV-012")
@pytest.mark.parametrize(
    ("path", "line"),
    [
        ("backend/src/telemetry/x.py", f"import os  {NOQA}: F401"),
        ("backend/src/telemetry/x.py", "x = f()  # type: " + "ignore"),
        ("backend/tests/unit/test_x.py", f"@{SKIP}\ndef test_x(): ..."),
        ("frontend/src/x.ts", "// eslint-" + "disable-next-line\nconst x = 1;"),
        ("frontend/tests/unit/x.test.ts", "it." + "only('x', () => {});"),
    ],
)
def test_gov_012_new_suppressions_blocked(path: str, line: str) -> None:
    reason = guard.decide(event("Write", path, content=line), REPO)

    assert reason is not None
    assert "GOV-012" in reason


@pytest.mark.req("GOV-012")
def test_gov_012_existing_suppressions_may_stay_when_editing_elsewhere(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text(f"a = 1  {NOQA}: E501  justified: long generated line\nb = 2\n")
    edit = event("Edit", str(tmp_path / "m.py"), old_string="b = 2", new_string="b = 3")

    assert guard.decide(edit, tmp_path) is None


@pytest.mark.req("GOV-016")
def test_gov_016_req_status_may_only_shrink(tmp_path: Path) -> None:
    status = tmp_path / "scripts/governance/req_status.txt"
    status.parent.mkdir(parents=True)
    status.write_text("FR-001 pending x\nFR-002 pending y\n")
    rel = "scripts/governance/req_status.txt"

    remove = event("Edit", rel, old_string="FR-001 pending x\n", new_string="")
    add = event(
        "Edit",
        rel,
        old_string="FR-002 pending y\n",
        new_string="FR-002 pending y\nFR-003 pending z\n",
    )

    assert guard.decide(remove, tmp_path) is None
    assert "GOV-016" in (guard.decide(add, tmp_path) or "")


def test_ordinary_source_edits_and_outside_paths_are_allowed() -> None:
    assert (
        guard.decide(event("Write", "backend/src/telemetry/new.py", content="x = 1\n"), REPO)
        is None
    )
    assert guard.decide(event("Write", "/opt/elsewhere/.env", content="X=1"), REPO) is None
