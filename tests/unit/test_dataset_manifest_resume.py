from __future__ import annotations

import pytest

from xray_curation.gui.app import (
    partition_size_from_manifest,
    partition_values_from_manifest,
)
from xray_curation.services import dataset_index


def test_existing_dataset_manifest_load_does_not_scan_images(monkeypatch, small_dataset) -> None:
    dataset_index.build_dataset_manifest(small_dataset, partition_size=4, persist=True)

    def fail_if_scanned(*_args, **_kwargs):
        raise AssertionError("existing manifest load should not list image files")

    monkeypatch.setattr(dataset_index, "list_image_records", fail_if_scanned)

    manifest = dataset_index.load_or_create_dataset_manifest(
        small_dataset,
        partition_size=10_000,
    )

    assert manifest["image_count"] == 6
    assert manifest["partition_size"] == 4
    assert [item["partition_id"] for item in manifest["partitions"]] == [
        "part-0001",
        "part-0002",
    ]


def test_partition_dropdown_values_and_size_come_from_saved_manifest() -> None:
    manifest = {
        "partition_size": 4,
        "partitions": [
            {"partition_id": "part-0001", "image_count": 4},
            {"partition_id": "part-0002", "image_count": 2},
        ],
    }

    assert partition_values_from_manifest(manifest) == [
        "part-0001 (4 images)",
        "part-0002 (2 images)",
    ]
    assert partition_size_from_manifest(manifest) == 4


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, 10_000),
        ("bad", 10_000),
        (0, 10_000),
        (-1, 10_000),
        ("12", 12),
    ],
)
def test_partition_size_from_manifest_uses_safe_fallback(value, expected) -> None:
    assert partition_size_from_manifest({"partition_size": value}) == expected
