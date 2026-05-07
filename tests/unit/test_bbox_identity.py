from __future__ import annotations

from xray_curation.domain.annotations import BBOX_ID_FIELD
from xray_curation.services.annotation_store import (
    assign_missing_bbox_ids,
    load_annotation,
    save_json_atomic,
)


def test_bbox_id_is_created_for_missing_rectangle(small_dataset):
    path = small_dataset / "json" / "image_001.json"
    data = load_annotation(path, image_id="image_001", assign_ids=True, save_if_changed=False)

    assert data["shapes"][0]["flags"][BBOX_ID_FIELD].startswith("bbox-")


def test_bbox_id_survives_relabel(small_dataset):
    path = small_dataset / "json" / "image_002.json"
    data = load_annotation(path, image_id="image_002", assign_ids=True, save_if_changed=True)
    bbox_id = data["shapes"][0]["flags"][BBOX_ID_FIELD]

    data["shapes"][0]["label"] = "Power Bank"
    save_json_atomic(path, data)
    reloaded = load_annotation(path, image_id="image_002", assign_ids=True)

    assert reloaded["shapes"][0]["flags"][BBOX_ID_FIELD] == bbox_id


def test_bbox_id_survives_shape_reorder():
    annotation = {
        "shapes": [
            {"label": "Backpack", "shape_type": "rectangle", "points": [[0, 0], [3, 3]], "flags": {}},
            {"label": "Belt", "shape_type": "rectangle", "points": [[1, 1], [3, 3]], "flags": {}},
        ]
    }
    assigned = assign_missing_bbox_ids(annotation, image_id="image_x")
    annotation["shapes"].reverse()

    assert {
        shape["flags"][BBOX_ID_FIELD] for shape in annotation["shapes"]
    } == set(assigned)


def test_duplicate_rectangle_geometry_gets_unique_bbox_ids():
    annotation = {
        "shapes": [
            {"label": "Backpack", "shape_type": "rectangle", "points": [[0, 0], [3, 3]], "flags": {}},
            {"label": "Belt", "shape_type": "rectangle", "points": [[0, 0], [3, 3]], "flags": {}},
        ]
    }

    assigned = assign_missing_bbox_ids(annotation, image_id="image_x")
    bbox_ids = [shape["flags"][BBOX_ID_FIELD] for shape in annotation["shapes"]]

    assert len(set(bbox_ids)) == 2
    assert bbox_ids == assigned


def test_duplicate_existing_bbox_ids_are_repaired():
    annotation = {
        "shapes": [
            {
                "label": "Backpack",
                "shape_type": "rectangle",
                "points": [[0, 0], [3, 3]],
                "flags": {BBOX_ID_FIELD: "bbox-existing"},
            },
            {
                "label": "Belt",
                "shape_type": "rectangle",
                "points": [[1, 1], [4, 4]],
                "flags": {BBOX_ID_FIELD: "bbox-existing"},
            },
        ]
    }

    repaired = assign_missing_bbox_ids(annotation, image_id="image_x")
    bbox_ids = [shape["flags"][BBOX_ID_FIELD] for shape in annotation["shapes"]]

    assert bbox_ids == ["bbox-existing", "bbox-existing-2"]
    assert repaired == ["bbox-existing-2"]
