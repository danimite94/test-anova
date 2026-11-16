#!/usr/bin/env python3
"""Quality-threshold floors that cannot be lowered (GOV-012, NFR-010).

Floors live here, in a protected path (GOV-013), not next to the values they guard.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

COVERAGE_FLOOR = 85
RUFF_RULES_FLOOR = {"E", "F", "W", "I", "N", "B", "UP", "S", "PT", "SIM", "RUF"}
ALLOWED_PER_FILE_IGNORES = {"tests/**": {"S101"}}
PYTEST_ADDOPTS_FLOOR = {"--strict-markers", "--strict-config"}
TSCONFIG_FLOOR = {"strict": True, "noUncheckedIndexedAccess": True}


def check(root: Path) -> list[str]:
    problems: list[str] = []
    py = tomllib.loads((root / "backend/pyproject.toml").read_text())
    tool = py.get("tool", {})

    fail_under = tool.get("coverage", {}).get("report", {}).get("fail_under", 0)
    if fail_under < COVERAGE_FLOOR:
        problems.append(f"coverage fail_under is {fail_under}, floor is {COVERAGE_FLOOR}")

    if tool.get("mypy", {}).get("strict") is not True:
        problems.append("mypy strict must be true")

    lint = tool.get("ruff", {}).get("lint", {})
    missing = RUFF_RULES_FLOOR - set(lint.get("select", []))
    if missing:
        problems.append(f"ruff lint.select is missing {sorted(missing)}")
    if lint.get("ignore"):
        problems.append(f"ruff lint.ignore must be empty, found {lint['ignore']}")
    for pattern, codes in lint.get("per-file-ignores", {}).items():
        extra = set(codes) - ALLOWED_PER_FILE_IGNORES.get(pattern, set())
        if extra:
            problems.append(f"ruff per-file-ignores[{pattern!r}] adds {sorted(extra)}")

    addopts = set(tool.get("pytest", {}).get("ini_options", {}).get("addopts", []))
    if not addopts >= PYTEST_ADDOPTS_FLOOR:
        problems.append(f"pytest addopts must include {sorted(PYTEST_ADDOPTS_FLOOR)}")

    ts = json.loads((root / "frontend/tsconfig.json").read_text()).get("compilerOptions", {})
    for key, value in TSCONFIG_FLOOR.items():
        if ts.get(key) != value:
            problems.append(f"tsconfig compilerOptions.{key} must be {value}")

    if "strictTypeChecked" not in (root / "frontend/eslint.config.js").read_text():
        problems.append("eslint config must extend typescript-eslint strictTypeChecked")
    pkg = json.loads((root / "frontend/package.json").read_text())
    if "--max-warnings 0" not in pkg.get("scripts", {}).get("lint", ""):
        problems.append("frontend lint script must use --max-warnings 0")

    ci = root / ".github/workflows/ci.yml"
    if ci.exists() and f"--cov-fail-under={COVERAGE_FLOOR}" not in ci.read_text():
        problems.append(f"ci.yml must pass --cov-fail-under={COVERAGE_FLOOR} explicitly")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    problems = check(parser.parse_args(argv).root)
    for problem in problems:
        print(f"GOV-012 {problem}")
    if not problems:
        print("Quality thresholds at or above their floors.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
