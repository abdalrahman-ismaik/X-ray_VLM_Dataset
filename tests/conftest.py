from __future__ import annotations

import shutil
from pathlib import Path

import pytest


@pytest.fixture
def small_dataset(tmp_path: Path) -> Path:
    source = Path(__file__).parent / "fixtures" / "small_dataset"
    target = tmp_path / "small_dataset"
    shutil.copytree(source, target)
    generated_state = target / "curation"
    if generated_state.exists():
        shutil.rmtree(generated_state)
    return target


@pytest.fixture
def annotation_editor_case_path() -> Path:
    return (
        Path(__file__).parent
        / "fixtures"
        / "annotation_editor_cases"
        / "overlap_unknown_unsupported.json"
    )


@pytest.fixture
def apply_annotation_editor_case(annotation_editor_case_path: Path):
    def apply(dataset_root: Path, image_id: str = "image_000") -> Path:
        target = dataset_root / "json" / f"{image_id}.json"
        shutil.copyfile(annotation_editor_case_path, target)
        return target

    return apply
