from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from xray_curation.domain.operations import (
    ANNOTATION_ADD,
    ANNOTATION_DELETE,
    ANNOTATION_EDIT_OPERATIONS,
    ANNOTATION_RELABEL,
    ANNOTATION_UPDATE_BOX,
    OperationResult,
    PendingChange,
)
from xray_curation.domain.annotations import (
    BBOX_ID_FIELD,
    bbox_id_from_shape,
    get_bbox_id,
    is_valid_rectangle,
    normalize_rectangle,
    rectangle_shapes,
    set_bbox_id,
)
from xray_curation.domain.labels import is_approved_label


class AnnotationStoreError(RuntimeError):
    pass


def load_json(path: str | Path) -> dict[str, Any]:
    json_path = Path(path)
    try:
        with json_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise AnnotationStoreError(f"Could not load annotation JSON: {json_path}") from exc
    if not isinstance(data, dict):
        raise AnnotationStoreError(f"Annotation JSON root must be an object: {json_path}")
    return data


def save_json_atomic(path: str | Path, data: dict[str, Any]) -> None:
    json_path = Path(path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = json_path.with_name(json_path.name + ".tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(temp_path, json_path)
    except OSError as exc:
        raise AnnotationStoreError(f"Could not save annotation JSON: {json_path}") from exc


def assign_missing_bbox_ids(annotation: dict[str, Any], image_id: str) -> list[str]:
    assigned: list[str] = []
    seen: set[str] = set()
    for _, shape in rectangle_shapes(annotation, image_id, assign_ids=False):
        before = get_bbox_id(shape)
        base_id = before or bbox_id_from_shape(image_id, shape)
        bbox_id = _unique_bbox_id(base_id, seen)
        if before != bbox_id:
            set_bbox_id(shape, bbox_id)
            assigned.append(bbox_id)
        seen.add(bbox_id)
    return assigned


def _unique_bbox_id(base_id: str, seen: set[str]) -> str:
    if base_id not in seen:
        return base_id
    suffix = 2
    while f"{base_id}-{suffix}" in seen:
        suffix += 1
    return f"{base_id}-{suffix}"


def load_annotation(
    path: str | Path,
    image_id: str,
    assign_ids: bool = False,
    save_if_changed: bool = False,
) -> dict[str, Any]:
    annotation = load_json(path)
    assigned = assign_missing_bbox_ids(annotation, image_id) if assign_ids else []
    if assigned and save_if_changed:
        save_json_atomic(path, annotation)
    return annotation


def find_shape_by_bbox_id(
    annotation: dict[str, Any],
    image_id: str,
    bbox_id: str,
) -> dict[str, Any] | None:
    for _, shape in rectangle_shapes(annotation, image_id, assign_ids=True):
        if get_bbox_id(shape) == bbox_id:
            return shape
    return None


def _crop_change(
    crop: dict[str, Any],
    operation: str,
    payload: dict[str, Any] | None = None,
) -> PendingChange:
    crop_id = str(crop["crop_id"])
    return PendingChange(
        change_id=f"{operation}:{crop_id}",
        target_id=crop_id,
        operation=operation,
        payload={
            "crop_id": crop_id,
            "bbox_id": str(crop["bbox_id"]),
            "image_id": str(crop["image_id"]),
            "annotation_path": str(crop["annotation_path"]),
            **(payload or {}),
        },
    )


def stage_relabel_change(crop: dict[str, Any], new_label: str) -> PendingChange:
    return _crop_change(crop, "relabel", {"label": new_label})


def stage_rename_change(crop: dict[str, Any], display_name: str) -> PendingChange:
    return _crop_change(crop, "rename", {"display_name": display_name})


def stage_move_group_change(crop: dict[str, Any], new_label: str) -> PendingChange:
    return _crop_change(crop, "move_group", {"label": new_label})


def stage_soft_delete_change(crop: dict[str, Any]) -> PendingChange:
    return _crop_change(crop, "soft_delete")


def stage_restore_change(crop: dict[str, Any]) -> PendingChange:
    return _crop_change(crop, "restore")


def add_pending_change(
    pending_changes: list[PendingChange],
    change: PendingChange,
) -> list[PendingChange]:
    return [item for item in pending_changes if item.change_id != change.change_id] + [change]


def cancel_pending_change(
    pending_changes: list[PendingChange],
    change_id: str,
) -> list[PendingChange]:
    return [change for change in pending_changes if change.change_id != change_id]


def _shape_flags(shape: dict[str, Any]) -> dict[str, Any]:
    flags = shape.setdefault("flags", {})
    if not isinstance(flags, dict):
        flags = {}
        shape["flags"] = flags
    return flags


def _shape_points(rectangle: tuple[int, int, int, int]) -> list[list[int]]:
    return [[rectangle[0], rectangle[1]], [rectangle[2], rectangle[3]]]


def _apply_annotation_add(annotation: dict[str, Any], change: PendingChange) -> str:
    shapes = annotation.setdefault("shapes", [])
    if not isinstance(shapes, list):
        raise AnnotationStoreError("Annotation JSON 'shapes' field must be a list")
    image_id = str(change.payload["image_id"])
    label = str(change.payload["label"])
    if not is_approved_label(label):
        raise AnnotationStoreError(f"New boxes require an approved PIDRay label: {label}")
    points = change.payload["points"]
    rectangle = normalize_rectangle(((points[0], points[1]), (points[2], points[3])))
    if not is_valid_rectangle(rectangle):
        raise AnnotationStoreError("Rectangle must be at least 2x2 image pixels")
    bbox_id = str(change.payload["temporary_bbox_id"])
    shape = {
        "label": label,
        "points": _shape_points(rectangle),
        "group_id": None,
        "description": "",
        "shape_type": "rectangle",
        "flags": {},
    }
    set_bbox_id(shape, bbox_id)
    shapes.append(shape)
    return bbox_id


def _apply_change(annotation: dict[str, Any], change: PendingChange) -> str:
    if change.operation == ANNOTATION_ADD:
        return _apply_annotation_add(annotation, change)

    image_id = str(change.payload["image_id"])
    bbox_id = str(change.payload["bbox_id"])
    shape = find_shape_by_bbox_id(annotation, image_id=image_id, bbox_id=bbox_id)
    if shape is None:
        raise AnnotationStoreError(f"Bounding box not found: {bbox_id}")
    set_bbox_id(shape, bbox_id)
    flags = _shape_flags(shape)

    if change.operation == ANNOTATION_UPDATE_BOX:
        points = change.payload["points"]
        rectangle = normalize_rectangle(((points[0], points[1]), (points[2], points[3])))
        if not is_valid_rectangle(rectangle):
            raise AnnotationStoreError("Rectangle must be at least 2x2 image pixels")
        shape["points"] = _shape_points(rectangle)
    elif change.operation == ANNOTATION_RELABEL:
        label = str(change.payload["label"])
        if not is_approved_label(label):
            raise AnnotationStoreError(f"Existing boxes require an approved PIDRay label: {label}")
        shape["label"] = label
        flags["curation_status"] = "active"
    elif change.operation == ANNOTATION_DELETE:
        shapes = annotation.get("shapes", [])
        if not isinstance(shapes, list):
            raise AnnotationStoreError("Annotation JSON 'shapes' field must be a list")
        annotation["shapes"] = [
            candidate
            for candidate in shapes
            if not (
                isinstance(candidate, dict)
                and get_bbox_id(candidate) == bbox_id
            )
        ]
    elif change.operation in {"relabel", "move_group"}:
        shape["label"] = str(change.payload["label"])
        flags["curation_status"] = "active"
    elif change.operation == "rename":
        flags["curation_display_name"] = str(change.payload["display_name"])
    elif change.operation == "soft_delete":
        flags["curation_status"] = "soft_deleted"
    elif change.operation == "restore":
        flags["curation_status"] = "active"
    else:
        raise AnnotationStoreError(f"Unsupported pending change: {change.operation}")
    return str(flags.get(BBOX_ID_FIELD, bbox_id))


def commit_pending_changes(pending_changes: list[PendingChange]) -> OperationResult:
    grouped: dict[Path, list[PendingChange]] = {}
    for change in pending_changes:
        grouped.setdefault(Path(str(change.payload["annotation_path"])), []).append(change)

    affected_ids: list[str] = []
    errors: list[str] = []
    files_written = 0
    changes_applied = 0
    annotation_add_count = 0
    annotation_update_box_count = 0
    annotation_relabel_count = 0
    annotation_delete_count = 0

    for annotation_path, changes in grouped.items():
        if not changes:
            continue
        image_id = str(changes[0].payload["image_id"])
        try:
            annotation = load_annotation(
                annotation_path,
                image_id=image_id,
                assign_ids=True,
                save_if_changed=False,
            )
            for change in changes:
                affected_ids.append(_apply_change(annotation, change))
                changes_applied += 1
                if change.operation == ANNOTATION_ADD:
                    annotation_add_count += 1
                elif change.operation == ANNOTATION_UPDATE_BOX:
                    annotation_update_box_count += 1
                elif change.operation == ANNOTATION_RELABEL:
                    annotation_relabel_count += 1
                elif change.operation == ANNOTATION_DELETE:
                    annotation_delete_count += 1
            save_json_atomic(annotation_path, annotation)
            files_written += 1
        except AnnotationStoreError as exc:
            errors.append(str(exc))

    summary = {
        "changes_applied": changes_applied,
        "files_written": files_written,
    }
    if annotation_add_count:
        summary["annotation_add_count"] = annotation_add_count
    if annotation_update_box_count:
        summary["annotation_update_box_count"] = annotation_update_box_count
    if annotation_relabel_count:
        summary["annotation_relabel_count"] = annotation_relabel_count
    if annotation_delete_count:
        summary["annotation_delete_count"] = annotation_delete_count
    affected_image_ids = sorted(
        {
            str(change.payload.get("image_id"))
            for change in pending_changes
            if change.payload.get("image_id")
        }
    )
    if affected_image_ids:
        summary["affected_image_ids"] = affected_image_ids

    return OperationResult(
        operation="commit_pending_changes",
        success=len(errors) == 0,
        summary=summary,
        errors=tuple(errors),
        affected_ids=tuple(affected_ids),
    )


def commit_shared_pending_changes(pending_changes: list[PendingChange]) -> OperationResult:
    return commit_pending_changes(pending_changes)
