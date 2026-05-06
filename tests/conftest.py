from __future__ import annotations

import shutil
from pathlib import Path

import pytest


@pytest.fixture
def small_dataset(tmp_path: Path) -> Path:
    source = Path(__file__).parent / "fixtures" / "small_dataset"
    target = tmp_path / "small_dataset"
    shutil.copytree(source, target)
    return target
