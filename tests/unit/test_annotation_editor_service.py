from __future__ import annotations

from xray_curation.services.annotation_editor import (
    list_partition_source_images,
    load_source_image_context,
    stage_annotation_add,
    stage_annotation_delete,
    stage_annotation_relabel,
    stage_annotation_update_box,
)
from xray_curation.services.annotation_store import (
    commit_pending_changes,
    find_shape_by_bbox_id,
    load_annotation,
)
from xray_curation.services.dataset_index import build_dataset_manifest


def test_lists_source_images_from_selected_partition_without_crop_manifest(small_dataset) -> None:
    build_dataset_manifest(small_dataset, partition_size=4, persist=True)

    records = list_partition_source_images(small_dataset, "part-0001")

    assert [record.image_id for record in records] == [
        "image_000",
        "image_001",
        "image_002",
        "image_003",
    ]


def test_loads_source_context_with_supported_boxes_warnings_and_stable_ids(
    small_dataset,
    apply_annotation_editor_case,
) -> None:
    apply_annotation_editor_case(small_dataset)
    build_dataset_manifest(small_dataset, partition_size=4, persist=True)

    context = load_source_image_context(
        small_dataset,
        "part-0001",
        "image_000",
        selected_bbox_id="bbox-overlap-b",
    )

    assert context.image_id == "image_000"
    assert context.image_size == (4, 4)
    assert [box.bbox_id for box in context.boxes] == [
        "bbox-overlap-a",
        "bbox-overlap-b",
    ]
    assert context.selected_box is not None
    assert context.selected_box.bbox_id == "bbox-overlap-b"
    assert context.unsupported_shape_count == 2
    assert any("Unknown label on bbox-overlap-b" in warning for warning in context.load_warnings)
    assert any("unsupported or invalid" in warning for warning in context.load_warnings)


def test_commit_annotation_add_writes_stable_bbox_and_preserves_json_fields(small_dataset) -> None:
    build_dataset_manifest(small_dataset, partition_size=4, persist=True)
    context = load_source_image_context(small_dataset, "part-0001", "image_000")
    change = stage_annotation_add(context, (0, 1, 2, 3), "Belt")

    result = commit_pending_changes([change])

    assert result.success
    assert result.summary["annotation_add_count"] == 1
    assert result.affected_ids == (change.payload["temporary_bbox_id"],)

    annotation = load_annotation(
        small_dataset / "json" / "image_000.json",
        image_id="image_000",
        assign_ids=False,
    )
    assert annotation["fixture_meta"] == "preserve"
    added = annotation["shapes"][-1]
    assert added["label"] == "Belt"
    assert added["shape_type"] == "rectangle"
    assert added["points"] == [[0, 1], [2, 3]]
    assert added["flags"]["curation_bbox_id"] == change.payload["temporary_bbox_id"]


def test_commit_annotation_edits_preserves_unsupported_shapes_and_unrelated_fields(
    small_dataset,
    apply_annotation_editor_case,
) -> None:
    apply_annotation_editor_case(small_dataset)
    build_dataset_manifest(small_dataset, partition_size=4, persist=True)
    context = load_source_image_context(small_dataset, "part-0001", "image_000")
    update = stage_annotation_update_box(context, "bbox-overlap-a", (0, 1, 3, 3))
    relabel_context = load_source_image_context(small_dataset, "part-0001", "image_000")
    relabel = stage_annotation_relabel(relabel_context, "bbox-overlap-a", "Belt")

    result = commit_pending_changes([update, relabel])

    assert result.success
    assert result.summary["annotation_update_box_count"] == 1
    assert result.summary["annotation_relabel_count"] == 1
    annotation = load_annotation(
        small_dataset / "json" / "image_000.json",
        image_id="image_000",
        assign_ids=False,
    )
    edited = find_shape_by_bbox_id(annotation, "image_000", "bbox-overlap-a")
    assert annotation["fixture_meta"] == "preserve"
    assert edited["label"] == "Belt"
    assert edited["points"] == [[0, 1], [3, 3]]
    assert edited["flags"]["curation_bbox_id"] == "bbox-overlap-a"
    assert any(shape.get("shape_type") == "polygon" for shape in annotation["shapes"])
    assert any(shape.get("flags", {}).get("curation_bbox_id") == "bbox-invalid-zero-width" for shape in annotation["shapes"])


def test_commit_annotation_delete_preserves_other_bbox_identity(
    small_dataset,
    apply_annotation_editor_case,
) -> None:
    apply_annotation_editor_case(small_dataset)
    build_dataset_manifest(small_dataset, partition_size=4, persist=True)
    context = load_source_image_context(small_dataset, "part-0001", "image_000")
    delete = stage_annotation_delete(context, "bbox-overlap-b")

    result = commit_pending_changes([delete])

    assert result.success
    assert result.summary["annotation_delete_count"] == 1
    annotation = load_annotation(
        small_dataset / "json" / "image_000.json",
        image_id="image_000",
        assign_ids=False,
    )
    assert find_shape_by_bbox_id(annotation, "image_000", "bbox-overlap-b") is None
    assert find_shape_by_bbox_id(annotation, "image_000", "bbox-overlap-a") is not None
