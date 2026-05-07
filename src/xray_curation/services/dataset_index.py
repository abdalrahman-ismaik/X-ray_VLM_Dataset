from __future__ import annotations

from pathlib import Path
from typing import Any

from xray_curation.config import DEFAULT_PARTITION_SIZE, DatasetConfig
from xray_curation.domain.operations import ImageRecord
from xray_curation.domain.partitions import build_partitions, partition_index
from xray_curation.services.annotation_store import load_json, save_json_atomic

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".ppm"}
MANIFEST_VERSION = 1
PARTITION_STATE_VERSION = 1


def dataset_manifest_path(dataset_root: str | Path) -> Path:
    return DatasetConfig.from_root(dataset_root).curation_dir / "dataset_manifest.json"


def partition_dir(dataset_root: str | Path, partition_id: str) -> Path:
    return DatasetConfig.from_root(dataset_root).curation_dir / "partitions" / partition_id


def partition_manifest_path(dataset_root: str | Path, partition_id: str) -> Path:
    return partition_dir(dataset_root, partition_id) / "partition.json"


def partition_state_path(dataset_root: str | Path, partition_id: str) -> Path:
    return partition_dir(dataset_root, partition_id) / "state.json"


def image_id_from_path(path: Path) -> str:
    return path.stem


def list_image_records(
    images_dir: str | Path,
    annotations_dir: str | Path,
) -> list[ImageRecord]:
    image_root = Path(images_dir)
    annotation_root = Path(annotations_dir)
    image_paths = sorted(
        path
        for path in image_root.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    records: list[ImageRecord] = []
    for ordinal, image_path in enumerate(image_paths):
        image_id = image_id_from_path(image_path)
        records.append(
            ImageRecord(
                image_id=image_id,
                image_path=image_path.resolve(),
                annotation_path=(annotation_root / f"{image_id}.json").resolve(),
                ordinal=ordinal,
            )
        )
    return records


def build_dataset_manifest(
    dataset_root: str | Path,
    partition_size: int = DEFAULT_PARTITION_SIZE,
    image_records: list[ImageRecord] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    config = DatasetConfig.from_root(dataset_root, partition_size=partition_size)
    records = image_records or list_image_records(config.images_dir, config.annotations_dir)
    partitions = build_partitions(records, partition_size)
    manifest = {
        "version": MANIFEST_VERSION,
        "dataset_root": str(config.root),
        "partition_size": partition_size,
        "image_count": len(records),
        "images": [record.to_manifest() for record in records],
        "partitions": [partition.to_manifest() for partition in partitions],
    }
    if persist:
        config.curation_dir.mkdir(parents=True, exist_ok=True)
        save_json_atomic(dataset_manifest_path(config.root), manifest)
        for partition in partitions:
            images = records[partition.start_ordinal : partition.end_ordinal + 1]
            payload = {
                **partition.to_manifest(),
                "images": [record.to_manifest() for record in images],
            }
            save_json_atomic(partition_manifest_path(config.root, partition.partition_id), payload)
    return manifest


def read_dataset_manifest(dataset_root: str | Path) -> dict[str, Any]:
    return load_json(dataset_manifest_path(dataset_root))


def read_partition_manifest(dataset_root: str | Path, partition_id: str) -> dict[str, Any]:
    return load_json(partition_manifest_path(dataset_root, partition_id))


def load_or_create_dataset_manifest(
    dataset_root: str | Path,
    partition_size: int = DEFAULT_PARTITION_SIZE,
) -> dict[str, Any]:
    path = dataset_manifest_path(dataset_root)
    if path.exists():
        return load_json(path)
    return build_dataset_manifest(dataset_root, partition_size=partition_size, persist=True)


def select_partition(
    manifest: dict[str, Any],
    partition_id_value: str,
) -> dict[str, Any]:
    index = partition_index(partition_id_value)
    partitions = manifest.get("partitions", [])
    if index < 0 or index >= len(partitions):
        raise ValueError(f"Partition not found: {partition_id_value}")
    partition = partitions[index]
    start = int(partition["start_ordinal"])
    end = int(partition["end_ordinal"])
    images = manifest.get("images", [])[start : end + 1]
    return {
        **partition,
        "images": images,
    }


def image_record_from_manifest(payload: dict[str, Any]) -> ImageRecord:
    return ImageRecord(
        image_id=str(payload["image_id"]),
        image_path=Path(str(payload["image_path"])),
        annotation_path=Path(str(payload["annotation_path"])),
        ordinal=int(payload.get("ordinal", 0)),
    )


def list_partition_image_records(
    dataset_root: str | Path,
    partition_id: str,
) -> list[ImageRecord]:
    partition_path = partition_manifest_path(dataset_root, partition_id)
    if partition_path.exists():
        partition = load_json(partition_path)
    else:
        partition = select_partition(read_dataset_manifest(dataset_root), partition_id)
    images = partition.get("images", [])
    if not isinstance(images, list):
        raise ValueError(f"Partition images must be a list: {partition_id}")
    return [
        image_record_from_manifest(image)
        for image in images
        if isinstance(image, dict)
    ]


def annotation_signature(annotation_path: str | Path) -> dict[str, Any]:
    path = Path(annotation_path)
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "mtime_ns": None,
            "size": None,
        }
    stat = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "mtime_ns": stat.st_mtime_ns,
        "size": stat.st_size,
    }


def partition_annotation_signatures(partition: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(image["image_id"]): annotation_signature(image["annotation_path"])
        for image in partition.get("images", [])
    }


def load_partition_state(dataset_root: str | Path, partition_id: str) -> dict[str, Any]:
    path = partition_state_path(dataset_root, partition_id)
    if not path.exists():
        return {
            "version": PARTITION_STATE_VERSION,
            "partition_id": partition_id,
            "status": "not_generated",
            "summary": {},
            "annotation_signatures": {},
        }
    return load_json(path)


def write_partition_state(
    dataset_root: str | Path,
    partition_id: str,
    state: dict[str, Any],
) -> Path:
    path = partition_state_path(dataset_root, partition_id)
    save_json_atomic(path, state)
    return path


def update_partition_state(
    dataset_root: str | Path,
    partition_id: str,
    status: str,
    summary: dict[str, Any],
) -> dict[str, Any]:
    manifest = read_dataset_manifest(dataset_root)
    partition = select_partition(manifest, partition_id)
    state = {
        "version": PARTITION_STATE_VERSION,
        "partition_id": partition_id,
        "status": status,
        "summary": summary,
        "annotation_signatures": partition_annotation_signatures(partition),
    }
    write_partition_state(dataset_root, partition_id, state)
    return state


def detect_stale_images(dataset_root: str | Path, partition_id: str) -> dict[str, Any]:
    manifest = read_dataset_manifest(dataset_root)
    partition = select_partition(manifest, partition_id)
    state = load_partition_state(dataset_root, partition_id)
    previous = state.get("annotation_signatures", {})
    current = partition_annotation_signatures(partition)
    changed_ids = [
        image_id
        for image_id, signature in current.items()
        if previous.get(image_id) != signature
    ]
    if state.get("status") == "not_generated" and not previous:
        status = "not_generated"
    elif changed_ids:
        status = "stale"
    else:
        status = state.get("status", "ready")
    return {
        "partition_id": partition_id,
        "status": status,
        "image_count": len(current),
        "changed_image_count": len(changed_ids),
        "changed_image_ids": changed_ids,
        "previous_status": state.get("status", "not_generated"),
        "annotation_signatures": current,
    }


def summarize_partition_state(dataset_root: str | Path, partition_id: str) -> dict[str, Any]:
    try:
        stale = detect_stale_images(dataset_root, partition_id)
    except Exception as exc:
        return {
            "partition_id": partition_id,
            "status": "error",
            "error": str(exc),
        }
    return stale
