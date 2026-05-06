from __future__ import annotations

from xray_curation.domain.annotations import BBOX_ID_FIELD, rectangle_shapes
from xray_curation.services.annotation_store import load_annotation, load_json, save_json_atomic


def test_annotation_json_preserves_unknown_fields(small_dataset):
    path = small_dataset / "json" / "image_000.json"
    data = load_annotation(path, image_id="image_000", assign_ids=True, save_if_changed=True)
    bbox_id = data["shapes"][0]["flags"][BBOX_ID_FIELD]

    data["shapes"][0]["label"] = "Belt"
    save_json_atomic(path, data)

    reloaded = load_json(path)
    assert reloaded["fixture_meta"] == "preserve"
    assert reloaded["shapes"][0]["extra_field"] == "keep"
    assert reloaded["shapes"][0]["flags"][BBOX_ID_FIELD] == bbox_id


def test_invalid_shapes_are_skipped_without_ids():
    annotation = {
        "shapes": [
            {"label": "Bad", "shape_type": "rectangle", "points": [[1, 2]]},
            {"label": "Poly", "shape_type": "polygon", "points": [[0, 0], [1, 1], [2, 0]]},
        ]
    }

    assert rectangle_shapes(annotation, image_id="image_x", assign_ids=True) == []
