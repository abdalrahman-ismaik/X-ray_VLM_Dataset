from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from xray_curation.config import DEFAULT_PARTITION_SIZE, DatasetConfig
from xray_curation.domain.annotations import get_bbox_id, normalize_rectangle, rectangle_shapes
from xray_curation.domain.crops import CROP_STATUS_ACTIVE, crop_id_for_bbox
from xray_curation.domain.operations import CropRecord, OperationResult
from xray_curation.services.annotation_store import load_annotation
from xray_curation.services.crop_manifest import (
    build_crop_manifest,
    crop_file_path,
    crop_manifest_path,
    crop_records as manifest_crop_records,
    read_crop_manifest,
    replace_image_crops,
    write_crop_manifest,
)
from xray_curation.services.dataset_index import (
    detect_stale_images,
    load_or_create_dataset_manifest,
    partition_dir,
    select_partition,
    update_partition_state,
)
from xray_curation.services.validation import append_operation_log


def _clamp_box(
    box: tuple[int, int, int, int],
    width: int,
    height: int,
    padding: int,
) -> tuple[int, int, int, int]:
    left, top, right, bottom = box
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(width, max(left + 1, right + padding))
    bottom = min(height, max(top + 1, bottom + padding))
    return left, top, right, bottom


def _generate_crop_records_for_images(
    image_infos: list[dict],
    crop_dir: Path,
    overwrite: bool,
    padding: int,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> tuple[list[CropRecord], list[str], dict[str, int]]:
    from PIL import Image

    crop_records: list[CropRecord] = []
    warnings: list[str] = []
    images_processed = 0
    crops_written = 0
    crops_skipped = 0

    total = len(image_infos)
    for position, image_info in enumerate(image_infos, start=1):
        image_id = str(image_info["image_id"])
        image_path = Path(image_info["image_path"])
        annotation_path = Path(image_info["annotation_path"])
        if not image_path.exists():
            warnings.append(f"Missing image: {image_path}")
            if progress_callback:
                progress_callback(position, total, image_id)
            continue
        if not annotation_path.exists():
            warnings.append(f"Missing annotation: {annotation_path}")
            if progress_callback:
                progress_callback(position, total, image_id)
            continue

        annotation = load_annotation(
            annotation_path,
            image_id=image_id,
            assign_ids=True,
            save_if_changed=True,
        )
        with Image.open(image_path) as image:
            images_processed += 1
            width, height = image.size
            for _, shape in rectangle_shapes(annotation, image_id, assign_ids=True):
                bbox_id = get_bbox_id(shape)
                if bbox_id is None:
                    continue
                label = str(shape.get("label", ""))
                status = str(shape.get("flags", {}).get("curation_status", CROP_STATUS_ACTIVE))
                crop_id = crop_id_for_bbox(image_id, bbox_id)
                crop_path = crop_file_path(crop_dir, label, crop_id, status)
                if crop_path.exists() and not overwrite:
                    crops_skipped += 1
                else:
                    crop_path.parent.mkdir(parents=True, exist_ok=True)
                    box = _clamp_box(normalize_rectangle(shape["points"]), width, height, padding)
                    image.crop(box).save(crop_path)
                    crops_written += 1
                crop_records.append(
                    CropRecord(
                        crop_id=crop_id,
                        bbox_id=bbox_id,
                        image_id=image_id,
                        label=label,
                        crop_path=crop_path,
                        source_image_path=image_path,
                        annotation_path=annotation_path,
                        status=status,
                    )
                )
        if progress_callback:
            progress_callback(position, total, image_id)
    return crop_records, warnings, {
        "images_processed": images_processed,
        "crops_written": crops_written,
        "crops_skipped": crops_skipped,
    }


def generate_crops_for_partition(
    dataset_root: str | Path,
    partition_id: str,
    partition_size: int = DEFAULT_PARTITION_SIZE,
    overwrite: bool = False,
    padding: int = 0,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> OperationResult:
    try:
        from PIL import Image
    except ImportError as exc:
        return OperationResult(
            operation="generate_crops",
            success=False,
            errors=("Pillow is required to generate crops.",),
        )

    config = DatasetConfig.from_root(dataset_root, partition_size=partition_size)
    manifest = load_or_create_dataset_manifest(config.root, partition_size=partition_size)
    partition = select_partition(manifest, partition_id)
    crop_dir = partition_dir(config.root, partition_id) / "crops"
    crop_dir.mkdir(parents=True, exist_ok=True)

    crop_records, warnings, counters = _generate_crop_records_for_images(
        partition["images"],
        crop_dir=crop_dir,
        overwrite=overwrite,
        padding=padding,
        progress_callback=progress_callback,
    )

    summary = {
        "partition_id": partition_id,
        "partition_image_count": partition["image_count"],
        "images_seen": len(partition["images"]),
        "images_processed": counters["images_processed"],
        "crops_total": len(crop_records),
        "crops_written": counters["crops_written"],
        "crops_skipped": counters["crops_skipped"],
        "crop_dir": str(crop_dir),
    }
    crop_manifest = build_crop_manifest(partition_id, crop_records, summary)
    manifest_path = write_crop_manifest(config.root, partition_id, crop_manifest)
    summary["crop_manifest_path"] = str(manifest_path)
    result = OperationResult(
        operation="generate_crops",
        success=len(warnings) == 0,
        summary=summary,
        warnings=tuple(warnings),
        affected_ids=tuple(record.crop_id for record in crop_records),
    )
    update_partition_state(
        config.root,
        partition_id,
        status="ready" if result.success else "error",
        summary=result.summary,
    )
    append_operation_log(config.root, result)
    return result


def refresh_changed_crops_for_partition(
    dataset_root: str | Path,
    partition_id: str,
    partition_size: int = DEFAULT_PARTITION_SIZE,
    padding: int = 0,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> OperationResult:
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        return OperationResult(
            operation="refresh_changed_crops",
            success=False,
            errors=("Pillow is required to refresh crops.",),
        )

    config = DatasetConfig.from_root(dataset_root, partition_size=partition_size)
    manifest = load_or_create_dataset_manifest(config.root, partition_size=partition_size)
    partition = select_partition(manifest, partition_id)
    stale = detect_stale_images(config.root, partition_id)
    changed_ids = set(stale["changed_image_ids"])
    crop_dir = partition_dir(config.root, partition_id) / "crops"
    crop_dir.mkdir(parents=True, exist_ok=True)

    try:
        existing_manifest = read_crop_manifest(config.root, partition_id)
        existing_crops = [
            crop
            for crop in existing_manifest.get("crops", [])
            if crop.get("image_id") not in changed_ids
        ]
    except Exception:
        existing_crops = []

    changed_images = [
        image_info
        for image_info in partition["images"]
        if image_info["image_id"] in changed_ids
    ]
    crop_records, warnings, counters = _generate_crop_records_for_images(
        changed_images,
        crop_dir=crop_dir,
        overwrite=True,
        padding=padding,
        progress_callback=progress_callback,
    )
    refreshed_crops = [record.to_manifest() for record in crop_records]
    all_crops = existing_crops + refreshed_crops

    summary = {
        "partition_id": partition_id,
        "mode": "refresh_changed",
        "partition_image_count": partition["image_count"],
        "changed_image_count": len(changed_images),
        "changed_image_ids": sorted(changed_ids),
        "images_processed": counters["images_processed"],
        "crops_total": len(all_crops),
        "crops_written": counters["crops_written"],
        "crops_skipped": counters["crops_skipped"],
        "crop_dir": str(crop_dir),
    }
    crop_manifest = {
        "version": 1,
        "partition_id": partition_id,
        "summary": summary,
        "crops": all_crops,
    }
    manifest_path = write_crop_manifest(config.root, partition_id, crop_manifest)
    summary["crop_manifest_path"] = str(manifest_path)

    result = OperationResult(
        operation="refresh_changed_crops",
        success=len(warnings) == 0,
        summary=summary,
        warnings=tuple(warnings),
        affected_ids=tuple(record.crop_id for record in crop_records),
    )
    update_partition_state(
        config.root,
        partition_id,
        status="ready" if result.success else "error",
        summary=result.summary,
    )
    append_operation_log(config.root, result)
    return result


def refresh_affected_image_crops(
    dataset_root: str | Path,
    partition_id: str,
    image_ids: list[str] | tuple[str, ...] | set[str],
    partition_size: int = DEFAULT_PARTITION_SIZE,
    padding: int = 0,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> OperationResult:
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        return OperationResult(
            operation="refresh_affected_image_crops",
            success=False,
            errors=("Pillow is required to refresh crops.",),
        )

    config = DatasetConfig.from_root(dataset_root, partition_size=partition_size)
    affected_ids = {str(image_id) for image_id in image_ids if str(image_id)}
    manifest_path = crop_manifest_path(config.root, partition_id)
    if not manifest_path.exists():
        result = OperationResult(
            operation="refresh_affected_image_crops",
            success=True,
            summary={
                "partition_id": partition_id,
                "mode": "affected_images",
                "requested_image_count": len(affected_ids),
                "refreshed_image_count": 0,
                "skipped_image_count": len(affected_ids),
                "skip_reason": "crop manifest does not exist",
            },
            affected_ids=(),
        )
        append_operation_log(config.root, result)
        return result

    manifest = load_or_create_dataset_manifest(config.root, partition_size=partition_size)
    partition = select_partition(manifest, partition_id)
    selected_images = [
        image_info
        for image_info in partition["images"]
        if str(image_info["image_id"]) in affected_ids
    ]
    selected_ids = {str(image_info["image_id"]) for image_info in selected_images}
    skipped_ids = sorted(affected_ids - selected_ids)
    crop_dir = partition_dir(config.root, partition_id) / "crops"
    crop_dir.mkdir(parents=True, exist_ok=True)
    crop_records, warnings, counters = _generate_crop_records_for_images(
        selected_images,
        crop_dir=crop_dir,
        overwrite=True,
        padding=padding,
        progress_callback=progress_callback,
    )
    refreshed_crops = [record.to_manifest() for record in crop_records]
    existing_manifest = read_crop_manifest(config.root, partition_id)
    stale_paths = {
        Path(str(crop.get("crop_path", "")))
        for crop in manifest_crop_records(existing_manifest)
        if str(crop.get("image_id")) in selected_ids
    }
    refreshed_paths = {Path(str(crop.get("crop_path", ""))) for crop in refreshed_crops}
    for stale_path in stale_paths - refreshed_paths:
        if stale_path.is_file():
            stale_path.unlink()
    summary = {
        "partition_id": partition_id,
        "mode": "affected_images",
        "requested_image_count": len(affected_ids),
        "refreshed_image_count": len(selected_images),
        "skipped_image_count": len(skipped_ids),
        "skipped_image_ids": skipped_ids,
        "affected_image_ids": sorted(selected_ids),
        "images_processed": counters["images_processed"],
        "crops_written": counters["crops_written"],
        "crops_skipped": counters["crops_skipped"],
        "refreshed_crop_count": len(refreshed_crops),
        "crop_dir": str(crop_dir),
    }
    refreshed_manifest = replace_image_crops(
        existing_manifest,
        selected_ids,
        refreshed_crops,
        summary_updates=summary,
    )
    written_path = write_crop_manifest(config.root, partition_id, refreshed_manifest)
    summary["crop_manifest_path"] = str(written_path)
    result = OperationResult(
        operation="refresh_affected_image_crops",
        success=len(warnings) == 0,
        summary=summary,
        warnings=tuple(warnings),
        affected_ids=tuple(record.crop_id for record in crop_records),
    )
    update_partition_state(
        config.root,
        partition_id,
        status="ready" if result.success else "error",
        summary=result.summary,
    )
    append_operation_log(config.root, result)
    return result
