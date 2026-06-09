from __future__ import annotations

from pathlib import Path

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


def test_generate_crops_removes_unreferenced_legacy_flat_pngs(small_dataset):
    build_dataset_manifest(small_dataset, partition_size=4, persist=True)
    first = generate_crops_for_partition(small_dataset, "part-0001", partition_size=4)
    assert first.success is True

    manifest = read_crop_manifest(small_dataset, "part-0001")
    crop = manifest["crops"][0]
    current_crop_path = Path(crop["crop_path"])
    crop_root = small_dataset / "curation" / "partitions" / "part-0001" / "crops"
    legacy_flat_path = crop_root / f"{crop['crop_id']}.png"
    non_png_note = crop_root / "manual-note.txt"
    legacy_flat_path.write_bytes(current_crop_path.read_bytes())
    non_png_note.write_text("keep reviewer note", encoding="utf-8")

    result = generate_crops_for_partition(
        small_dataset,
        "part-0001",
        partition_size=4,
        overwrite=True,
    )

    assert result.success is True
    assert result.summary["orphan_crop_files_removed"] == 1
    assert result.summary["orphan_crop_bytes_removed"] > 0
    assert not legacy_flat_path.exists()
    assert non_png_note.is_file()

    refreshed_manifest = read_crop_manifest(small_dataset, "part-0001")
    for refreshed_crop in refreshed_manifest["crops"]:
        assert Path(refreshed_crop["crop_path"]).is_file()
