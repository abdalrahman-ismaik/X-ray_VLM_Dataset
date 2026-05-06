from __future__ import annotations

from pathlib import Path

from xray_curation.services.crop_generator import generate_crops_for_partition
from xray_curation.services.crop_manifest import read_crop_manifest
from xray_curation.services.dataset_index import build_dataset_manifest
from xray_curation.services.validation import (
    detect_missing_crops,
    stage_missing_crop_deletions,
)


def test_missing_crop_detection_preview_and_staged_deletions(small_dataset):
    build_dataset_manifest(small_dataset, partition_size=4, persist=True)
    result = generate_crops_for_partition(small_dataset, "part-0001", partition_size=4)
    assert result.success is True
    manifest = read_crop_manifest(small_dataset, "part-0001")
    missing_crop = manifest["crops"][0]
    missing_path = Path(missing_crop["crop_path"])
    missing_path.unlink()

    preview = detect_missing_crops(small_dataset, "part-0001")

    assert preview.success is True
    assert preview.summary["checked_count"] == 4
    assert preview.summary["missing_count"] == 1
    assert preview.affected_ids == (missing_crop["crop_id"],)

    staged_result, changes = stage_missing_crop_deletions(small_dataset, "part-0001")

    assert staged_result.success is True
    assert staged_result.summary["staged_count"] == 1
    assert [change.operation for change in changes] == ["soft_delete"]
    assert changes[0].target_id == missing_crop["crop_id"]
