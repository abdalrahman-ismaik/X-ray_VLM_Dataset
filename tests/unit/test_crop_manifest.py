from __future__ import annotations

from xray_curation.services.crop_generator import generate_crops_for_partition
from xray_curation.services.crop_manifest import (
    find_crop,
    query_crops,
    read_crop_manifest,
    update_crop,
)
from xray_curation.services.dataset_index import build_dataset_manifest


def _manifest(small_dataset):
    build_dataset_manifest(small_dataset, partition_size=4, persist=True)
    result = generate_crops_for_partition(small_dataset, "part-0001", partition_size=4)
    assert result.success is True
    return read_crop_manifest(small_dataset, "part-0001")


def test_crop_lookup_does_not_depend_on_filename_or_folder(small_dataset):
    manifest = _manifest(small_dataset)
    crop = manifest["crops"][0]
    crop_id = crop["crop_id"]
    crop["crop_path"] = "some/renamed/folder/renamed_crop.png"
    crop["label"] = "Moved Class Folder"

    found = find_crop(manifest, crop_id)

    assert found["crop_id"] == crop_id
    assert found["bbox_id"] == crop["bbox_id"]


def test_crop_query_filters_by_label_status_image_and_text(small_dataset):
    manifest = _manifest(small_dataset)
    update_crop(manifest, manifest["crops"][0]["crop_id"], {"status": "soft_deleted"})

    assert len(query_crops(manifest, label="Belt")) == 1
    assert len(query_crops(manifest, source_image_id="image_002")) == 1
    assert len(query_crops(manifest, status="soft_deleted")) == 1
    assert len(query_crops(manifest, text="mobile")) == 1
