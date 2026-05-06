from __future__ import annotations

from xray_curation.services.annotation_store import load_json, save_json_atomic
from xray_curation.services.crop_generator import (
    generate_crops_for_partition,
    refresh_changed_crops_for_partition,
)
from xray_curation.services.crop_manifest import read_crop_manifest
from xray_curation.services.dataset_index import (
    build_dataset_manifest,
    summarize_partition_state,
)
from xray_curation.services.validation import read_operation_log


def test_resume_and_refresh_changed_only_processes_stale_fixture_image(small_dataset):
    build_dataset_manifest(small_dataset, partition_size=4, persist=True)
    generated = generate_crops_for_partition(small_dataset, "part-0001", partition_size=4)
    assert generated.success is True

    ready = summarize_partition_state(small_dataset, "part-0001")
    assert ready["status"] == "ready"
    assert ready["changed_image_count"] == 0

    path = small_dataset / "json" / "image_000.json"
    data = load_json(path)
    data["shapes"][0]["label"] = "Wallet"
    save_json_atomic(path, data)

    stale = summarize_partition_state(small_dataset, "part-0001")
    assert stale["status"] == "stale"
    assert stale["changed_image_ids"] == ["image_000"]

    refreshed = refresh_changed_crops_for_partition(small_dataset, "part-0001", partition_size=4)

    assert refreshed.success is True
    assert refreshed.summary["changed_image_count"] == 1
    assert refreshed.summary["images_processed"] == 1

    manifest = read_crop_manifest(small_dataset, "part-0001")
    assert len(manifest["crops"]) == 4
    refreshed_crop = next(crop for crop in manifest["crops"] if crop["image_id"] == "image_000")
    untouched_crop = next(crop for crop in manifest["crops"] if crop["image_id"] == "image_001")
    assert refreshed_crop["label"] == "Wallet"
    assert untouched_crop["label"] == "Belt"

    resumed = summarize_partition_state(small_dataset, "part-0001")
    assert resumed["status"] == "ready"
    assert resumed["changed_image_count"] == 0

    operations = [entry["operation"] for entry in read_operation_log(small_dataset)]
    assert operations[-2:] == ["generate_crops", "refresh_changed_crops"]
