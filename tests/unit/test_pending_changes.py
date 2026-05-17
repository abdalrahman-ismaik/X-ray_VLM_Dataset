from __future__ import annotations

from xray_curation.domain.annotations import BBOX_ID_FIELD
from xray_curation.services.annotation_store import (
    add_pending_change,
    cancel_pending_change,
    commit_pending_changes,
    load_json,
    stage_move_group_change,
    stage_relabel_change,
    stage_rename_change,
    stage_restore_change,
    stage_soft_delete_change,
)
from xray_curation.services.crop_generator import generate_crops_for_partition
from xray_curation.services.crop_manifest import read_crop_manifest
from xray_curation.services.dataset_index import build_dataset_manifest


def _first_crop(small_dataset):
    build_dataset_manifest(small_dataset, partition_size=4, persist=True)
    result = generate_crops_for_partition(small_dataset, "part-0001", partition_size=4)
    assert result.success is True
    return read_crop_manifest(small_dataset, "part-0001")["crops"][0]


def test_pending_changes_can_be_staged_and_cancelled(small_dataset):
    crop = _first_crop(small_dataset)
    pending = []
    pending = add_pending_change(pending, stage_relabel_change(crop, "Belt"))
    pending = add_pending_change(pending, stage_rename_change(crop, "reviewed crop"))

    assert [change.operation for change in pending] == ["relabel", "rename"]

    pending = cancel_pending_change(pending, f"relabel:{crop['crop_id']}")

    assert [change.operation for change in pending] == ["rename"]


def test_commit_relabel_rename_move_soft_delete_and_restore(small_dataset):
    crop = _first_crop(small_dataset)
    pending = [
        stage_relabel_change(crop, "Belt"),
        stage_rename_change(crop, "reviewed crop"),
        stage_move_group_change(crop, "Laptop"),
        stage_soft_delete_change(crop),
        stage_restore_change(crop),
    ]

    result = commit_pending_changes(pending)

    assert result.success is True
    assert result.summary == {
        "changes_applied": 5,
        "files_written": 1,
        "affected_image_ids": [crop["image_id"]],
    }

    annotation = load_json(crop["annotation_path"])
    shape = annotation["shapes"][0]
    assert shape["label"] == "Laptop"
    assert shape["flags"]["curation_display_name"] == "reviewed crop"
    assert shape["flags"]["curation_status"] == "active"
    assert shape["flags"][BBOX_ID_FIELD] == crop["bbox_id"]


def test_commit_crop_level_change_reports_affected_image_for_refresh(small_dataset):
    crop = _first_crop(small_dataset)
    pending = [stage_relabel_change(crop, "Wallet")]

    result = commit_pending_changes(pending)

    assert result.success is True
    assert result.summary["affected_image_ids"] == [crop["image_id"]]
