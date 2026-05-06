from __future__ import annotations

from xray_curation.services.validation import failure_result, success_result


def test_success_result_serializes_summary():
    result = success_result("index", {"image_count": 6}, affected_ids=("part-0001",))

    assert result.to_dict() == {
        "operation": "index",
        "success": True,
        "summary": {"image_count": 6},
        "warnings": [],
        "errors": [],
        "affected_ids": ["part-0001"],
    }


def test_failure_result_serializes_errors():
    result = failure_result("generate_crops", ("missing annotation",))

    assert result.success is False
    assert result.to_dict()["errors"] == ["missing annotation"]
