from __future__ import annotations

from pathlib import Path

from xray_curation.domain.operations import ImageRecord
from xray_curation.services.dataset_index import build_dataset_manifest


def test_synthetic_10001_image_manifest_without_real_files(tmp_path):
    records = [
        ImageRecord(
            image_id=f"synthetic_{index:05d}",
            image_path=Path(f"synthetic_{index:05d}.png"),
            annotation_path=Path(f"synthetic_{index:05d}.json"),
            ordinal=index,
        )
        for index in range(10_001)
    ]

    manifest = build_dataset_manifest(
        tmp_path / "synthetic_batch",
        partition_size=10_000,
        image_records=records,
        persist=False,
    )

    assert manifest["image_count"] == 10_001
    assert [partition["image_count"] for partition in manifest["partitions"]] == [10_000, 1]
    assert not (tmp_path / "synthetic_batch" / "curation").exists()
