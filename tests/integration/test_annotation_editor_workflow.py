from __future__ import annotations

from xray_curation.services.annotation_editor import (
    load_source_image_context,
    stage_annotation_add,
    stage_annotation_delete,
    stage_annotation_relabel,
    stage_annotation_update_box,
)
from xray_curation.services.annotation_store import commit_pending_changes, stage_relabel_change
from xray_curation.services.annotation_editor import load_source_context_for_crop
from xray_curation.services.crop_generator import generate_crops_for_partition, refresh_affected_image_crops
from xray_curation.services.crop_manifest import query_crops, read_crop_manifest
from xray_curation.services.dataset_index import build_dataset_manifest


def test_crop_selection_loads_matching_source_bbox_context(small_dataset) -> None:
    build_dataset_manifest(small_dataset, partition_size=3, persist=True)
    result = generate_crops_for_partition(small_dataset, "part-0001", partition_size=3)
    assert result.summary["images_seen"] == 3

    manifest = read_crop_manifest(small_dataset, "part-0001")
    crop = next(crop for crop in query_crops(manifest) if crop["image_id"] == "image_000")

    context = load_source_context_for_crop(small_dataset, "part-0001", crop["crop_id"])

    assert context.image_id == "image_000"
    assert context.selected_bbox_id == crop["bbox_id"]
    assert context.selected_box is not None
    assert context.selected_box.bbox_id == crop["bbox_id"]


def test_draw_label_save_path_preserves_original_image_bytes(small_dataset) -> None:
    build_dataset_manifest(small_dataset, partition_size=4, persist=True)
    image_path = small_dataset / "images" / "image_000.ppm"
    before_image = image_path.read_bytes()
    context = load_source_image_context(small_dataset, "part-0001", "image_000")
    change = stage_annotation_add(context, (0, 1, 2, 3), "Wallet")

    result = commit_pending_changes([change])
    reloaded = load_source_image_context(
        small_dataset,
        "part-0001",
        "image_000",
        selected_bbox_id=change.payload["temporary_bbox_id"],
    )

    assert result.success
    assert image_path.read_bytes() == before_image
    assert reloaded.selected_box is not None
    assert reloaded.selected_box.label == "Wallet"


def test_mixed_crop_correction_and_annotation_edit_refreshes_affected_image(small_dataset) -> None:
    build_dataset_manifest(small_dataset, partition_size=3, persist=True)
    generate_crops_for_partition(small_dataset, "part-0001", partition_size=3)
    manifest = read_crop_manifest(small_dataset, "part-0001")
    crop = next(crop for crop in query_crops(manifest) if crop["image_id"] == "image_000")
    context = load_source_image_context(small_dataset, "part-0001", "image_000")
    changes = [
        stage_relabel_change(crop, "Belt"),
        stage_annotation_update_box(context, crop["bbox_id"], (0, 1, 2, 3)),
    ]

    commit = commit_pending_changes(changes)
    refresh = refresh_affected_image_crops(
        small_dataset,
        "part-0001",
        ["image_000"],
        partition_size=3,
    )

    manifest = read_crop_manifest(small_dataset, "part-0001")
    refreshed_crop = next(crop for crop in query_crops(manifest) if crop["image_id"] == "image_000")
    reloaded = load_source_image_context(small_dataset, "part-0001", "image_000")
    assert commit.success
    assert refresh.success
    assert refresh.summary["refreshed_image_count"] == 1
    assert refreshed_crop["label"] == "Belt"
    assert reloaded.boxes[0].points == (0, 1, 2, 3)


def test_move_relabel_delete_save_refresh_sequence(small_dataset) -> None:
    build_dataset_manifest(small_dataset, partition_size=3, persist=True)
    generate_crops_for_partition(small_dataset, "part-0001", partition_size=3)
    context = load_source_image_context(small_dataset, "part-0001", "image_000")
    bbox_id = context.boxes[0].bbox_id

    update = commit_pending_changes([stage_annotation_update_box(context, bbox_id, (0, 1, 2, 3))])
    refresh_update = refresh_affected_image_crops(small_dataset, "part-0001", ["image_000"], partition_size=3)
    relabel_context = load_source_image_context(small_dataset, "part-0001", "image_000")
    relabel = commit_pending_changes([stage_annotation_relabel(relabel_context, bbox_id, "Umbrella")])
    refresh_relabel = refresh_affected_image_crops(small_dataset, "part-0001", ["image_000"], partition_size=3)
    delete_context = load_source_image_context(small_dataset, "part-0001", "image_000")
    delete = commit_pending_changes([stage_annotation_delete(delete_context, bbox_id)])
    refresh_delete = refresh_affected_image_crops(small_dataset, "part-0001", ["image_000"], partition_size=3)

    manifest = read_crop_manifest(small_dataset, "part-0001")
    assert update.success and relabel.success and delete.success
    assert refresh_update.summary["refreshed_image_count"] == 1
    assert refresh_relabel.summary["refreshed_image_count"] == 1
    assert refresh_delete.summary["refreshed_image_count"] == 1
    assert not [crop for crop in query_crops(manifest) if crop["image_id"] == "image_000"]
