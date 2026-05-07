from __future__ import annotations

from pathlib import Path
import re
import shutil
from typing import Any

from xray_curation.domain.operations import CropRecord, OperationResult
from xray_curation.services.annotation_store import (
    commit_pending_changes,
    find_shape_by_bbox_id,
    load_annotation,
    load_json,
    save_json_atomic,
    stage_move_group_change,
)
from xray_curation.services.dataset_index import partition_dir

CROP_MANIFEST_VERSION = 1
SOFT_DELETED_FOLDER = "_soft_deleted"


class CropManifestError(RuntimeError):
    pass


def class_folder_name(label: str | None) -> str:
    name = re.sub(r'[<>:"/\\|?*]', " ", str(label or "").strip())
    name = re.sub(r"\s+", " ", name).strip()
    return name or "_unlabeled"


def crop_file_path(
    crop_dir: str | Path,
    label: str | None,
    crop_id: str,
    status: str = "active",
) -> Path:
    root = Path(crop_dir)
    class_folder = class_folder_name(label)
    if status == "soft_deleted":
        return root / SOFT_DELETED_FOLDER / class_folder / f"{crop_id}.png"
    return root / class_folder / f"{crop_id}.png"


def crop_manifest_path(dataset_root: str | Path, partition_id: str) -> Path:
    return partition_dir(dataset_root, partition_id) / "crop_manifest.json"


def crop_root_dir(dataset_root: str | Path, partition_id: str) -> Path:
    return partition_dir(dataset_root, partition_id) / "crops"


def build_crop_manifest(
    partition_id: str,
    crop_records: list[CropRecord],
    summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "version": CROP_MANIFEST_VERSION,
        "partition_id": partition_id,
        "summary": summary,
        "crops": [record.to_manifest() for record in crop_records],
    }


def write_crop_manifest(
    dataset_root: str | Path,
    partition_id: str,
    manifest: dict[str, Any],
) -> Path:
    path = crop_manifest_path(dataset_root, partition_id)
    save_json_atomic(path, manifest)
    return path


def read_crop_manifest(dataset_root: str | Path, partition_id: str) -> dict[str, Any]:
    return load_json(crop_manifest_path(dataset_root, partition_id))


def crop_records(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    crops = manifest.get("crops", [])
    if not isinstance(crops, list):
        raise CropManifestError("Crop manifest 'crops' field must be a list")
    return [crop for crop in crops if isinstance(crop, dict)]


def find_crop(manifest: dict[str, Any], crop_id: str) -> dict[str, Any]:
    for crop in crop_records(manifest):
        if crop.get("crop_id") == crop_id:
            return crop
    raise CropManifestError(f"Crop not found: {crop_id}")


def find_crop_for_bbox(
    manifest: dict[str, Any],
    image_id: str,
    bbox_id: str,
) -> dict[str, Any] | None:
    for crop in crop_records(manifest):
        if str(crop.get("image_id")) == image_id and str(crop.get("bbox_id")) == bbox_id:
            return crop
    return None


def query_crops(
    manifest: dict[str, Any],
    label: str | None = None,
    source_image_id: str | None = None,
    status: str | None = None,
    text: str | None = None,
) -> list[dict[str, Any]]:
    query = text.lower().strip() if text else None
    result: list[dict[str, Any]] = []
    for crop in crop_records(manifest):
        if label and crop.get("label") != label:
            continue
        if source_image_id and crop.get("image_id") != source_image_id:
            continue
        if status and crop.get("status") != status:
            continue
        if query:
            haystack = " ".join(
                str(crop.get(key, ""))
                for key in (
                    "crop_id",
                    "bbox_id",
                    "image_id",
                    "label",
                    "status",
                    "display_name",
                    "crop_path",
                )
            ).lower()
            if query not in haystack:
                continue
        result.append(crop)
    return result


def update_crop(
    manifest: dict[str, Any],
    crop_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    crop = find_crop(manifest, crop_id)
    crop.update(updates)
    return crop


def _remove_empty_class_dirs(path: Path, crop_root: Path) -> None:
    current = path
    while current != crop_root and crop_root in current.parents:
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def relocate_crop_file(
    dataset_root: str | Path,
    partition_id: str,
    crop: dict[str, Any],
    label: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    crop_root = crop_root_dir(dataset_root, partition_id)
    target_label = label if label is not None else str(crop.get("label", ""))
    target_status = status if status is not None else str(crop.get("status", "active"))
    target_path = crop_file_path(crop_root, target_label, str(crop["crop_id"]), target_status)
    old_path = Path(str(crop.get("crop_path", "")))
    if old_path == target_path:
        return {"crop_path": str(target_path)}
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if old_path.is_file():
        if target_path.exists():
            target_path.unlink()
        shutil.move(str(old_path), str(target_path))
        _remove_empty_class_dirs(old_path.parent, crop_root)
    return {"crop_path": str(target_path)}


def replace_image_crops(
    manifest: dict[str, Any],
    image_ids: set[str],
    refreshed_crops: list[dict[str, Any]],
    summary_updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    kept_crops = [
        crop
        for crop in crop_records(manifest)
        if str(crop.get("image_id")) not in image_ids
    ]
    summary = dict(manifest.get("summary", {}))
    summary.update(summary_updates or {})
    all_crops = kept_crops + refreshed_crops
    summary["crops_total"] = len(all_crops)
    return {
        "version": manifest.get("version", CROP_MANIFEST_VERSION),
        "partition_id": manifest.get("partition_id", ""),
        "summary": summary,
        "crops": all_crops,
    }


def lookup_source_context(
    dataset_root: str | Path,
    partition_id: str,
    crop_id: str,
) -> dict[str, Any]:
    manifest = read_crop_manifest(dataset_root, partition_id)
    crop = find_crop(manifest, crop_id)
    image_id = str(crop["image_id"])
    annotation_path = Path(crop["annotation_path"])
    annotation = load_annotation(annotation_path, image_id=image_id, assign_ids=True)
    shape = find_shape_by_bbox_id(annotation, image_id=image_id, bbox_id=str(crop["bbox_id"]))
    if shape is None:
        raise CropManifestError(f"Source bounding box not found for crop: {crop_id}")
    return {
        "partition_id": partition_id,
        "crop": crop,
        "image_id": image_id,
        "source_image_path": crop["source_image_path"],
        "annotation_path": str(annotation_path),
        "bbox_id": crop["bbox_id"],
        "shape": shape,
    }


def _external_crop_files(external_root: str | Path) -> list[Path]:
    root = Path(external_root)
    if not root.exists():
        raise CropManifestError(f"External move folder does not exist: {root}")
    return sorted(path for path in root.rglob("*") if path.is_file())


def preview_external_moves(
    dataset_root: str | Path,
    partition_id: str,
    external_root: str | Path,
) -> OperationResult:
    manifest = read_crop_manifest(dataset_root, partition_id)
    crops_by_id = {str(crop["crop_id"]): crop for crop in query_crops(manifest)}
    moves: list[dict[str, Any]] = []
    files_checked = 0
    for path in _external_crop_files(external_root):
        files_checked += 1
        crop = crops_by_id.get(path.stem)
        if crop is None:
            continue
        target_label = path.parent.name.replace("_", " ").strip()
        if not target_label or target_label == crop.get("label"):
            continue
        moves.append(
            {
                "crop_id": crop["crop_id"],
                "bbox_id": crop["bbox_id"],
                "image_id": crop["image_id"],
                "from_label": crop.get("label", ""),
                "to_label": target_label,
                "external_path": str(path),
            }
        )
    return OperationResult(
        operation="preview_external_moves",
        success=True,
        summary={
            "partition_id": partition_id,
            "external_root": str(Path(external_root)),
            "files_checked": files_checked,
            "moves_found": len(moves),
            "moves": moves,
        },
        affected_ids=tuple(move["crop_id"] for move in moves),
    )


def apply_external_moves(
    dataset_root: str | Path,
    partition_id: str,
    external_root: str | Path,
) -> OperationResult:
    preview = preview_external_moves(dataset_root, partition_id, external_root)
    if not preview.success:
        return preview
    manifest = read_crop_manifest(dataset_root, partition_id)
    changes = []
    for move in preview.summary["moves"]:
        crop = find_crop(manifest, move["crop_id"])
        changes.append(stage_move_group_change(crop, move["to_label"]))
    commit_result = commit_pending_changes(changes)
    if not commit_result.success:
        return commit_result
    for move in preview.summary["moves"]:
        update_crop(
            manifest,
            move["crop_id"],
            {
                "label": move["to_label"],
                "external_move_path": move["external_path"],
            },
        )
    write_crop_manifest(dataset_root, partition_id, manifest)
    return OperationResult(
        operation="apply_external_moves",
        success=True,
        summary={
            "partition_id": partition_id,
            "moves_applied": len(changes),
            "files_written": commit_result.summary.get("files_written", 0),
        },
        affected_ids=tuple(move["crop_id"] for move in preview.summary["moves"]),
    )
