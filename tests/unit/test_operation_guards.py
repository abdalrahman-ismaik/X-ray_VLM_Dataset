from __future__ import annotations

from xray_curation.domain.operations import PendingChange
from xray_curation.services.validation import ensure_no_unsaved_changes, has_unsaved_changes


def test_guard_allows_utility_when_no_pending_changes():
    result = ensure_no_unsaved_changes([], "missing crop detection")

    assert result.success is True
    assert result.summary == {"operation": "missing crop detection", "pending_count": 0}
    assert has_unsaved_changes([]) is False


def test_guard_blocks_utility_when_pending_changes_exist():
    pending = [
        PendingChange(
            change_id="relabel:crop-1",
            target_id="crop-1",
            operation="relabel",
            payload={"label": "Belt"},
        )
    ]

    result = ensure_no_unsaved_changes(pending, "external moved-crop import")

    assert result.success is False
    assert result.summary["pending_count"] == 1
    assert "Save or cancel" in result.errors[0]
    assert has_unsaved_changes(pending) is True
