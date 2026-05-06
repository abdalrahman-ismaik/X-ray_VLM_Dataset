from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DatasetPaths:
    root: Path
    images_dir: Path
    annotations_dir: Path
    curation_dir: Path


@dataclass(frozen=True)
class ImageRecord:
    image_id: str
    image_path: Path
    annotation_path: Path
    ordinal: int

    def to_manifest(self) -> dict[str, Any]:
        return {
            "image_id": self.image_id,
            "image_path": str(self.image_path),
            "annotation_path": str(self.annotation_path),
            "ordinal": self.ordinal,
        }


@dataclass(frozen=True)
class AnnotationShape:
    shape_index: int
    label: str
    points: tuple[tuple[float, float], tuple[float, float]]
    bbox_id: str
    shape_type: str = "rectangle"


@dataclass(frozen=True)
class Partition:
    partition_id: str
    index: int
    start_ordinal: int
    end_ordinal: int
    image_count: int
    image_ids: tuple[str, ...] = field(default_factory=tuple)

    def to_manifest(self) -> dict[str, Any]:
        return {
            "partition_id": self.partition_id,
            "index": self.index,
            "start_ordinal": self.start_ordinal,
            "end_ordinal": self.end_ordinal,
            "image_count": self.image_count,
            "image_ids": list(self.image_ids),
        }


@dataclass(frozen=True)
class CropRecord:
    crop_id: str
    bbox_id: str
    image_id: str
    label: str
    crop_path: Path
    source_image_path: Path
    annotation_path: Path
    status: str = "active"

    def to_manifest(self) -> dict[str, Any]:
        return {
            "crop_id": self.crop_id,
            "bbox_id": self.bbox_id,
            "image_id": self.image_id,
            "label": self.label,
            "crop_path": str(self.crop_path),
            "source_image_path": str(self.source_image_path),
            "annotation_path": str(self.annotation_path),
            "status": self.status,
        }


@dataclass(frozen=True)
class PendingChange:
    change_id: str
    target_id: str
    operation: str
    payload: dict[str, Any]
    status: str = "pending"


@dataclass(frozen=True)
class OperationResult:
    operation: str
    success: bool
    summary: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)
    affected_ids: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "success": self.success,
            "summary": self.summary,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "affected_ids": list(self.affected_ids),
        }
