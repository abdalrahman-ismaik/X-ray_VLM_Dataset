from xray_curation.gui.crop_browser import (
    browser_card_size,
    browser_grid_column_count,
    browser_page_count,
    browser_page_for_item_index,
    browser_page_slice,
    browser_grid_position,
    clamp_browser_page,
    crop_id_after_navigation,
    crop_row_to_select_after_refresh,
    crops_for_active_image,
    navigation_anchor_after_crop_selection,
    unique_crop_row_id,
)


def test_unique_crop_row_id_keeps_duplicate_crop_ids_insertable() -> None:
    seen: dict[str, int] = {}

    assert unique_crop_row_id("crop-a", seen) == "crop-a"
    assert unique_crop_row_id("crop-a", seen) == "crop-a::1"
    assert unique_crop_row_id("crop-b", seen) == "crop-b"
    assert unique_crop_row_id("crop-a", seen) == "crop-a::2"


def test_browser_grid_column_count_uses_vertical_grid() -> None:
    assert browser_grid_column_count(100) == 1
    assert browser_grid_column_count(300) >= 2


def test_browser_grid_position_wraps_rows() -> None:
    assert browser_grid_position(0, columns=2) == (10, 10)
    assert browser_grid_position(1, columns=2) == (152, 10)
    assert browser_grid_position(2, columns=2) == (10, 132)


def test_browser_card_size_zoom_changes_grid_density() -> None:
    small_width, _ = browser_card_size(70)
    large_width, _ = browser_card_size(180)

    assert large_width > small_width
    assert browser_grid_column_count(600, card_width=large_width) < browser_grid_column_count(
        600,
        card_width=small_width,
    )


def test_browser_page_count_keeps_120_items_per_page() -> None:
    assert browser_page_count(0) == 0
    assert browser_page_count(120) == 1
    assert browser_page_count(121) == 2
    assert browser_page_count(240) == 2
    assert browser_page_count(241) == 3


def test_browser_page_slice_returns_current_page_bounds() -> None:
    assert browser_page_slice(0, 241) == (0, 120)
    assert browser_page_slice(1, 241) == (120, 240)
    assert browser_page_slice(2, 241) == (240, 241)


def test_browser_page_helpers_clamp_and_find_item_page() -> None:
    assert clamp_browser_page(-3, 241) == 0
    assert clamp_browser_page(9, 241) == 2
    assert browser_page_for_item_index(0, 241) == 0
    assert browser_page_for_item_index(119, 241) == 0
    assert browser_page_for_item_index(120, 241) == 1
    assert browser_page_for_item_index(240, 241) == 2
    assert browser_page_for_item_index(241, 241) is None


def test_crop_row_to_select_keeps_previous_visible_crop() -> None:
    assert (
        crop_row_to_select_after_refresh(
            "crop-b",
            ["row-a", "row-b"],
            {"row-a": "crop-a", "row-b": "crop-b"},
        )
        == "row-b"
    )


def test_crop_row_to_select_can_avoid_first_row_fallback_after_save() -> None:
    assert (
        crop_row_to_select_after_refresh(
            "crop-moved-out-of-filter",
            ["row-a", "row-b"],
            {"row-a": "crop-a", "row-b": "crop-b"},
            select_first=False,
        )
        is None
    )


def test_active_image_items_list_ignores_class_filter() -> None:
    manifest = {
        "crops": [
            {"crop_id": "crop-a", "image_id": "image-1", "label": "Box", "status": "active"},
            {"crop_id": "crop-b", "image_id": "image-1", "label": "Wallet", "status": "active"},
            {"crop_id": "crop-c", "image_id": "image-2", "label": "Box", "status": "active"},
        ]
    }

    crops = crops_for_active_image(
        manifest,
        "image-1",
        status="active",
    )

    assert [crop["crop_id"] for crop in crops] == ["crop-a", "crop-b"]


def test_crop_navigation_uses_filtered_crop_sequence() -> None:
    crops = [
        {"crop_id": "crop-a"},
        {"crop_id": "crop-b"},
        {"crop_id": "crop-c"},
    ]

    assert crop_id_after_navigation("crop-b", crops, 1) == "crop-c"
    assert crop_id_after_navigation("crop-b", crops, -1) == "crop-a"
    assert crop_id_after_navigation("crop-missing", crops, 1) == "crop-a"


def test_navigation_anchor_stays_on_filtered_class_when_selecting_other_image_item() -> None:
    box_crops = [
        {"crop_id": "box-crop-1", "label": "Box"},
        {"crop_id": "box-crop-2", "label": "Box"},
    ]

    anchor = navigation_anchor_after_crop_selection(
        "box-crop-1",
        "wallet-crop-1",
        box_crops,
    )

    assert anchor == "box-crop-1"
    assert crop_id_after_navigation(anchor, box_crops, 1) == "box-crop-2"


def test_navigation_anchor_updates_when_selected_item_is_in_filtered_class() -> None:
    box_crops = [
        {"crop_id": "box-crop-1", "label": "Box"},
        {"crop_id": "box-crop-2", "label": "Box"},
    ]

    assert (
        navigation_anchor_after_crop_selection("box-crop-1", "box-crop-2", box_crops)
        == "box-crop-2"
    )
