from __future__ import annotations

from xray_curation.domain.crops import crop_id_for_bbox


def test_crop_id_depends_on_image_and_bbox_not_label():
    first = crop_id_for_bbox("image_001", "bbox-abc")
    after_relabel = crop_id_for_bbox("image_001", "bbox-abc")
    other_box = crop_id_for_bbox("image_001", "bbox-other")

    assert first == after_relabel
    assert first != other_box
