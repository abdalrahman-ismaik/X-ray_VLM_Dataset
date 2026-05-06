from __future__ import annotations

from xray_curation.services.crop_generator import generate_crops_for_partition
from xray_curation.services.crop_manifest import read_crop_manifest
from xray_curation.services.dataset_index import build_dataset_manifest


def test_generates_crops_only_for_selected_partition(small_dataset):
    build_dataset_manifest(small_dataset, partition_size=4, persist=True)

    result = generate_crops_for_partition(small_dataset, "part-0001", partition_size=4)

    assert result.success is True
    assert result.summary["images_seen"] == 4
    assert result.summary["images_processed"] == 4
    assert result.summary["crops_total"] == 4

    manifest = read_crop_manifest(small_dataset, "part-0001")
    assert {crop["image_id"] for crop in manifest["crops"]} == {
        "image_000",
        "image_001",
        "image_002",
        "image_003",
    }
    assert not (small_dataset / "curation" / "partitions" / "part-0002" / "crops").exists()
