from __future__ import annotations

from xray_curation.domain.labels import (
    APPROVED_FORMAL_LABELS,
    APPROVED_PIDRAY_LABELS,
    available_labels,
    is_approved_label,
    set_custom_labels,
)
from xray_curation.services.label_catalog import (
    add_custom_label,
    load_custom_labels,
    normalize_custom_labels,
)


def test_custom_labels_are_normalized_and_do_not_duplicate_pidray_labels() -> None:
    assert normalize_custom_labels(["Custom_Class", " custom class ", "Box", "Gun"]) == (
        "Custom Class",
    )


def test_custom_labels_are_persisted_and_added_to_runtime_catalog(tmp_path) -> None:
    try:
        custom_labels, added = add_custom_label(tmp_path, "Medical Tool")

        assert added is True
        assert custom_labels == ("Medical Tool",)
        assert load_custom_labels(tmp_path) == ("Medical Tool",)
        assert "Medical Tool" in available_labels()
        assert is_approved_label("Medical Tool") is True
        assert APPROVED_PIDRAY_LABELS[0] in available_labels()
        assert "Gun" in available_labels()
    finally:
        set_custom_labels(())


def test_adding_existing_formal_label_is_noop(tmp_path) -> None:
    try:
        custom_labels, added = add_custom_label(tmp_path, "Box")

        assert added is False
        assert custom_labels == ()
        assert load_custom_labels(tmp_path) == ()

        custom_labels, added = add_custom_label(tmp_path, "Gun")

        assert added is False
        assert custom_labels == ()
        assert load_custom_labels(tmp_path) == ()
        assert "Gun" in APPROVED_FORMAL_LABELS
    finally:
        set_custom_labels(())
