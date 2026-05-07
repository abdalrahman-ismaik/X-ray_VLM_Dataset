from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from PIL import Image

from xray_curation.domain.annotations import (
    MIN_RECTANGLE_SIZE,
    bbox_id_from_shape,
    clamp_rectangle,
    ensure_bbox_id,
    is_rectangle_shape,
    is_valid_rectangle,
    normalize_rectangle,
)
from xray_curation.domain.labels import is_approved_label
from xray_curation.domain.operations import (
    ANNOTATION_ADD,
    ANNOTATION_DELETE,
    ANNOTATION_RELABEL,
    ANNOTATION_UPDATE_BOX,
    ImageRecord,
    PendingChange,
)
from xray_curation.services.annotation_store import load_annotation
from xray_curation.services.crop_manifest import lookup_source_context
from xray_curation.services.dataset_index import list_partition_image_records


@dataclass(frozen=True)
class EditableBoundingBox:
    bbox_id: str
    shape_index: int
    label: str
    points: tuple[int, int, int, int]
    status: str = "active"
    is_selected: bool = False
    source_crop_id: str | None = None

    @property
    def width(self) -> int:
        return abs(self.points[2] - self.points[0])

    @property
    def height(self) -> int:
        return abs(self.points[3] - self.points[1])


@dataclass(frozen=True)
class SourceImageContext:
    dataset_root: Path
    partition_id: str
    image_id: str
    image_path: Path
    annotation_path: Path
    ordinal: int
    image_size: tuple[int, int]
    boxes: tuple[EditableBoundingBox, ...]
    unsupported_shape_count: int = 0
    load_warnings: tuple[str, ...] = ()
    selected_bbox_id: str | None = None

    @property
    def selected_box(self) -> EditableBoundingBox | None:
        if self.selected_bbox_id is None:
            return None
        for box in self.boxes:
            if box.bbox_id == self.selected_bbox_id:
                return box
        return None

    def with_selection(self, bbox_id: str | None) -> "SourceImageContext":
        return replace(
            self,
            selected_bbox_id=bbox_id,
            boxes=tuple(
                replace(box, is_selected=box.bbox_id == bbox_id)
                for box in self.boxes
            ),
        )


@dataclass(frozen=True)
class CanvasTransform:
    image_width: int
    image_height: int
    canvas_width: int
    canvas_height: int
    scale: float
    offset_x: float
    offset_y: float

    @classmethod
    def fit(
        cls,
        image_size: tuple[int, int],
        canvas_size: tuple[int, int],
    ) -> "CanvasTransform":
        image_width, image_height = image_size
        canvas_width, canvas_height = canvas_size
        if image_width <= 0 or image_height <= 0:
            raise ValueError("Image size must be positive")
        usable_width = max(1, canvas_width)
        usable_height = max(1, canvas_height)
        scale = min(usable_width / image_width, usable_height / image_height)
        scale = max(scale, 0.01)
        fitted_width = image_width * scale
        fitted_height = image_height * scale
        return cls(
            image_width=image_width,
            image_height=image_height,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            scale=scale,
            offset_x=(usable_width - fitted_width) / 2,
            offset_y=(usable_height - fitted_height) / 2,
        )

    def image_to_canvas_point(self, x: float, y: float) -> tuple[float, float]:
        return self.offset_x + x * self.scale, self.offset_y + y * self.scale

    def canvas_to_image_point(self, x: float, y: float) -> tuple[float, float]:
        return (x - self.offset_x) / self.scale, (y - self.offset_y) / self.scale

    def image_to_canvas_rect(
        self,
        rectangle: tuple[int, int, int, int],
    ) -> tuple[float, float, float, float]:
        x1, y1 = self.image_to_canvas_point(rectangle[0], rectangle[1])
        x2, y2 = self.image_to_canvas_point(rectangle[2], rectangle[3])
        return x1, y1, x2, y2

    def contains_canvas_point(self, x: float, y: float) -> bool:
        image_x, image_y = self.canvas_to_image_point(x, y)
        return 0 <= image_x <= self.image_width and 0 <= image_y <= self.image_height


@dataclass(frozen=True)
class AnnotationEdit:
    change: PendingChange


def normalize_drawn_rectangle(
    image_size: tuple[int, int],
    start_point: tuple[float, float],
    end_point: tuple[float, float],
    min_size: int = MIN_RECTANGLE_SIZE,
    validate: bool = True,
) -> tuple[int, int, int, int]:
    rectangle = normalize_rectangle((start_point, end_point))
    clamped = clamp_rectangle(rectangle, image_size[0], image_size[1])
    normalized = normalize_rectangle(((clamped[0], clamped[1]), (clamped[2], clamped[3])))
    if validate and not is_valid_rectangle(normalized, min_size=min_size):
        raise ValueError(
            f"Rectangle must be at least {min_size}x{min_size} image pixels"
        )
    return normalized


def validate_new_box_label(label: str) -> str:
    if not is_approved_label(label):
        raise ValueError(f"New boxes require an approved PIDRay label: {label}")
    return label


def validate_existing_box_label(label: str) -> str:
    if not is_approved_label(label):
        raise ValueError(f"Existing boxes require an approved PIDRay label: {label}")
    return label


def move_rectangle(
    image_size: tuple[int, int],
    rectangle: tuple[int, int, int, int],
    delta: tuple[float, float],
    min_size: int = MIN_RECTANGLE_SIZE,
) -> tuple[int, int, int, int]:
    width = rectangle[2] - rectangle[0]
    height = rectangle[3] - rectangle[1]
    if width < min_size or height < min_size:
        raise ValueError(f"Rectangle must be at least {min_size}x{min_size} image pixels")
    max_x, max_y = image_size
    left = round(rectangle[0] + delta[0])
    top = round(rectangle[1] + delta[1])
    right = left + width
    bottom = top + height
    if left < 0:
        right -= left
        left = 0
    if top < 0:
        bottom -= top
        top = 0
    if right > max_x:
        left -= right - max_x
        right = max_x
    if bottom > max_y:
        top -= bottom - max_y
        bottom = max_y
    moved = (max(0, left), max(0, top), min(max_x, right), min(max_y, bottom))
    if not is_valid_rectangle(moved, min_size=min_size):
        raise ValueError(f"Rectangle must be at least {min_size}x{min_size} image pixels")
    return moved


def resize_rectangle(
    image_size: tuple[int, int],
    rectangle: tuple[int, int, int, int],
    handle: str,
    image_point: tuple[float, float],
    min_size: int = MIN_RECTANGLE_SIZE,
    validate: bool = True,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = rectangle
    px, py = round(image_point[0]), round(image_point[1])
    if handle == "nw":
        candidate = (px, py, x2, y2)
    elif handle == "ne":
        candidate = (x1, py, px, y2)
    elif handle == "sw":
        candidate = (px, y1, x2, py)
    elif handle == "se":
        candidate = (x1, y1, px, py)
    else:
        raise ValueError(f"Unsupported resize handle: {handle}")
    clamped = clamp_rectangle(candidate, image_size[0], image_size[1])
    normalized = normalize_rectangle(((clamped[0], clamped[1]), (clamped[2], clamped[3])))
    if validate and not is_valid_rectangle(normalized, min_size=min_size):
        raise ValueError(f"Rectangle must be at least {min_size}x{min_size} image pixels")
    return normalized


def _find_box(context: SourceImageContext, bbox_id: str) -> EditableBoundingBox:
    for box in context.boxes:
        if box.bbox_id == bbox_id:
            return box
    raise ValueError(f"Bounding box not found: {bbox_id}")


def _temporary_bbox_id(image_id: str, rectangle: tuple[int, int, int, int], label: str) -> str:
    shape = {
        "label": label,
        "points": [[rectangle[0], rectangle[1]], [rectangle[2], rectangle[3]]],
        "shape_type": "rectangle",
        "flags": {},
    }
    return bbox_id_from_shape(image_id, shape)


def stage_annotation_add(
    context: SourceImageContext,
    rectangle: tuple[int, int, int, int],
    label: str,
) -> PendingChange:
    rectangle = normalize_drawn_rectangle(
        context.image_size,
        (rectangle[0], rectangle[1]),
        (rectangle[2], rectangle[3]),
    )
    label = validate_new_box_label(label)
    bbox_id = _temporary_bbox_id(context.image_id, rectangle, label)
    return PendingChange(
        change_id=f"{ANNOTATION_ADD}:{context.image_id}:{bbox_id}",
        target_id=bbox_id,
        operation=ANNOTATION_ADD,
        payload={
            "annotation_path": str(context.annotation_path),
            "image_id": context.image_id,
            "temporary_bbox_id": bbox_id,
            "label": label,
            "points": rectangle,
        },
    )


def stage_annotation_update_box(
    context: SourceImageContext,
    bbox_id: str,
    rectangle: tuple[int, int, int, int],
) -> PendingChange:
    box = _find_box(context, bbox_id)
    rectangle = normalize_drawn_rectangle(
        context.image_size,
        (rectangle[0], rectangle[1]),
        (rectangle[2], rectangle[3]),
    )
    return PendingChange(
        change_id=f"{ANNOTATION_UPDATE_BOX}:{context.image_id}:{bbox_id}",
        target_id=bbox_id,
        operation=ANNOTATION_UPDATE_BOX,
        payload={
            "annotation_path": str(context.annotation_path),
            "image_id": context.image_id,
            "bbox_id": bbox_id,
            "points": rectangle,
            "previous_points": box.points,
        },
    )


def stage_annotation_relabel(
    context: SourceImageContext,
    bbox_id: str,
    label: str,
) -> PendingChange:
    box = _find_box(context, bbox_id)
    label = validate_existing_box_label(label)
    return PendingChange(
        change_id=f"{ANNOTATION_RELABEL}:{context.image_id}:{bbox_id}",
        target_id=bbox_id,
        operation=ANNOTATION_RELABEL,
        payload={
            "annotation_path": str(context.annotation_path),
            "image_id": context.image_id,
            "bbox_id": bbox_id,
            "label": label,
            "previous_label": box.label,
        },
    )


def stage_annotation_delete(
    context: SourceImageContext,
    bbox_id: str,
) -> PendingChange:
    box = _find_box(context, bbox_id)
    return PendingChange(
        change_id=f"{ANNOTATION_DELETE}:{context.image_id}:{bbox_id}",
        target_id=bbox_id,
        operation=ANNOTATION_DELETE,
        payload={
            "annotation_path": str(context.annotation_path),
            "image_id": context.image_id,
            "bbox_id": bbox_id,
            "previous_label": box.label,
            "previous_points": box.points,
        },
    )


def list_partition_source_images(
    dataset_root: str | Path,
    partition_id: str,
) -> tuple[ImageRecord, ...]:
    return tuple(list_partition_image_records(dataset_root, partition_id))


def _find_image_record(
    dataset_root: str | Path,
    partition_id: str,
    image_id: str,
) -> ImageRecord:
    for record in list_partition_source_images(dataset_root, partition_id):
        if record.image_id == image_id:
            return record
    raise ValueError(f"Image not found in {partition_id}: {image_id}")


def _image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def _boxes_from_annotation(
    annotation: dict[str, Any],
    image_id: str,
    selected_bbox_id: str | None,
) -> tuple[tuple[EditableBoundingBox, ...], int, tuple[str, ...]]:
    boxes: list[EditableBoundingBox] = []
    warnings: list[str] = []
    unsupported_count = 0
    shapes = annotation.get("shapes", [])
    if not isinstance(shapes, list):
        return (), 0, ("Annotation JSON 'shapes' field is not a list.",)

    for index, shape in enumerate(shapes):
        if not isinstance(shape, dict) or not is_rectangle_shape(shape):
            unsupported_count += 1
            continue
        try:
            rectangle = normalize_rectangle(shape["points"])
        except (KeyError, ValueError):
            unsupported_count += 1
            continue
        if not is_valid_rectangle(rectangle, min_size=MIN_RECTANGLE_SIZE):
            unsupported_count += 1
            continue
        bbox_id = ensure_bbox_id(shape, image_id)
        label = str(shape.get("label", ""))
        if label and not is_approved_label(label):
            warnings.append(f"Unknown label on {bbox_id}: {label}")
        boxes.append(
            EditableBoundingBox(
                bbox_id=bbox_id,
                shape_index=index,
                label=label,
                points=rectangle,
                is_selected=bbox_id == selected_bbox_id,
            )
        )
    return tuple(boxes), unsupported_count, tuple(warnings)


def load_source_image_context(
    dataset_root: str | Path,
    partition_id: str,
    image_id: str,
    selected_bbox_id: str | None = None,
) -> SourceImageContext:
    record = _find_image_record(dataset_root, partition_id, image_id)
    if not record.image_path.exists():
        raise FileNotFoundError(f"Source image not found: {record.image_path}")
    if not record.annotation_path.exists():
        raise FileNotFoundError(f"Annotation JSON not found: {record.annotation_path}")

    annotation = load_annotation(record.annotation_path, image_id=image_id, assign_ids=True)
    image_size = _image_size(record.image_path)
    boxes, unsupported_count, warnings = _boxes_from_annotation(
        annotation,
        image_id,
        selected_bbox_id,
    )
    if unsupported_count:
        warnings = (
            *warnings,
            f"{unsupported_count} unsupported or invalid shape(s) were preserved.",
        )
    context = SourceImageContext(
        dataset_root=Path(dataset_root),
        partition_id=partition_id,
        image_id=image_id,
        image_path=record.image_path,
        annotation_path=record.annotation_path,
        ordinal=record.ordinal,
        image_size=image_size,
        boxes=boxes,
        unsupported_shape_count=unsupported_count,
        load_warnings=warnings,
        selected_bbox_id=selected_bbox_id,
    )
    return context.with_selection(selected_bbox_id)


def load_source_context_for_crop(
    dataset_root: str | Path,
    partition_id: str,
    crop_id: str,
) -> SourceImageContext:
    crop_context = lookup_source_context(dataset_root, partition_id, crop_id)
    return load_source_image_context(
        dataset_root,
        partition_id,
        str(crop_context["image_id"]),
        selected_bbox_id=str(crop_context["bbox_id"]),
    )


def _point_in_rect(point: tuple[float, float], rect: tuple[int, int, int, int]) -> bool:
    x, y = point
    left, top, right, bottom = rect
    return left <= x <= right and top <= y <= bottom


def _box_area(box: EditableBoundingBox) -> int:
    return max(0, box.points[2] - box.points[0]) * max(0, box.points[3] - box.points[1])


def _distance_sq(
    first: tuple[float, float],
    second: tuple[float, float],
) -> float:
    dx = first[0] - second[0]
    dy = first[1] - second[1]
    return dx * dx + dy * dy


def hit_test_boxes(
    context: SourceImageContext,
    image_point: tuple[float, float],
    previous_click_point: tuple[float, float] | None = None,
    previous_selected_bbox_id: str | None = None,
    repeat_tolerance: float = 4.0,
) -> str | None:
    hits = [
        box
        for box in sorted(context.boxes, key=lambda item: (_box_area(item), item.shape_index))
        if _point_in_rect(image_point, box.points)
    ]
    if not hits:
        return None

    is_repeat = (
        previous_click_point is not None
        and _distance_sq(image_point, previous_click_point) <= repeat_tolerance * repeat_tolerance
    )
    if is_repeat and previous_selected_bbox_id:
        hit_ids = [box.bbox_id for box in hits]
        if previous_selected_bbox_id in hit_ids:
            index = hit_ids.index(previous_selected_bbox_id)
            return hit_ids[(index + 1) % len(hit_ids)]
    return hits[0].bbox_id
