from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATASET_NAME = "dataset"
DEFAULT_PARTITION_SIZE = 10_000


@dataclass(frozen=True)
class DatasetConfig:
    root: Path
    images_dir: Path
    annotations_dir: Path
    curation_dir: Path
    partition_size: int = DEFAULT_PARTITION_SIZE

    @classmethod
    def from_root(
        cls,
        root: str | Path,
        partition_size: int = DEFAULT_PARTITION_SIZE,
    ) -> "DatasetConfig":
        dataset_root = Path(root).resolve()
        return cls(
            root=dataset_root,
            images_dir=dataset_root / "images",
            annotations_dir=dataset_root / "json",
            curation_dir=dataset_root / "curation",
            partition_size=partition_size,
        )


def default_dataset_root(project_root: str | Path | None = None) -> Path:
    base = Path(project_root) if project_root is not None else Path.cwd()
    return base / DEFAULT_DATASET_NAME
