from __future__ import annotations

from xray_curation.domain.operations import (
    ANNOTATION_ADD,
    ANNOTATION_DELETE,
    ANNOTATION_RELABEL,
    ANNOTATION_UPDATE_BOX,
    PendingChange,
)
from xray_curation.services.annotation_editor import (
    load_source_image_context,
    stage_annotation_add,
    stage_annotation_delete,
    stage_annotation_relabel,
    stage_annotation_update_box,
    validate_new_box_label,
)
from xray_curation.services.annotation_store import cancel_pending_change
from xray_curation.services.dataset_index import build_dataset_manifest
from xray_curation.services.validation import (
    summarize_pending_changes,
    validate_pending_change_conflicts,
)


def test_pending_summary_groups_annotation_and_crop_operations() -> None:
    changes = [
        PendingChange(
            change_id="annotation_relabel:image_000:bbox-a",
            target_id="bbox-a",
            operation=ANNOTATION_RELABEL,
            payload={"image_id": "image_000", "bbox_id": "bbox-a", "label": "Backpack"},
        ),
        PendingChange(
            change_id="relabel:crop-a",
            target_id="crop-a",
            operation="relabel",
            payload={"label": "Belt"},
        ),
    ]

    summary = summarize_pending_changes(changes)

    assert summary["total"] == 2
    assert summary["annotation_edit_count"] == 1
    assert summary["crop_edit_count"] == 1
    assert summary["by_operation"][ANNOTATION_RELABEL] == 1
    assert summary["by_operation"]["relabel"] == 1


def test_conflicting_annotation_edits_for_same_bbox_are_reported() -> None:
    changes = [
        PendingChange(
            change_id="annotation_relabel:image_000:bbox-a",
            target_id="bbox-a",
            operation=ANNOTATION_RELABEL,
            payload={"image_id": "image_000", "bbox_id": "bbox-a", "label": "Backpack"},
        ),
        PendingChange(
            change_id="annotation_delete:image_000:bbox-a",
            target_id="bbox-a",
            operation=ANNOTATION_DELETE,
            payload={"image_id": "image_000", "bbox_id": "bbox-a"},
        ),
    ]

    result = validate_pending_change_conflicts(changes)

    assert not result.success
    assert result.summary["conflict_count"] == 1
    assert "image_000:bbox-a" in result.summary["conflicts"]


def test_new_annotation_label_must_be_approved_pidray_label() -> None:
    assert validate_new_box_label("Backpack") == "Backpack"

    try:
        validate_new_box_label("Electrical_Device")
    except ValueError as exc:
        assert "approved PIDRay" in str(exc)
    else:
        raise AssertionError("Expected invalid label to be rejected")


def test_stage_annotation_add_does_not_write_json(small_dataset) -> None:
    build_dataset_manifest(small_dataset, partition_size=4, persist=True)
    annotation_path = small_dataset / "json" / "image_000.json"
    before = annotation_path.read_bytes()
    context = load_source_image_context(small_dataset, "part-0001", "image_000")

    change = stage_annotation_add(context, (0, 1, 2, 3), "Backpack")

    assert annotation_path.read_bytes() == before
    assert change.operation == ANNOTATION_ADD
    assert change.payload["image_id"] == "image_000"
    assert change.payload["label"] == "Backpack"
    assert change.payload["points"] == (0, 1, 2, 3)
    assert change.target_id == change.payload["temporary_bbox_id"]


def test_stage_existing_box_update_relabel_delete_and_cancel(small_dataset) -> None:
    build_dataset_manifest(small_dataset, partition_size=4, persist=True)
    context = load_source_image_context(small_dataset, "part-0001", "image_000")
    box = context.boxes[0]

    update = stage_annotation_update_box(context, box.bbox_id, (0, 1, 2, 3))
    relabel = stage_annotation_relabel(context, box.bbox_id, "Belt")
    delete = stage_annotation_delete(context, box.bbox_id)
    remaining = cancel_pending_change([update, relabel, delete], delete.change_id)

    assert update.operation == ANNOTATION_UPDATE_BOX
    assert update.payload["bbox_id"] == box.bbox_id
    assert update.payload["previous_points"] == box.points
    assert update.payload["points"] == (0, 1, 2, 3)
    assert relabel.operation == ANNOTATION_RELABEL
    assert relabel.payload["previous_label"] == box.label
    assert delete.operation == ANNOTATION_DELETE
    assert delete.payload["previous_points"] == box.points
    assert [change.change_id for change in remaining] == [update.change_id, relabel.change_id]


def test_conflicting_update_and_delete_for_same_bbox_are_reported(small_dataset) -> None:
    build_dataset_manifest(small_dataset, partition_size=4, persist=True)
    context = load_source_image_context(small_dataset, "part-0001", "image_000")
    box = context.boxes[0]
    changes = [
        stage_annotation_update_box(context, box.bbox_id, (0, 1, 2, 3)),
        stage_annotation_delete(context, box.bbox_id),
    ]

    result = validate_pending_change_conflicts(changes)

    assert not result.success
    assert result.summary["conflict_count"] == 1
