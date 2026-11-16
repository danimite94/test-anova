#!/usr/bin/env python3
"""Supply-chain and CI-permission checks (GOV-009, GOV-010).

- Every GitHub workflow declares top-level `permissions:` and never `write-all`.
- Every `uses:` of an external action is pinned to a full 40-character commit SHA.
- Every Dockerfile `FROM` and compose `image:` of an external image is pinned by digest.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

USES = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
SHA = re.compile(r"@[0-9a-f]{40}$")
FROM = re.compile(r"^FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?", re.MULTILINE | re.I)
IMAGE = re.compile(r"^\s*image:\s*([^\s#]+)", re.MULTILINE)
LOCAL_IMAGE = re.compile(r":local$")


def check_workflows(root: Path) -> list[str]:
    problems: list[str] = []
    for path in sorted((root / ".github/workflows").glob("*.y*ml")):
        text = path.read_text()
        rel = path.relative_to(root)
        if not re.search(r"^permissions:", text, re.MULTILINE):
            problems.append(f"GOV-009 {rel}: missing top-level 'permissions:'")
        if "write-all" in text:
            problems.append(f"GOV-009 {rel}: 'write-all' permissions")
        for ref in USES.findall(text):
            if ref.startswith("./") or ref.startswith("docker://"):
                continue
            if not SHA.search(ref):
                problems.append(f"GOV-010 {rel}: action not pinned to a commit SHA: {ref}")
    return problems


def check_images(root: Path) -> list[str]:
    problems: list[str] = []
    for path in sorted(root.glob("*/Dockerfile")):
        stages: set[str] = set()
        for image, alias in FROM.findall(path.read_text()):
            if image not in stages and "@sha256:" not in image:
                problems.append(f"GOV-010 {path.relative_to(root)}: FROM not pinned: {image}")
            if alias:
                stages.add(alias)
    for path in sorted(root.glob("compose*.y*ml")):
        for image in IMAGE.findall(path.read_text()):
            if not LOCAL_IMAGE.search(image) and "@sha256:" not in image:
                problems.append(f"GOV-010 {path.relative_to(root)}: image not pinned: {image}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    root = parser.parse_args(argv).root
    problems = check_workflows(root) + check_images(root)
    for problem in problems:
        print(problem)
    if not problems:
        print("Workflows least-privilege; actions and images pinned.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
