from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from xray_curation.services.annotation_store import load_json, save_json_atomic
from xray_curation.services.dataset_index import partition_dir

REVIEW_STATE_VERSION = 1
REVIEW_FILTER_UNAPPROVED = "unapproved"
REVIEW_FILTER_APPROVED = "approved"
REVIEW_FILTER_ALL = "all"


def review_state_path(dataset_root: str | Path, partition_id: str) -> Path:
    return partition_dir(dataset_root, partition_id) / "review_state.json"


def empty_review_state(partition_id: str) -> dict[str, Any]:
    return {
        "version": REVIEW_STATE_VERSION,
        "partition_id": partition_id,
        "approved_images": [],
        "approved_crops": [],
    }


def normalize_review_state(payload: dict[str, Any] | None, partition_id: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}
    return {
        "version": int(payload.get("version", REVIEW_STATE_VERSION)),
        "partition_id": str(payload.get("partition_id") or partition_id),
        "approved_images": sorted(
            {str(image_id) for image_id in payload.get("approved_images", []) if str(image_id)}
        ),
        "approved_crops": sorted(
            {str(crop_id) for crop_id in payload.get("approved_crops", []) if str(crop_id)}
        ),
    }


def load_review_state(dataset_root: str | Path, partition_id: str) -> dict[str, Any]:
    path = review_state_path(dataset_root, partition_id)
    if not path.exists():
        return empty_review_state(partition_id)
    return normalize_review_state(load_json(path), partition_id)


def write_review_state(
    dataset_root: str | Path,
    partition_id: str,
    state: dict[str, Any],
) -> Path:
    normalized = normalize_review_state(state, partition_id)
    path = review_state_path(dataset_root, partition_id)
    save_json_atomic(path, normalized)
    return path


def approved_image_ids(state: dict[str, Any] | None) -> set[str]:
    normalized = normalize_review_state(state, "")
    return set(normalized["approved_images"])


def approved_crop_ids(state: dict[str, Any] | None) -> set[str]:
    normalized = normalize_review_state(state, "")
    return set(normalized["approved_crops"])


def crop_is_approved(crop: dict[str, Any], state: dict[str, Any] | None) -> bool:
    return str(crop.get("crop_id", "")) in approved_crop_ids(state) or str(
        crop.get("image_id", "")
    ) in approved_image_ids(state)


def image_is_approved(image_id: str, state: dict[str, Any] | None) -> bool:
    return image_id in approved_image_ids(state)


def review_filter_accepts_approved(is_approved: bool, review_filter: str) -> bool:
    normalized_filter = str(review_filter or REVIEW_FILTER_UNAPPROVED).casefold()
    if normalized_filter == REVIEW_FILTER_ALL:
        return True
    if normalized_filter == REVIEW_FILTER_APPROVED:
        return is_approved
    return not is_approved


def filter_crops_by_review_state(
    crops: Iterable[dict[str, Any]],
    state: dict[str, Any] | None,
    review_filter: str = REVIEW_FILTER_UNAPPROVED,
) -> list[dict[str, Any]]:
    return [
        crop
        for crop in crops
        if review_filter_accepts_approved(crop_is_approved(crop, state), review_filter)
    ]


def set_review_approval(
    state: dict[str, Any] | None,
    *,
    partition_id: str,
    crop_ids: Iterable[str] = (),
    image_ids: Iterable[str] = (),
    approved: bool,
) -> dict[str, Any]:
    normalized = normalize_review_state(state, partition_id)
    approved_crops = set(normalized["approved_crops"])
    approved_images = set(normalized["approved_images"])
    clean_crop_ids = {str(crop_id) for crop_id in crop_ids if str(crop_id)}
    clean_image_ids = {str(image_id) for image_id in image_ids if str(image_id)}
    if approved:
        approved_crops.update(clean_crop_ids)
        approved_images.update(clean_image_ids)
    else:
        approved_crops.difference_update(clean_crop_ids)
        approved_images.difference_update(clean_image_ids)
    normalized["approved_crops"] = sorted(approved_crops)
    normalized["approved_images"] = sorted(approved_images)
    return normalized
