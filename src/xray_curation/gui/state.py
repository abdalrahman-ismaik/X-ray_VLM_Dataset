from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from xray_curation.domain.operations import PendingChange


@dataclass
class CurationState:
    dataset_root: Path | None = None
    partition_id: str | None = None
    crop_manifest: dict[str, Any] | None = None
    selected_crop_id: str | None = None
    selected_image_id: str | None = None
    selected_bbox_id: str | None = None
    active_source_image_id: str | None = None
    annotation_editor_mode: str = "browse"
    worker_status: str = "idle"
    worker_progress: float = 0
    pending_changes: list[PendingChange] = field(default_factory=list)

    def pending_summary(self) -> dict[str, int]:
        summary: dict[str, int] = {}
        for change in self.pending_changes:
            summary[change.operation] = summary.get(change.operation, 0) + 1
        return summary
