#!/usr/bin/env python3
"""PreToolUse guard for shell commands (GOV-008, GOV-013, GOV-014).

Pattern-based by design: it catches the direct forms of risky commands. Indirect forms are
caught by CI and review (see docs/GOVERNANCE.md, "Known limits").
Standard library only and Python 3.9-compatible.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

PROTECTED = (
    "(?:"
    + "|".join(
        [
            r"\.claude/",
            r"\.github/",
            r"scripts/governance/",
            r"\.pre-commit-config\.yaml",
            r"CODEOWNERS",
            r"eslint\.config\.js",
            r"tsconfig\.json",
            r"pyproject\.toml",
        ]
    )
    + ")"
)
WRITE_VERBS = (
    "(?:"
    + "|".join(
        [
            r">",
            r">>",
            r"\btee\b",
            r"\bsed\s+-i",
            r"\bperl\s+-[a-z]*i",
            r"\b(?:cp|mv|rm|truncate|chmod|ln)\b",
            r"git\s+(?:checkout|restore|rm|mv)\b",
        ]
    )
    + ")"
)
ENV_REF = re.compile(r"(?:^|[\s'\"=/<>(])\.env(?!\.example)(?:\.[\w.-]+)?(?=$|[\s'\";|&)<>])")

RULES: list[tuple[str, re.Pattern[str]]] = [
    ("GOV-014: hooks must not be skipped (--no-verify)", re.compile(r"--no-verify\b")),
    (
        "GOV-014: 'git commit -n' skips hooks",
        re.compile(r"\bgit\s+commit\b[^|;&]*\s-[a-zA-Z]*n[a-zA-Z]*(?:\s|$)"),
    ),
    (
        "GOV-014: pre-commit hooks must not be skipped (SKIP=)",
        re.compile(r"\bSKIP=\S+.*\bgit\s+commit\b"),
    ),
    (
        "GOV-014: no force pushes",
        re.compile(r"\bgit\s+push\b.*(?:\s--force(?:-with-lease)?\b|\s-f\b|\s\+\S)"),
    ),
    (
        "GOV-014: no pushes to main",
        re.compile(r"\bgit\s+push\b.*(?:\smain\b|:main\b|\sHEAD:main\b)"),
    ),
    ("GOV-014: merging PRs is for humans", re.compile(r"\bgh\s+pr\s+merge\b")),
    (
        "GOV-014: git hooks must stay installed",
        re.compile(r"\bcore\.hooksPath\b|\bpre-commit\s+uninstall\b|\.git/hooks"),
    ),
    ("GOV-008: agents never touch .env files", ENV_REF),
    (
        "GOV-013: writes to protected paths are for humans",
        re.compile(rf"{WRITE_VERBS}[^|;&]*{PROTECTED}|{PROTECTED}[^|;&]*\s(?:>|>>)\s"),
    ),
]


def decide(event: dict[str, Any]) -> str | None:
    command = str((event.get("tool_input") or {}).get("command", ""))
    for message, pattern in RULES:
        if pattern.search(command):
            return f"Blocked by {message}. Ask the user if this is really needed."
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    reason = decide(event)
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
