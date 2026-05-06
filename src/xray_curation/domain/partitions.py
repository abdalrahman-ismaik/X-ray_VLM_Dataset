from __future__ import annotations

import math
from collections.abc import Sequence

from .operations import ImageRecord, Partition

PARTITION_STATUS_READY = "ready"
PARTITION_STATUS_EMPTY = "empty"


def partition_id(index: int) -> str:
    if index < 0:
        raise ValueError("Partition index must be non-negative")
    return f"part-{index + 1:04d}"


def partition_index(partition_id_value: str) -> int:
    if not partition_id_value.startswith("part-"):
        raise ValueError(f"Invalid partition id: {partition_id_value}")
    return int(partition_id_value.removeprefix("part-")) - 1


def partition_count(image_count: int, partition_size: int) -> int:
    if partition_size <= 0:
        raise ValueError("Partition size must be positive")
    if image_count <= 0:
        return 0
    return math.ceil(image_count / partition_size)


def build_partitions(
    image_records: Sequence[ImageRecord],
    partition_size: int,
) -> list[Partition]:
    count = partition_count(len(image_records), partition_size)
    partitions: list[Partition] = []
    for index in range(count):
        start = index * partition_size
        end = min(start + partition_size, len(image_records))
        records = image_records[start:end]
        partitions.append(
            Partition(
                partition_id=partition_id(index),
                index=index,
                start_ordinal=start,
                end_ordinal=end - 1,
                image_count=len(records),
                image_ids=tuple(record.image_id for record in records),
            )
        )
    return partitions
