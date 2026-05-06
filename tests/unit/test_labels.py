from __future__ import annotations

from xray_curation.domain.labels import (
    APPROVED_PIDRAY_LABELS,
    canonical_label,
    is_approved_label,
    label_requires_standardization,
    normalize_label_text,
)


def test_approved_pidray_labels_use_spaces_not_underscores():
    assert "Electrical Device" in APPROVED_PIDRAY_LABELS
    assert "Electrical_Device" not in APPROVED_PIDRAY_LABELS
    assert all("_" not in label for label in APPROVED_PIDRAY_LABELS)
    assert all(is_approved_label(label) for label in APPROVED_PIDRAY_LABELS)


def test_underscore_and_case_aliases_resolve_to_approved_labels():
    assert normalize_label_text("Electrical_Device") == "Electrical Device"
    assert canonical_label("Electrical_Device") == "Electrical Device"
    assert canonical_label("mobile_phone") == "Mobile Phone"
    assert canonical_label("  laptop_power_adapter ") == "Laptop Power Adapter"
    assert label_requires_standardization("Glass_Bottle") is True
    assert label_requires_standardization("Glass Bottle") is False


def test_unknown_label_is_reviewable_not_auto_mapped():
    assert canonical_label("mystery object") is None
