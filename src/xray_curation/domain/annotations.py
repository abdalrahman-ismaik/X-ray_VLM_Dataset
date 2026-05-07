from __future__ import annotations

import hashlib
from typing import Any, Iterable

BBOX_ID_FIELD = "curation_bbox_id"
MIN_RECTANGLE_SIZE = 2


def _point_pair(point: Any) -> tuple[float, float] | None:
    if not isinstance(point, (list, tuple)) or len(point) < 2:
        return None
    try:
        return float(point[0]), float(point[1])
    except (TypeError, ValueError):
        return None


def is_rectangle_shape(shape: dict[str, Any]) -> bool:
    points = shape.get("points")
    if not isinstance(points, list) or len(points) < 2:
        return False
    shape_type = shape.get("shape_type") or "rectangle"
    if str(shape_type).lower() != "rectangle":
        return False
    valid_points = [_point_pair(point) for point in points]
    return sum(point is not None for point in valid_points) >= 2


def normalize_rectangle(
    points: Iterable[Iterable[float]],
) -> tuple[int, int, int, int]:
    coords = []
    for point in points:
        pair = _point_pair(point)
        if pair is not None:
            coords.append(pair)
    if len(coords) < 2:
        raise ValueError("Rectangle requires at least two valid points")
    xs = [point[0] for point in coords]
    ys = [point[1] for point in coords]
    left, right = sorted((min(xs), max(xs)))
    top, bottom = sorted((min(ys), max(ys)))
    return round(left), round(top), round(right), round(bottom)


def clamp_rectangle(
    rectangle: tuple[int, int, int, int],
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = rectangle
    max_x = max(0, int(image_width))
    max_y = max(0, int(image_height))
    return (
        max(0, min(max_x, x1)),
        max(0, min(max_y, y1)),
        max(0, min(max_x, x2)),
        max(0, min(max_y, y2)),
    )


def rectangle_size(rectangle: tuple[int, int, int, int]) -> tuple[int, int]:
    x1, y1, x2, y2 = rectangle
    return abs(x2 - x1), abs(y2 - y1)


def is_valid_rectangle(
    rectangle: tuple[int, int, int, int],
    min_size: int = MIN_RECTANGLE_SIZE,
) -> bool:
    width, height = rectangle_size(rectangle)
    return width >= min_size and height >= min_size


def normalize_clamped_rectangle(
    points: Iterable[Iterable[float]],
    image_width: int,
    image_height: int,
    min_size: int = MIN_RECTANGLE_SIZE,
) -> tuple[int, int, int, int]:
    rectangle = clamp_rectangle(normalize_rectangle(points), image_width, image_height)
    x1, y1, x2, y2 = normalize_rectangle(((rectangle[0], rectangle[1]), (rectangle[2], rectangle[3])))
    normalized = (x1, y1, x2, y2)
    if not is_valid_rectangle(normalized, min_size=min_size):
        raise ValueError(
            f"Rectangle must be at least {min_size}x{min_size} image pixels"
        )
    return normalized


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
        try:
            normalize_rectangle(shape["points"])
        except (KeyError, ValueError):
            continue
        if assign_ids:
            ensure_bbox_id(shape, image_id)
        result.append((index, shape))
    return result
