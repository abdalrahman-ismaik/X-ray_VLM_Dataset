from __future__ import annotations

from pathlib import Path

from xray_curation.services.crop_generator import generate_crops_for_partition
from xray_curation.services.crop_manifest import (
    SOFT_DELETED_FOLDER,
    find_crop,
    find_crop_for_bbox,
    query_crops,
    read_crop_manifest,
    relocate_crop_file,
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


def test_crop_lookup_by_source_bbox(small_dataset):
    manifest = _manifest(small_dataset)
    crop = manifest["crops"][0]

    found = find_crop_for_bbox(manifest, crop["image_id"], crop["bbox_id"])

    assert found is not None
    assert found["crop_id"] == crop["crop_id"]
    assert find_crop_for_bbox(manifest, crop["image_id"], "bbox-missing") is None


def test_crop_query_filters_by_label_status_image_and_text(small_dataset):
    manifest = _manifest(small_dataset)
    update_crop(manifest, manifest["crops"][0]["crop_id"], {"status": "soft_deleted"})

    assert len(query_crops(manifest, label="Belt")) == 1
    assert len(query_crops(manifest, source_image_id="image_002")) == 1
    assert len(query_crops(manifest, status="soft_deleted")) == 1
    assert len(query_crops(manifest, text="mobile")) == 1


def test_generated_crops_are_written_under_class_folders(small_dataset):
    manifest = _manifest(small_dataset)

    for crop in manifest["crops"]:
        crop_path = Path(crop["crop_path"])
        assert crop_path.is_file()
        assert crop_path.parent.name == crop["label"]


def test_relocate_crop_file_moves_between_class_and_soft_deleted_folders(small_dataset):
    manifest = _manifest(small_dataset)
    crop = manifest["crops"][0]
    old_path = Path(crop["crop_path"])

    updates = relocate_crop_file(small_dataset, "part-0001", crop, label="Wallet", status="active")
    update_crop(manifest, crop["crop_id"], {"label": "Wallet", "status": "active", **updates})
    moved_path = Path(crop["crop_path"])

    assert moved_path.is_file()
    assert moved_path.parent.name == "Wallet"
    assert not old_path.exists()

    updates = relocate_crop_file(small_dataset, "part-0001", crop, label="Wallet", status="soft_deleted")
    update_crop(manifest, crop["crop_id"], {"status": "soft_deleted", **updates})
    deleted_path = Path(crop["crop_path"])

    assert deleted_path.is_file()
    assert deleted_path.parent.name == "Wallet"
    assert deleted_path.parent.parent.name == SOFT_DELETED_FOLDER
    assert not moved_path.exists()
