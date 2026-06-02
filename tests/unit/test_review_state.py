from __future__ import annotations

from xray_curation.services.review_state import (
    REVIEW_FILTER_ALL,
    REVIEW_FILTER_APPROVED,
    REVIEW_FILTER_UNAPPROVED,
    crop_is_approved,
    filter_crops_by_review_state,
    image_is_approved,
    load_review_state,
    set_review_approval,
    write_review_state,
)


def test_review_state_approval_filters_crops_by_crop_or_image() -> None:
    crops = [
        {"crop_id": "crop-a", "image_id": "image-1"},
        {"crop_id": "crop-b", "image_id": "image-2"},
        {"crop_id": "crop-c", "image_id": "image-3"},
    ]
    state = set_review_approval(
        None,
        partition_id="part-0001",
        crop_ids={"crop-a"},
        image_ids={"image-2"},
        approved=True,
    )

    assert crop_is_approved(crops[0], state) is True
    assert crop_is_approved(crops[1], state) is True
    assert crop_is_approved(crops[2], state) is False
    assert [crop["crop_id"] for crop in filter_crops_by_review_state(crops, state)] == ["crop-c"]
    assert [
        crop["crop_id"]
        for crop in filter_crops_by_review_state(crops, state, REVIEW_FILTER_APPROVED)
    ] == ["crop-a", "crop-b"]
    assert [
        crop["crop_id"] for crop in filter_crops_by_review_state(crops, state, REVIEW_FILTER_ALL)
    ] == ["crop-a", "crop-b", "crop-c"]


def test_review_state_can_unapprove_and_persist(tmp_path) -> None:
    state = set_review_approval(
        None,
        partition_id="part-0001",
        crop_ids={"crop-a", "crop-b"},
        image_ids={"image-1"},
        approved=True,
    )
    state = set_review_approval(
        state,
        partition_id="part-0001",
        crop_ids={"crop-b"},
        image_ids={"image-1"},
        approved=False,
    )

    write_review_state(tmp_path, "part-0001", state)
    loaded = load_review_state(tmp_path, "part-0001")

    assert loaded["approved_crops"] == ["crop-a"]
    assert loaded["approved_images"] == []
    assert image_is_approved("image-1", loaded) is False
    assert crop_is_approved({"crop_id": "crop-a", "image_id": "image-x"}, loaded) is True
    assert crop_is_approved({"crop_id": "crop-b", "image_id": "image-x"}, loaded) is False


def test_review_state_defaults_to_unapproved_when_file_is_missing(tmp_path) -> None:
    state = load_review_state(tmp_path, "part-0001")

    assert state["approved_crops"] == []
    assert state["approved_images"] == []
    assert filter_crops_by_review_state(
        [{"crop_id": "crop-a", "image_id": "image-1"}],
        state,
        REVIEW_FILTER_UNAPPROVED,
    ) == [{"crop_id": "crop-a", "image_id": "image-1"}]
