"""Agent shell guard (.claude/hooks/guard_bash.py)."""

from __future__ import annotations

import pytest

from tests.unit.governance.conftest import load

guard = load(".claude/hooks/guard_bash.py")


def decide(command: str) -> str | None:
    result: str | None = guard.decide({"tool_name": "Bash", "tool_input": {"command": command}})
    return result


@pytest.mark.req("GOV-014")
@pytest.mark.parametrize(
    "command",
    [
        "git commit --no-verify -m 'x'",
        "git commit -nm 'x'",
        "git commit -an -m 'wip'",
        "SKIP=ruff-check git commit -m x",
        "git push --force origin feature",
        "git push -f",
        "git push origin +feature",
        "git push origin main",
        "git push origin HEAD:main",
        "gh pr merge 12 --squash",
        "git config core.hooksPath /dev/null",
        "pre-commit uninstall",
        "rm .git/hooks/pre-commit",
    ],
)
def test_gov_014_risky_git_commands_blocked(command: str) -> None:
    reason = decide(command)

    assert reason is not None
    assert "GOV-014" in reason


@pytest.mark.req("GOV-008")
@pytest.mark.parametrize(
    "command",
    [
        "cat .env",
        "echo X=1 >> .env",
        "cp .env.example .env",
        "source ./.env",
        "grep KEY backend/.env.local",
    ],
)
def test_gov_008_shell_access_to_env_files_blocked(command: str) -> None:
    assert "GOV-008" in (decide(command) or "")


@pytest.mark.req("GOV-013")
@pytest.mark.parametrize(
    "command",
    [
        "sed -i '' 's/85/50/' backend/pyproject.toml",
        "echo x > .github/workflows/ci.yml",
        "rm scripts/governance/check_thresholds.py",
        "cp /tmp/x .claude/settings.json",
        "git checkout main -- .pre-commit-config.yaml",
        "tee frontend/tsconfig.json < /tmp/x",
    ],
)
def test_gov_013_shell_writes_to_protected_paths_blocked(command: str) -> None:
    assert "GOV-013" in (decide(command) or "")


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m 'feat: add x'",
        "git push -u origin phase-2-foundation",
        "cat .env.example",
        "cat backend/pyproject.toml",
        "grep -n strict frontend/tsconfig.json",
        "git diff .github/workflows/ci.yml",
        "make test-fast",
        "uv --directory backend run pytest -q",
    ],
)
def test_everyday_commands_are_allowed(command: str) -> None:
    assert decide(command) is None
