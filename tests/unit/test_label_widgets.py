from __future__ import annotations

from xray_curation.gui.label_widgets import (
    label_dropdown_values,
    matching_approved_labels,
    selected_approved_label,
    should_post_label_dropdown,
)


def test_matching_approved_labels_filters_by_typed_prefix() -> None:
    assert matching_approved_labels("lap")[:3] == (
        "Laptop",
        "Laptop Charger",
        "Laptop Power Adapter",
    )


def test_matching_approved_labels_matches_text_inside_label() -> None:
    assert matching_approved_labels("device") == (
        "Electrical Device",
        "Electronic Device",
    )


def test_selected_approved_label_accepts_case_and_underscore_variants() -> None:
    assert selected_approved_label("mobile phone") == "Mobile Phone"
    assert selected_approved_label("Electrical_Device") == "Electrical Device"


def test_selected_approved_label_rejects_ambiguous_partial_text() -> None:
    assert selected_approved_label("device") is None


def test_dropdown_posts_only_for_typed_queries_with_matches() -> None:
    assert should_post_label_dropdown("lap", ("Laptop",)) is True
    assert should_post_label_dropdown("l", ("Laptop", "Lighter")) is True
    assert should_post_label_dropdown("", ("Laptop",)) is False
    assert should_post_label_dropdown("missing", ()) is False


def test_label_dropdown_values_can_show_all_labels_when_forced() -> None:
    labels = ("Backpack", "Belt", "Box")

    assert label_dropdown_values("", labels) == labels
    assert label_dropdown_values("bo", labels) == ("Box",)
    assert label_dropdown_values("Box", labels, show_all=True) == labels
