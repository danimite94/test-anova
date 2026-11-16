#!/usr/bin/env python3
"""PreToolUse guard for file tools (GOV-008, GOV-012, GOV-013).

Reads the hook event from stdin. Exit 2 blocks the tool call; stderr is shown to the agent.
Standard library only and Python 3.9-compatible: it runs before any virtualenv exists.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ENV_FILE = re.compile(r"(^|/)\.env(\.[^/]*)?$")
ENV_EXAMPLE = re.compile(r"(^|/)\.env\.example$")
PROTECTED_PREFIXES = (".claude/", ".github/", "scripts/governance/")
PROTECTED_FILES = {
    ".pre-commit-config.yaml",
    "CODEOWNERS",
    "frontend/eslint.config.js",
    "frontend/tsconfig.json",
}
REMOVE_ONLY_FILES = {"scripts/governance/req_status.txt"}
PYPROJECT = "backend/pyproject.toml"
PROTECTED_TOML_SECTION = re.compile(r"^\[\[?tool\.(ruff|mypy|pytest|coverage)\b")
ACCEPTED_ADR = re.compile(r"^docs/adr/\d{4}-.+\.md$")
SUPPRESSION = re.compile(
    "|".join(
        [
            r"#\s*noqa\b",
            r"#\s*type:\s*ignore",
            r"#\s*pragma:\s*no\s*cover",
            r"eslint-disable",
            r"@ts-(?:ignore|expect-error|nocheck)",
            r"pytest\.mark\.(?:skip|skipif|xfail)\b",
            r"pytest\.(?:skip|xfail)\(",
            r"\b(?:it|test|describe)\.(?:skip|only)\b",
        ]
    )
)
ASK_USER = "Propose the change to the user instead; a human applies it."


def project_root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()


def relative(path: str, root: Path) -> str | None:
    """Repo-relative POSIX path, or None for files outside the project."""
    full = Path(path)
    if not full.is_absolute():
        full = root / full
    try:
        return full.resolve().relative_to(root).as_posix()
    except ValueError:
        return None


def is_env_file(rel: str) -> bool:
    return bool(ENV_FILE.search(rel)) and not ENV_EXAMPLE.search(rel)


def read(root: Path, rel: str) -> str:
    try:
        return (root / rel).read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError, IsADirectoryError):
        return ""


def proposed_content(tool: str, tool_input: dict[str, Any], current: str) -> str:
    if tool == "Write":
        return str(tool_input.get("content", ""))
    edits = tool_input.get("edits") if tool == "MultiEdit" else [tool_input]
    result = current
    for edit in edits or []:
        old, new = str(edit.get("old_string", "")), str(edit.get("new_string", ""))
        result = (
            result.replace(old, new) if edit.get("replace_all") else result.replace(old, new, 1)
        )
    return result


def protected_toml(text: str) -> str:
    keep, inside = [], False
    for line in text.splitlines():
        if line.startswith("["):
            inside = bool(PROTECTED_TOML_SECTION.match(line))
        if inside:
            keep.append(line)
    return "\n".join(keep)


def suppression_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if SUPPRESSION.search(line))


def decide(event: dict[str, Any], root: Path) -> str | None:
    """Return a block reason, or None to allow."""
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not path:
        return None
    rel = relative(str(path), root)
    if rel is None:
        return None

    if is_env_file(rel):
        verb = "read" if tool == "Read" else "write"
        return f"Blocked by GOV-008: agents never {verb} .env files ({rel}). Use .env.example."
    if tool == "Read":
        return None

    current = read(root, rel)
    new = proposed_content(tool, tool_input, current)

    if rel in REMOVE_ONLY_FILES:
        added = set(new.splitlines()) - set(current.splitlines())
        if added:
            return f"Blocked by GOV-016: {rel} may only shrink; it would gain {sorted(added)}."
        return None
    if rel in PROTECTED_FILES or rel.startswith(PROTECTED_PREFIXES):
        return f"Blocked by GOV-013: {rel} is a protected path. {ASK_USER}"
    if rel == PYPROJECT and protected_toml(current) != protected_toml(new):
        return f"Blocked by GOV-013: tool configuration in {rel} is protected. {ASK_USER}"
    if ACCEPTED_ADR.match(rel) and "**Status:** Accepted" in current:
        return f"Blocked by GOV-013: {rel} is an accepted ADR; write a new ADR that supersedes it."
    if not rel.endswith(".md") and suppression_count(new) > suppression_count(current):
        return (
            f"Blocked by GOV-012: the change adds a check suppression to {rel}. Fix the cause, "
            "or ask the user to approve a suppression with 'justified: <reason>'."
        )
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    reason = decide(event, project_root())
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
