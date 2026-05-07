from __future__ import annotations

from xray_curation.gui.annotation_editor import EMPTY_STATE_GUIDANCE, NO_SELECTION_GUIDANCE
from xray_curation.services.annotation_editor import load_source_image_context
from xray_curation.services.crop_manifest import crop_manifest_path
from xray_curation.services.dataset_index import build_dataset_manifest


def test_can_browse_partition_source_image_before_crop_manifest_exists(small_dataset) -> None:
    build_dataset_manifest(small_dataset, partition_size=4, persist=True)

    assert not crop_manifest_path(small_dataset, "part-0001").exists()

    context = load_source_image_context(small_dataset, "part-0001", "image_000")

    assert context.image_id == "image_000"
    assert len(context.boxes) == 1
    assert context.boxes[0].bbox_id == "bbox-e05e0ef3c3e91c9e"


def test_annotation_editor_empty_state_guidance_is_actionable() -> None:
    text = f"{EMPTY_STATE_GUIDANCE}\n{NO_SELECTION_GUIDANCE}".casefold()

    assert "index dataset" in text
    assert "select a partition" in text
    assert "source image" in text
    assert "draw box" in text
    assert "save pending" in text
