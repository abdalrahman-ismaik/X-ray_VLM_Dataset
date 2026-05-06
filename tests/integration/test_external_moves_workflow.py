from __future__ import annotations

import shutil

from xray_curation.services.annotation_store import load_json
from xray_curation.services.crop_generator import generate_crops_for_partition
from xray_curation.services.crop_manifest import (
    apply_external_moves,
    preview_external_moves,
    read_crop_manifest,
)
from xray_curation.services.dataset_index import build_dataset_manifest


def test_external_moved_crop_preview_and_apply(small_dataset, tmp_path):
    build_dataset_manifest(small_dataset, partition_size=4, persist=True)
    result = generate_crops_for_partition(small_dataset, "part-0001", partition_size=4)
    assert result.success is True
    manifest = read_crop_manifest(small_dataset, "part-0001")
    crop = manifest["crops"][1]

    external_root = tmp_path / "external_moves"
    target_folder = external_root / "Laptop"
    target_folder.mkdir(parents=True)
    moved_crop_path = target_folder / f"{crop['crop_id']}.png"
    shutil.copy2(crop["crop_path"], moved_crop_path)

    preview = preview_external_moves(small_dataset, "part-0001", external_root)

    assert preview.success is True
    assert preview.summary["moves_found"] == 1
    assert preview.summary["moves"][0]["crop_id"] == crop["crop_id"]
    assert preview.summary["moves"][0]["to_label"] == "Laptop"

    applied = apply_external_moves(small_dataset, "part-0001", external_root)

    assert applied.success is True
    assert applied.summary["moves_applied"] == 1

    updated_manifest = read_crop_manifest(small_dataset, "part-0001")
    updated_crop = next(item for item in updated_manifest["crops"] if item["crop_id"] == crop["crop_id"])
    assert updated_crop["label"] == "Laptop"

    annotation = load_json(crop["annotation_path"])
    assert annotation["shapes"][0]["label"] == "Laptop"
