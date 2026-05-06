from __future__ import annotations

from xray_curation.services.crop_generator import generate_crops_for_partition
from xray_curation.services.crop_manifest import (
    lookup_source_context,
    query_crops,
    read_crop_manifest,
)
from xray_curation.services.dataset_index import build_dataset_manifest


def test_crop_browser_service_finds_crop_and_source_context(small_dataset):
    build_dataset_manifest(small_dataset, partition_size=4, persist=True)
    result = generate_crops_for_partition(small_dataset, "part-0001", partition_size=4)
    assert result.success is True

    manifest = read_crop_manifest(small_dataset, "part-0001")
    crops = query_crops(manifest, text="image_003")
    assert len(crops) == 1

    context = lookup_source_context(small_dataset, "part-0001", crops[0]["crop_id"])

    assert context["partition_id"] == "part-0001"
    assert context["image_id"] == "image_003"
    assert context["bbox_id"] == crops[0]["bbox_id"]
    assert context["shape"]["label"] == "Glass Bottle"
