from __future__ import annotations

from xray_curation.services.annotation_editor import load_source_image_context, stage_annotation_relabel
from xray_curation.services.annotation_store import commit_pending_changes
from xray_curation.services.crop_generator import generate_crops_for_partition, refresh_affected_image_crops
from xray_curation.services.crop_manifest import crop_manifest_path, query_crops, read_crop_manifest
from xray_curation.services.dataset_index import build_dataset_manifest, detect_stale_images


def test_selected_partition_state_detection_uses_fixture_scope_only(small_dataset) -> None:
    build_dataset_manifest(small_dataset, partition_size=4, persist=True)

    state = detect_stale_images(small_dataset, "part-0001")

    assert state["partition_id"] == "part-0001"
    assert state["image_count"] == 4
    assert state["status"] == "not_generated"


def test_refresh_affected_image_crops_updates_only_named_images(small_dataset) -> None:
    build_dataset_manifest(small_dataset, partition_size=3, persist=True)
    generate_crops_for_partition(small_dataset, "part-0001", partition_size=3)
    before_manifest = read_crop_manifest(small_dataset, "part-0001")
    before_other = [
        crop["crop_id"]
        for crop in query_crops(before_manifest)
        if crop["image_id"] != "image_000"
    ]
    context = load_source_image_context(small_dataset, "part-0001", "image_000")
    commit_pending_changes([stage_annotation_relabel(context, context.boxes[0].bbox_id, "Wallet")])

    result = refresh_affected_image_crops(
        small_dataset,
        "part-0001",
        ["image_000"],
        partition_size=3,
    )

    manifest = read_crop_manifest(small_dataset, "part-0001")
    image_000_crops = [crop for crop in query_crops(manifest) if crop["image_id"] == "image_000"]
    other_crops = [
        crop["crop_id"]
        for crop in query_crops(manifest)
        if crop["image_id"] != "image_000"
    ]
    assert result.success
    assert result.summary["refreshed_image_count"] == 1
    assert result.summary["skipped_image_count"] == 0
    assert result.summary["images_processed"] == 1
    assert image_000_crops[0]["label"] == "Wallet"
    assert other_crops == before_other


def test_refresh_affected_image_crops_skips_when_crop_manifest_missing(small_dataset) -> None:
    build_dataset_manifest(small_dataset, partition_size=3, persist=True)

    result = refresh_affected_image_crops(
        small_dataset,
        "part-0001",
        ["image_000"],
        partition_size=3,
    )

    assert result.success
    assert result.summary["refreshed_image_count"] == 0
    assert result.summary["skipped_image_count"] == 1
    assert not crop_manifest_path(small_dataset, "part-0001").exists()
