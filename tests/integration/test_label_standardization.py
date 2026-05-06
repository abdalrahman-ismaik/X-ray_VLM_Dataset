from __future__ import annotations

from xray_curation.services.annotation_store import load_json, save_json_atomic
from xray_curation.services.crop_generator import generate_crops_for_partition
from xray_curation.services.crop_manifest import read_crop_manifest
from xray_curation.services.dataset_index import build_dataset_manifest
from xray_curation.services.label_standardizer import (
    apply_label_standardization_for_partition,
    preview_label_standardization_for_partition,
)


def test_label_standardization_preview_and_apply_selected_partition(small_dataset):
    build_dataset_manifest(small_dataset, partition_size=4, persist=True)
    result = generate_crops_for_partition(small_dataset, "part-0001", partition_size=4)
    assert result.success is True

    standardize_path = small_dataset / "json" / "image_000.json"
    unknown_path = small_dataset / "json" / "image_001.json"
    standardize_data = load_json(standardize_path)
    unknown_data = load_json(unknown_path)
    standardize_data["shapes"][0]["label"] = "Electrical_Device"
    unknown_data["shapes"][0]["label"] = "mystery_object"
    save_json_atomic(standardize_path, standardize_data)
    save_json_atomic(unknown_path, unknown_data)

    preview = preview_label_standardization_for_partition(small_dataset, "part-0001")

    assert preview.success is True
    assert preview.summary["checked_count"] == 4
    assert preview.summary["proposed_count"] == 1
    assert preview.summary["unknown_count"] == 1
    assert preview.summary["proposals"][0]["target_label"] == "Electrical Device"
    assert preview.summary["unknowns"][0]["current_label"] == "mystery_object"

    applied = apply_label_standardization_for_partition(small_dataset, "part-0001")

    assert applied.success is True
    assert applied.summary["labels_updated"] == 1
    assert applied.summary["unknown_count"] == 1

    reloaded_standardized = load_json(standardize_path)
    reloaded_unknown = load_json(unknown_path)
    assert reloaded_standardized["shapes"][0]["label"] == "Electrical Device"
    assert reloaded_unknown["shapes"][0]["label"] == "mystery_object"

    manifest = read_crop_manifest(small_dataset, "part-0001")
    crop = next(item for item in manifest["crops"] if item["image_id"] == "image_000")
    assert crop["label"] == "Electrical Device"
