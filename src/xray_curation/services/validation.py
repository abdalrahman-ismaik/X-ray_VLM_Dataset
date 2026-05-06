from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import json
from typing import Any

from xray_curation.config import DatasetConfig
from xray_curation.domain.operations import OperationResult, PendingChange
from xray_curation.services.annotation_store import stage_soft_delete_change
from xray_curation.services.crop_manifest import query_crops, read_crop_manifest


def success_result(
    operation: str,
    summary: dict[str, Any] | None = None,
    affected_ids: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
) -> OperationResult:
    return OperationResult(
        operation=operation,
        success=True,
        summary=summary or {},
        warnings=warnings,
        affected_ids=affected_ids,
    )


def failure_result(
    operation: str,
    errors: tuple[str, ...],
    summary: dict[str, Any] | None = None,
) -> OperationResult:
    return OperationResult(
        operation=operation,
        success=False,
        summary=summary or {},
        errors=errors,
    )


def has_unsaved_changes(pending_changes: list[PendingChange]) -> bool:
    return len(pending_changes) > 0


def ensure_no_unsaved_changes(
    pending_changes: list[PendingChange],
    operation: str,
) -> OperationResult:
    if not pending_changes:
        return success_result(
            operation="guard_unsaved_changes",
            summary={"operation": operation, "pending_count": 0},
        )
    return failure_result(
        operation="guard_unsaved_changes",
        errors=(
            f"Save or cancel {len(pending_changes)} pending change(s) before running {operation}.",
        ),
        summary={"operation": operation, "pending_count": len(pending_changes)},
    )


def detect_missing_crops(dataset_root, partition_id: str) -> OperationResult:
    manifest = read_crop_manifest(dataset_root, partition_id)
    crops = query_crops(manifest)
    missing = [
        crop
        for crop in crops
        if not crop.get("crop_path") or not Path(crop["crop_path"]).exists()
    ]
    return success_result(
        operation="detect_missing_crops",
        summary={
            "partition_id": partition_id,
            "checked_count": len(crops),
            "missing_count": len(missing),
            "missing_crops": [
                {
                    "crop_id": crop["crop_id"],
                    "image_id": crop["image_id"],
                    "label": crop.get("label", ""),
                    "crop_path": crop.get("crop_path", ""),
                }
                for crop in missing
            ],
        },
        affected_ids=tuple(str(crop["crop_id"]) for crop in missing),
    )


def stage_missing_crop_deletions(
    dataset_root,
    partition_id: str,
) -> tuple[OperationResult, list[PendingChange]]:
    manifest = read_crop_manifest(dataset_root, partition_id)
    missing_ids = set(detect_missing_crops(dataset_root, partition_id).affected_ids)
    changes = [
        stage_soft_delete_change(crop)
        for crop in query_crops(manifest)
        if crop.get("crop_id") in missing_ids
    ]
    result = success_result(
        operation="stage_missing_crop_deletions",
        summary={
            "partition_id": partition_id,
            "staged_count": len(changes),
        },
        affected_ids=tuple(change.target_id for change in changes),
    )
    return result, changes


def operation_log_path(dataset_root: str | Path) -> Path:
    return DatasetConfig.from_root(dataset_root).curation_dir / "operation_log.jsonl"


def append_operation_log(
    dataset_root: str | Path,
    result: OperationResult,
    extra: dict[str, Any] | None = None,
) -> Path:
    path = operation_log_path(dataset_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "operation": result.operation,
        "success": result.success,
        "result": result.to_dict(),
    }
    if extra:
        entry["extra"] = extra
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False))
        handle.write("\n")
    return path


def read_operation_log(dataset_root: str | Path) -> list[dict[str, Any]]:
    path = operation_log_path(dataset_root)
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries
