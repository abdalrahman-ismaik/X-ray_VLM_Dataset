from __future__ import annotations

from pathlib import Path
from typing import Any

from xray_curation.domain.labels import canonical_label
from xray_curation.domain.operations import OperationResult
from xray_curation.services.annotation_store import (
    commit_pending_changes,
    find_shape_by_bbox_id,
    load_annotation,
    stage_relabel_change,
)
from xray_curation.services.crop_manifest import (
    find_crop,
    query_crops,
    read_crop_manifest,
    update_crop,
    write_crop_manifest,
)


def _annotation_label(crop: dict[str, Any]) -> str:
    image_id = str(crop["image_id"])
    annotation = load_annotation(
        crop["annotation_path"],
        image_id=image_id,
        assign_ids=True,
        save_if_changed=True,
    )
    shape = find_shape_by_bbox_id(annotation, image_id=image_id, bbox_id=str(crop["bbox_id"]))
    if shape is None:
        return str(crop.get("label", ""))
    return str(shape.get("label", ""))


def preview_label_standardization_for_partition(
    dataset_root: str | Path,
    partition_id: str,
) -> OperationResult:
    manifest = read_crop_manifest(dataset_root, partition_id)
    proposals: list[dict[str, Any]] = []
    unknowns: list[dict[str, Any]] = []
    checked = 0

    for crop in query_crops(manifest):
        checked += 1
        current_label = _annotation_label(crop)
        target_label = canonical_label(current_label)
        entry = {
            "crop_id": crop["crop_id"],
            "bbox_id": crop["bbox_id"],
            "image_id": crop["image_id"],
            "current_label": current_label,
        }
        if target_label is None:
            unknowns.append(entry)
        elif target_label != current_label:
            proposals.append({**entry, "target_label": target_label})

    return OperationResult(
        operation="preview_label_standardization",
        success=True,
        summary={
            "partition_id": partition_id,
            "checked_count": checked,
            "proposed_count": len(proposals),
            "unknown_count": len(unknowns),
            "proposals": proposals,
            "unknowns": unknowns,
        },
        warnings=tuple(
            f"Unknown label for {item['crop_id']}: {item['current_label']}"
            for item in unknowns
        ),
        affected_ids=tuple(item["crop_id"] for item in proposals),
    )


def apply_label_standardization_for_partition(
    dataset_root: str | Path,
    partition_id: str,
) -> OperationResult:
    preview = preview_label_standardization_for_partition(dataset_root, partition_id)
    manifest = read_crop_manifest(dataset_root, partition_id)
    changes = []

    for proposal in preview.summary["proposals"]:
        crop = find_crop(manifest, proposal["crop_id"])
        changes.append(stage_relabel_change(crop, proposal["target_label"]))

    commit_result = commit_pending_changes(changes)
    if not commit_result.success:
        return commit_result

    for proposal in preview.summary["proposals"]:
        update_crop(
            manifest,
            proposal["crop_id"],
            {"label": proposal["target_label"]},
        )
    if changes:
        write_crop_manifest(dataset_root, partition_id, manifest)

    return OperationResult(
        operation="apply_label_standardization",
        success=True,
        summary={
            "partition_id": partition_id,
            "labels_updated": len(changes),
            "unknown_count": preview.summary["unknown_count"],
            "files_written": commit_result.summary.get("files_written", 0),
            "unknowns": preview.summary["unknowns"],
        },
        warnings=preview.warnings,
        affected_ids=tuple(proposal["crop_id"] for proposal in preview.summary["proposals"]),
    )
