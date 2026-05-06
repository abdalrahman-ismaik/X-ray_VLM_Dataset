from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk

from xray_curation.services.crop_manifest import lookup_source_context


class ImageReviewPanel(ttk.LabelFrame):
    def __init__(self, master) -> None:
        super().__init__(master, text="Source Context", padding=8)
        self.context_var = tk.StringVar(value="Select a crop to view source context.")
        ttk.Label(self, textvariable=self.context_var).grid(row=0, column=0, sticky="w")
        self.columnconfigure(0, weight=1)

    def load_crop(
        self,
        dataset_root: Path,
        partition_id: str,
        crop_id: str,
    ) -> dict | None:
        try:
            context = lookup_source_context(dataset_root, partition_id, crop_id)
        except Exception as exc:
            self.context_var.set(f"Source context unavailable: {exc}")
            return None
        shape = context["shape"]
        self.context_var.set(
            " | ".join(
                (
                    f"image={context['image_id']}",
                    f"label={shape.get('label', '')}",
                    f"bbox={context['bbox_id']}",
                    f"source={context['source_image_path']}",
                )
            )
        )
        return context
