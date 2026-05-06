from __future__ import annotations

import hashlib
from typing import Any, Iterable

BBOX_ID_FIELD = "curation_bbox_id"


def is_rectangle_shape(shape: dict[str, Any]) -> bool:
    points = shape.get("points")
    if not isinstance(points, list) or len(points) < 2:
        return False
    shape_type = shape.get("shape_type") or "rectangle"
    return str(shape_type).lower() == "rectangle"


def normalize_rectangle(
    points: Iterable[Iterable[float]],
) -> tuple[int, int, int, int]:
    coords = [(float(point[0]), float(point[1])) for point in points]
    xs = [point[0] for point in coords]
    ys = [point[1] for point in coords]
    left, right = sorted((min(xs), max(xs)))
    top, bottom = sorted((min(ys), max(ys)))
    return round(left), round(top), round(right), round(bottom)


def get_bbox_id(shape: dict[str, Any]) -> str | None:
    flags = shape.get("flags")
    if isinstance(flags, dict) and flags.get(BBOX_ID_FIELD):
        return str(flags[BBOX_ID_FIELD])
    if shape.get(BBOX_ID_FIELD):
        return str(shape[BBOX_ID_FIELD])
    return None


def set_bbox_id(shape: dict[str, Any], bbox_id: str) -> None:
    flags = shape.setdefault("flags", {})
    if not isinstance(flags, dict):
        flags = {}
        shape["flags"] = flags
    flags[BBOX_ID_FIELD] = bbox_id


def bbox_id_from_shape(image_id: str, shape: dict[str, Any]) -> str:
    x1, y1, x2, y2 = normalize_rectangle(shape["points"])
    payload = f"{image_id}|{x1}|{y1}|{x2}|{y2}".encode("utf-8")
    return "bbox-" + hashlib.sha1(payload).hexdigest()[:16]


def ensure_bbox_id(shape: dict[str, Any], image_id: str) -> str:
    existing = get_bbox_id(shape)
    if existing:
        return existing
    bbox_id = bbox_id_from_shape(image_id, shape)
    set_bbox_id(shape, bbox_id)
    return bbox_id


def rectangle_shapes(
    annotation: dict[str, Any],
    image_id: str,
    assign_ids: bool = False,
) -> list[tuple[int, dict[str, Any]]]:
    result: list[tuple[int, dict[str, Any]]] = []
    for index, shape in enumerate(annotation.get("shapes", [])):
        if not isinstance(shape, dict) or not is_rectangle_shape(shape):
            continue
        if assign_ids:
            ensure_bbox_id(shape, image_id)
        result.append((index, shape))
    return result
