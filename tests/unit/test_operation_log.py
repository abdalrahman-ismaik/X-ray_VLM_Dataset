from __future__ import annotations

from xray_curation.services.validation import (
    append_operation_log,
    read_operation_log,
    success_result,
)


def test_operation_log_is_append_only_jsonl(tmp_path):
    first = success_result("index", {"image_count": 6})
    second = success_result("refresh_changed_crops", {"changed_image_count": 1})

    append_operation_log(tmp_path / "batch", first)
    append_operation_log(tmp_path / "batch", second)

    entries = read_operation_log(tmp_path / "batch")

    assert [entry["operation"] for entry in entries] == ["index", "refresh_changed_crops"]
    assert entries[0]["result"]["summary"] == {"image_count": 6}
    assert entries[1]["result"]["summary"] == {"changed_image_count": 1}
    assert entries[0]["timestamp"] <= entries[1]["timestamp"]
