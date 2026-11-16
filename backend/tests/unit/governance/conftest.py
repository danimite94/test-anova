"""Load the governance scripts and agent hooks (which live outside the package) by path."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[4]


def load(relative: str) -> ModuleType:
    path = REPO / relative
    name = "gov_" + path.stem
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repo_copy(tmp_path: Path) -> Callable[..., Path]:
    """Copy selected repo files into a temp root, so tests can tamper with them safely."""

    def make(*files: str) -> Path:
        for rel in files:
            target = tmp_path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(REPO / rel, target)
        return tmp_path

    return make
