#!/usr/bin/env python3
"""Requirement traceability report (GOV-016, NFR-009).

Collects requirement IDs from docs/PRD.md (FR, NFR) and docs/GOVERNANCE.md (GOV), and the IDs
that tests reference:
  - Python:     @pytest.mark.req("FR-006", ...)        in backend/tests/
  - Playwright/Vitest: "[FR-006]" in test titles         in frontend/tests/

IDs without tests must be listed in req_status.txt with a status:
  pending  — not built yet (Phase 3); the list only shrinks
  ci       — verified by a CI job rather than a test
  review   — verified by human review
  manual   — verified manually
  demo     — verified by scripts/governance/demo.sh

Fails (exit 1) when a Must FR, any NFR or any GOV ID has neither a test nor a status entry, or
when req_status.txt names an unknown ID. Should/Could FRs without either are warnings.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

FR_HEADING = re.compile(r"^\*\*(FR-\d{3}) — .+?\*\* · ([MSC])\b", re.MULTILINE)
NFR_ROW = re.compile(r"^\| (NFR-\d{3}) \|", re.MULTILINE)
GOV_ROW = re.compile(r"^\| \*\*(GOV-\d{3})\*\* \|", re.MULTILINE)
PY_REQ = re.compile(r"req\(([^)]*)\)")
ANY_ID = re.compile(r"\b(?:FR|NFR|GOV)-\d{3}\b")
TITLE_ID = re.compile(r"\[((?:FR|NFR|GOV)-\d{3})\]")
STATUSES = {"pending", "ci", "review", "manual", "demo"}


@dataclass
class Report:
    required: set[str] = field(default_factory=set)
    optional: set[str] = field(default_factory=set)
    tested: set[str] = field(default_factory=set)
    status: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def requirement_ids(root: Path) -> tuple[set[str], set[str]]:
    prd = (root / "docs/PRD.md").read_text()
    gov = (root / "docs/GOVERNANCE.md").read_text()
    must = {i for i, p in FR_HEADING.findall(prd) if p == "M"}
    optional = {i for i, p in FR_HEADING.findall(prd) if p != "M"}
    required = must | set(NFR_ROW.findall(prd)) | set(GOV_ROW.findall(gov))
    return required, optional


def tested_ids(root: Path) -> set[str]:
    ids: set[str] = set()
    for path in (root / "backend/tests").rglob("*.py"):
        for args in PY_REQ.findall(path.read_text()):
            ids.update(ANY_ID.findall(args))
    for pattern in ("*.ts", "*.tsx"):
        for path in (root / "frontend/tests").rglob(pattern):
            ids.update(TITLE_ID.findall(path.read_text()))
    return ids


def read_status(path: Path, report: Report) -> None:
    if not path.exists():
        return
    for n, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split(None, 2)
        if len(parts) < 3 or parts[1] not in STATUSES:
            report.errors.append(
                f"{path.name}:{n}: expected '<ID> <{'|'.join(sorted(STATUSES))}> <reason>'"
            )
            continue
        report.status[parts[0]] = parts[1]


def build_report(root: Path) -> Report:
    report = Report()
    report.required, report.optional = requirement_ids(root)
    report.tested = tested_ids(root)
    read_status(root / "scripts/governance/req_status.txt", report)

    known = report.required | report.optional
    for unknown in sorted((set(report.status) | report.tested) - known):
        report.errors.append(f"{unknown}: referenced but not defined in PRD or GOVERNANCE")
    for rid in sorted(report.required - report.tested - set(report.status)):
        report.errors.append(f"{rid}: no test and no status entry")
    for rid in sorted(report.optional - report.tested - set(report.status)):
        report.warnings.append(f"{rid}: (Should/Could) no test and no status entry")
    for rid in sorted(report.tested & {r for r, s in report.status.items() if s == "pending"}):
        report.warnings.append(f"{rid}: now has tests — remove its 'pending' line")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    report = build_report(args.root)

    known = sorted(report.required | report.optional)
    by_status: dict[str, int] = {}
    for rid in known:
        key = "tested" if rid in report.tested else report.status.get(rid, "missing")
        by_status[key] = by_status.get(key, 0) + 1
    print(
        f"Requirements: {len(known)}  "
        + "  ".join(f"{k}={v}" for k, v in sorted(by_status.items()))
    )
    for warning in report.warnings:
        print(f"WARN  {warning}")
    for error in report.errors:
        print(f"ERROR {error}")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
