from __future__ import annotations

from xray_curation.services.crop_generator import generate_crops_for_partition
from xray_curation.services.dataset_index import build_dataset_manifest, select_partition


def test_select_partition_contract_shape(small_dataset):
    manifest = build_dataset_manifest(small_dataset, partition_size=4, persist=True)
    selected = select_partition(manifest, "part-0002")

    assert selected["partition_id"] == "part-0002"
    assert selected["image_count"] == 2
    assert [image["image_id"] for image in selected["images"]] == ["image_004", "image_005"]


def test_generate_crops_contract_shape(small_dataset):
    build_dataset_manifest(small_dataset, partition_size=4, persist=True)
    result = generate_crops_for_partition(small_dataset, "part-0002", partition_size=4)
    payload = result.to_dict()

    assert payload["operation"] == "generate_crops"
    assert payload["success"] is True
    assert payload["summary"]["partition_id"] == "part-0002"
    assert payload["summary"]["crops_total"] == 2
    assert len(payload["affected_ids"]) == 2
