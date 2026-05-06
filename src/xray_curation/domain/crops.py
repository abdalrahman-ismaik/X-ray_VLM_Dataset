from __future__ import annotations

import hashlib

CROP_STATUS_ACTIVE = "active"
CROP_STATUS_SOFT_DELETED = "soft_deleted"


def crop_id_for_bbox(image_id: str, bbox_id: str) -> str:
    payload = f"{image_id}|{bbox_id}".encode("utf-8")
    return "crop-" + hashlib.sha1(payload).hexdigest()[:16]
