from __future__ import annotations

from pathlib import Path

from xray_curation.gui.annotation_editor import (
    ANNOTATION_EDITOR_GUIDANCE_TEXT,
    ANNOTATION_EDITOR_REQUIRED_GUIDANCE_TERMS,
)
from xray_curation.gui.app import ANNOTATION_EDITOR_WORKFLOW_TEXT


def _missing_terms(text: str) -> list[str]:
    folded = text.casefold()
    return [
        term
        for term in ANNOTATION_EDITOR_REQUIRED_GUIDANCE_TERMS
        if term.casefold() not in folded
    ]


def test_gui_guidance_covers_required_annotation_editor_workflow_terms() -> None:
    text = f"{ANNOTATION_EDITOR_GUIDANCE_TEXT}\n{ANNOTATION_EDITOR_WORKFLOW_TEXT}"

    assert _missing_terms(text) == []


def test_readme_covers_annotation_editor_workflow_terms() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert _missing_terms(readme) == []
