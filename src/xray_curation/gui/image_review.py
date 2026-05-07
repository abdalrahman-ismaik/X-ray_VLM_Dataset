from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk

from xray_curation.domain.annotations import normalize_rectangle
from xray_curation.services.crop_manifest import lookup_source_context


class ImageReviewPanel(ttk.Frame):
    def __init__(self, master) -> None:
        super().__init__(master, padding=8)
        self.context_var = tk.StringVar(value="Select a crop to preview the source image.")
        self._context: dict | None = None
        self._source_image = None
        self._crop_image = None
        self._source_photo = None
        self._crop_photo = None
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, textvariable=self.context_var).grid(row=0, column=0, sticky="w")
        ttk.Button(header, text="Open Full Preview", command=self.open_full_source).grid(
            row=0,
            column=1,
            padx=(8, 0),
        )

        panes = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        panes.grid(row=1, column=0, sticky="nsew", pady=(8, 0))

        source_frame = ttk.LabelFrame(panes, text="Source Image")
        crop_frame = ttk.LabelFrame(panes, text="Selected Crop")
        panes.add(source_frame, weight=4)
        panes.add(crop_frame, weight=1)

        source_frame.columnconfigure(0, weight=1)
        source_frame.rowconfigure(0, weight=1)
        crop_frame.columnconfigure(0, weight=1)
        crop_frame.rowconfigure(0, weight=1)

        self.source_canvas = tk.Canvas(source_frame, background="#121212", highlightthickness=0)
        self.crop_canvas = tk.Canvas(crop_frame, background="#121212", highlightthickness=0)
        self.source_canvas.grid(row=0, column=0, sticky="nsew")
        self.crop_canvas.grid(row=0, column=0, sticky="nsew")
        self.source_canvas.bind("<Configure>", lambda _event: self._render_source())
        self.crop_canvas.bind("<Configure>", lambda _event: self._render_crop())

    def clear(self, message: str = "Select a crop to preview the source image.") -> None:
        self._context = None
        self._source_image = None
        self._crop_image = None
        self.context_var.set(message)
        self.source_canvas.delete("all")
        self.crop_canvas.delete("all")

    def load_crop(
        self,
        dataset_root: Path,
        partition_id: str,
        crop_id: str,
    ) -> dict | None:
        try:
            from PIL import Image, ImageDraw
            context = lookup_source_context(dataset_root, partition_id, crop_id)
            source_image = Image.open(context["source_image_path"]).convert("RGB")
            crop_path = Path(context["crop"].get("crop_path", ""))
            crop_image = Image.open(crop_path).convert("RGB") if crop_path.is_file() else None
            shape = context["shape"]
            box = normalize_rectangle(shape["points"])
            draw = ImageDraw.Draw(source_image)
            width = max(2, round(max(source_image.size) / 180))
            draw.rectangle(box, outline="#ff3b30", width=width)
        except Exception as exc:
            self.clear(f"Source context unavailable: {exc}")
            return None

        self._context = context
        self._source_image = source_image
        self._crop_image = crop_image
        self.context_var.set(
            " | ".join(
                (
                    f"image={context['image_id']}",
                    f"label={shape.get('label', '')}",
                    f"bbox={context['bbox_id']}",
                )
            )
        )
        self.after_idle(self._render_source)
        self.after_idle(self._render_crop)
        return context

    def _fit_image(self, image, width: int, height: int):
        from PIL import Image

        if width <= 2 or height <= 2:
            width, height = 640, 480
        scale = min(width / image.width, height / image.height)
        scale = max(scale, 0.01)
        new_size = (
            max(1, int(image.width * scale)),
            max(1, int(image.height * scale)),
        )
        return image.resize(new_size, Image.Resampling.LANCZOS)

    def _render_source(self) -> None:
        self.source_canvas.delete("all")
        if self._source_image is None:
            self._draw_empty(self.source_canvas, "No source image selected.")
            return
        self._source_photo = self._render_to_canvas(self.source_canvas, self._source_image)

    def _render_crop(self) -> None:
        self.crop_canvas.delete("all")
        if self._crop_image is None:
            self._draw_empty(self.crop_canvas, "No crop image available.")
            return
        self._crop_photo = self._render_to_canvas(self.crop_canvas, self._crop_image)

    def _render_to_canvas(self, canvas: tk.Canvas, image):
        from PIL import ImageTk

        width = max(canvas.winfo_width(), 1)
        height = max(canvas.winfo_height(), 1)
        fitted = self._fit_image(image, width, height)
        photo = ImageTk.PhotoImage(fitted)
        canvas.create_image(width // 2, height // 2, image=photo, anchor=tk.CENTER)
        return photo

    def _draw_empty(self, canvas: tk.Canvas, message: str) -> None:
        width = max(canvas.winfo_width(), 320)
        height = max(canvas.winfo_height(), 160)
        canvas.create_text(
            width // 2,
            height // 2,
            text=message,
            fill="#f0f0f0",
            anchor=tk.CENTER,
        )

    def open_full_source(self) -> None:
        if self._source_image is None:
            return
        window = tk.Toplevel(self)
        window.title("Source Image Preview")
        window.geometry("1200x800")
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)
        canvas = tk.Canvas(window, background="#121212", highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        holder = {"photo": None}

        def render(_event=None) -> None:
            canvas.delete("all")
            holder["photo"] = self._render_to_canvas(canvas, self._source_image)

        canvas.bind("<Configure>", render)
        window.after_idle(render)
