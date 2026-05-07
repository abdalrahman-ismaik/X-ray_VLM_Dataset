from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import json
from typing import Any

from xray_curation.config import DatasetConfig
from xray_curation.domain.operations import (
    ANNOTATION_EDIT_OPERATIONS,
    OperationResult,
    PendingChange,
)
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


def annotation_edit_conflicts(
    pending_changes: list[PendingChange],
) -> dict[str, list[PendingChange]]:
    by_target: dict[str, list[PendingChange]] = {}
    for change in pending_changes:
        if change.operation not in ANNOTATION_EDIT_OPERATIONS:
            continue
        image_id = str(change.payload.get("image_id", ""))
        bbox_id = str(change.payload.get("bbox_id") or change.payload.get("temporary_bbox_id") or change.target_id)
        target = f"{image_id}:{bbox_id}"
        by_target.setdefault(target, []).append(change)
    return {
        target: changes
        for target, changes in by_target.items()
        if len({change.operation for change in changes}) > 1
    }


def validate_pending_change_conflicts(
    pending_changes: list[PendingChange],
) -> OperationResult:
    conflicts = annotation_edit_conflicts(pending_changes)
    if not conflicts:
        return success_result(
            operation="validate_pending_change_conflicts",
            summary={"conflict_count": 0},
        )
    return failure_result(
        operation="validate_pending_change_conflicts",
        errors=tuple(
            f"Conflicting pending edits for {target}: "
            + ", ".join(change.operation for change in changes)
            for target, changes in conflicts.items()
        ),
        summary={
            "conflict_count": len(conflicts),
            "conflicts": {
                target: [change.change_id for change in changes]
                for target, changes in conflicts.items()
            },
        },
    )


def summarize_pending_changes(pending_changes: list[PendingChange]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "total": len(pending_changes),
        "by_operation": {},
        "annotation_edit_count": 0,
        "crop_edit_count": 0,
    }
    by_operation = summary["by_operation"]
    for change in pending_changes:
        by_operation[change.operation] = by_operation.get(change.operation, 0) + 1
        if change.operation in ANNOTATION_EDIT_OPERATIONS:
            summary["annotation_edit_count"] += 1
        else:
            summary["crop_edit_count"] += 1
    return summary


def summarize_commit_and_refresh(
    commit_result: OperationResult,
    refresh_result: OperationResult | None = None,
) -> dict[str, Any]:
    commit_summary = commit_result.summary
    summary = {
        "changes_applied": commit_summary.get("changes_applied", 0),
        "files_written": commit_summary.get("files_written", 0),
        "added_count": commit_summary.get("annotation_add_count", 0),
        "coordinate_edited_count": commit_summary.get("annotation_update_box_count", 0),
        "relabeled_count": commit_summary.get("annotation_relabel_count", 0),
        "deleted_count": commit_summary.get("annotation_delete_count", 0),
        "cancelled_count": 0,
        "refreshed_count": 0,
        "skipped_count": 0,
    }
    if refresh_result is not None:
        refresh_summary = refresh_result.summary
        summary["refreshed_count"] = refresh_summary.get("refreshed_image_count", 0)
        summary["skipped_count"] = refresh_summary.get("skipped_image_count", 0)
    return summary


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
