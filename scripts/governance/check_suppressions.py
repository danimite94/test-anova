#!/usr/bin/env python3
"""Reject check suppressions that lack a justification (GOV-012).

A suppression is allowed only with a same-line `justified: <reason>` (≥ 10 characters), e.g.
    API_KEY = "x"  # noqa: S105  justified: throwaway test container credential

Usage: check_suppressions.py FILE...   (pre-commit passes staged files; CI passes all files)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PATTERNS = [
    r"#\s*noqa\b",
    r"#\s*type:\s*ignore",
    r"#\s*pragma:\s*no\s*cover",
    r"eslint-disable",
    r"@ts-(?:ignore|expect-error|nocheck)",
    r"pytest\.mark\.(?:skip|skipif|xfail)\b",
    r"pytest\.(?:skip|xfail)\(",
    r"\b(?:it|test|describe)\.(?:skip|only)\b",
]
SUPPRESSION = re.compile("|".join(PATTERNS))
JUSTIFIED = re.compile(r"justified:\s*\S.{8,}")

# The rule definitions themselves mention the tokens; these paths are protected (GOV-013).
EXEMPT_PREFIXES = ("scripts/governance/", ".claude/hooks/")
EXEMPT_SUFFIXES = (".md",)


def violations(path: str, text: str) -> list[str]:
    normalized = path.replace("\\", "/").removeprefix("./")
    if normalized.startswith(EXEMPT_PREFIXES) or normalized.endswith(EXEMPT_SUFFIXES):
        return []
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        match = SUPPRESSION.search(line)
        if match and not JUSTIFIED.search(line):
            found.append(f"{path}:{n}: '{match.group(0)}' without 'justified: <reason>'")
    return found


def main(argv: list[str]) -> int:
    problems: list[str] = []
    for name in argv:
        try:
            text = Path(name).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        problems.extend(violations(name, text))
    for problem in problems:
        print(f"GOV-012 {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
