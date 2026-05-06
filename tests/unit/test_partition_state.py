from __future__ import annotations

from xray_curation.services.annotation_store import load_json, save_json_atomic
from xray_curation.services.crop_generator import generate_crops_for_partition
from xray_curation.services.dataset_index import (
    build_dataset_manifest,
    detect_stale_images,
    summarize_partition_state,
)


def test_partition_state_transitions_from_not_generated_to_ready(small_dataset):
    build_dataset_manifest(small_dataset, partition_size=4, persist=True)

    before = summarize_partition_state(small_dataset, "part-0001")
    assert before["status"] == "not_generated"
    assert before["changed_image_count"] == 4

    result = generate_crops_for_partition(small_dataset, "part-0001", partition_size=4)
    assert result.success is True

    after = summarize_partition_state(small_dataset, "part-0001")
    assert after["status"] == "ready"
    assert after["changed_image_count"] == 0


def test_partition_state_becomes_stale_when_annotation_changes(small_dataset):
    build_dataset_manifest(small_dataset, partition_size=4, persist=True)
    result = generate_crops_for_partition(small_dataset, "part-0001", partition_size=4)
    assert result.success is True

    path = small_dataset / "json" / "image_000.json"
    data = load_json(path)
    data["shapes"][0]["label"] = "Wallet"
    save_json_atomic(path, data)

    stale = detect_stale_images(small_dataset, "part-0001")

    assert stale["status"] == "stale"
    assert stale["changed_image_count"] == 1
    assert stale["changed_image_ids"] == ["image_000"]
