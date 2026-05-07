from __future__ import annotations

from pathlib import Path

import pytest

from xray_curation.domain.annotations import normalize_clamped_rectangle
from xray_curation.services.annotation_editor import (
    CanvasTransform,
    EditableBoundingBox,
    SourceImageContext,
    hit_test_boxes,
    move_rectangle,
    normalize_drawn_rectangle,
    resize_rectangle,
)


def _context(boxes: tuple[EditableBoundingBox, ...]) -> SourceImageContext:
    return SourceImageContext(
        dataset_root=Path("dataset"),
        partition_id="part-0001",
        image_id="image_000",
        image_path=Path("image_000.ppm"),
        annotation_path=Path("image_000.json"),
        ordinal=0,
        image_size=(100, 50),
        boxes=boxes,
    )


def test_canvas_transform_fits_and_round_trips_points() -> None:
    transform = CanvasTransform.fit((100, 50), (200, 200))

    assert transform.scale == pytest.approx(2.0)
    assert transform.offset_x == pytest.approx(0.0)
    assert transform.offset_y == pytest.approx(50.0)
    assert transform.image_to_canvas_point(25, 10) == pytest.approx((50, 70))
    assert transform.canvas_to_image_point(50, 70) == pytest.approx((25, 10))


def test_normalize_clamped_rectangle_clamps_to_image_bounds() -> None:
    assert normalize_clamped_rectangle(((-2, -3), (8, 6)), 10, 10) == (0, 0, 8, 6)


def test_normalize_clamped_rectangle_rejects_tiny_boxes() -> None:
    with pytest.raises(ValueError, match="at least 2x2"):
        normalize_clamped_rectangle(((1, 1), (1, 3)), 10, 10)


def test_hit_test_boxes_uses_shape_order_and_cycles_repeated_clicks() -> None:
    context = _context(
        (
            EditableBoundingBox("bbox-a", 0, "Backpack", (0, 0, 20, 20)),
            EditableBoundingBox("bbox-b", 1, "Belt", (5, 5, 25, 25)),
            EditableBoundingBox("bbox-c", 2, "Box", (40, 40, 80, 45)),
        )
    )

    first = hit_test_boxes(context, (10, 10))
    second = hit_test_boxes(
        context,
        (11, 10),
        previous_click_point=(10, 10),
        previous_selected_bbox_id=first,
        repeat_tolerance=4,
    )
    third = hit_test_boxes(
        context,
        (11, 10),
        previous_click_point=(11, 10),
        previous_selected_bbox_id=second,
        repeat_tolerance=4,
    )

    assert first == "bbox-a"
    assert second == "bbox-b"
    assert third == "bbox-a"
    assert hit_test_boxes(context, (99, 99)) is None


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    (
        ((10, 5), (80, 40), (10, 5, 80, 40)),
        ((80, 40), (10, 5), (10, 5, 80, 40)),
        ((10, 40), (80, 5), (10, 5, 80, 40)),
        ((80, 5), (10, 40), (10, 5, 80, 40)),
    ),
)
def test_normalize_drawn_rectangle_accepts_all_drag_directions(
    start: tuple[int, int],
    end: tuple[int, int],
    expected: tuple[int, int, int, int],
) -> None:
    assert normalize_drawn_rectangle((100, 50), start, end) == expected


@pytest.mark.parametrize(
    ("start", "end"),
    (
        ((5, 5), (6, 6)),
        ((20, 20), (20, 30)),
        ((-10, -10), (-1, -1)),
    ),
)
def test_normalize_drawn_rectangle_rejects_invalid_new_boxes(
    start: tuple[int, int],
    end: tuple[int, int],
) -> None:
    with pytest.raises(ValueError, match="at least 2x2"):
        normalize_drawn_rectangle((100, 50), start, end)


def test_move_rectangle_clamps_to_image_bounds() -> None:
    assert move_rectangle((100, 50), (10, 10, 30, 30), (80, 80)) == (80, 30, 100, 50)
    assert move_rectangle((100, 50), (10, 10, 30, 30), (-80, -80)) == (0, 0, 20, 20)


def test_resize_rectangle_updates_selected_handle_and_clamps() -> None:
    assert resize_rectangle((100, 50), (10, 10, 30, 30), "se", (50, 45)) == (10, 10, 50, 45)
    assert resize_rectangle((100, 50), (10, 10, 30, 30), "nw", (-5, -5)) == (0, 0, 30, 30)


def test_resize_rectangle_rejects_tiny_result() -> None:
    with pytest.raises(ValueError, match="at least 2x2"):
        resize_rectangle((100, 50), (10, 10, 30, 30), "se", (11, 11))
