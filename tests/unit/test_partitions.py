from __future__ import annotations

from pathlib import Path

from xray_curation.domain.operations import ImageRecord
from xray_curation.domain.partitions import build_partitions


def _records(count: int) -> list[ImageRecord]:
    return [
        ImageRecord(
            image_id=f"image_{index:05d}",
            image_path=Path(f"image_{index:05d}.ppm"),
            annotation_path=Path(f"image_{index:05d}.json"),
            ordinal=index,
        )
        for index in range(count)
    ]


def test_partition_assignment_is_deterministic():
    first = build_partitions(_records(6), partition_size=4)
    second = build_partitions(_records(6), partition_size=4)

    assert first == second
    assert first[0].partition_id == "part-0001"
    assert first[0].image_ids == ("image_00000", "image_00001", "image_00002", "image_00003")


def test_final_partition_can_be_short():
    partitions = build_partitions(_records(10_001), partition_size=10_000)

    assert len(partitions) == 2
    assert partitions[0].image_count == 10_000
    assert partitions[1].partition_id == "part-0002"
    assert partitions[1].image_count == 1
