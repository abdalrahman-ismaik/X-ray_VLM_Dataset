from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from xray_curation.domain.labels import APPROVED_PIDRAY_LABELS
from xray_curation.domain.operations import PendingChange
from xray_curation.gui.label_widgets import (
    LabelAutocompleteEntry,
    selected_approved_label,
)
from xray_curation.gui.state import CurationState
from xray_curation.services.annotation_editor import (
    CanvasTransform,
    EditableBoundingBox,
    SourceImageContext,
    hit_test_boxes,
    list_partition_source_images,
    load_source_context_for_crop,
    load_source_image_context,
    move_rectangle,
    normalize_drawn_rectangle,
    resize_rectangle,
    stage_annotation_add,
    stage_annotation_delete,
    stage_annotation_relabel,
    stage_annotation_update_box,
)

HANDLE_SIZE = 6
MIN_VIEWER_ZOOM = 1.0
MAX_VIEWER_ZOOM = 8.0
VIEWER_ZOOM_STEP = 1.15


def clamp_viewer_zoom(value: float) -> float:
    return min(MAX_VIEWER_ZOOM, max(MIN_VIEWER_ZOOM, value))


def _viewer_scale_and_base_offset(
    image_size: tuple[int, int],
    canvas_size: tuple[int, int],
    zoom_factor: float,
) -> tuple[float, float, float]:
    fit = CanvasTransform.fit(image_size, canvas_size)
    zoom = clamp_viewer_zoom(zoom_factor)
    scale = fit.scale * zoom
    image_width, image_height = image_size
    canvas_width, canvas_height = canvas_size
    fitted_width = image_width * scale
    fitted_height = image_height * scale
    return scale, (canvas_width - fitted_width) / 2, (canvas_height - fitted_height) / 2


def clamp_viewer_pan(
    image_size: tuple[int, int],
    canvas_size: tuple[int, int],
    zoom_factor: float,
    pan_offset: tuple[float, float],
) -> tuple[float, float]:
    scale, base_x, base_y = _viewer_scale_and_base_offset(image_size, canvas_size, zoom_factor)
    image_width, image_height = image_size
    canvas_width, canvas_height = canvas_size
    fitted_width = image_width * scale
    fitted_height = image_height * scale
    offset_x = base_x + pan_offset[0]
    offset_y = base_y + pan_offset[1]
    if fitted_width <= canvas_width:
        offset_x = base_x
    else:
        offset_x = min(0, max(canvas_width - fitted_width, offset_x))
    if fitted_height <= canvas_height:
        offset_y = base_y
    else:
        offset_y = min(0, max(canvas_height - fitted_height, offset_y))
    return offset_x - base_x, offset_y - base_y


def zoomed_canvas_transform(
    image_size: tuple[int, int],
    canvas_size: tuple[int, int],
    zoom_factor: float,
    pan_offset: tuple[float, float] = (0, 0),
) -> CanvasTransform:
    scale, base_x, base_y = _viewer_scale_and_base_offset(image_size, canvas_size, zoom_factor)
    pan_x, pan_y = clamp_viewer_pan(image_size, canvas_size, zoom_factor, pan_offset)
    return CanvasTransform(
        image_width=image_size[0],
        image_height=image_size[1],
        canvas_width=canvas_size[0],
        canvas_height=canvas_size[1],
        scale=scale,
        offset_x=base_x + pan_x,
        offset_y=base_y + pan_y,
    )


def viewer_pan_for_anchor(
    image_size: tuple[int, int],
    canvas_size: tuple[int, int],
    zoom_factor: float,
    image_point: tuple[float, float],
    canvas_point: tuple[float, float],
) -> tuple[float, float]:
    scale, base_x, base_y = _viewer_scale_and_base_offset(image_size, canvas_size, zoom_factor)
    pan_offset = (
        canvas_point[0] - image_point[0] * scale - base_x,
        canvas_point[1] - image_point[1] * scale - base_y,
    )
    return clamp_viewer_pan(image_size, canvas_size, zoom_factor, pan_offset)

ANNOTATION_EDITOR_REQUIRED_GUIDANCE_TERMS: tuple[str, ...] = (
    "selected partition",
    "source-image browsing",
    "crop selection",
    "source context",
    "overlapping",
    "Draw Box",
    "approved PIDRay label",
    "move",
    "resize",
    "Relabel Box",
    "Delete Box",
    "Cancel Box Edit",
    "Save Pending",
    "atomic",
    "affected-image-only crop refresh",
)

ANNOTATION_EDITOR_GUIDANCE_STEPS: tuple[str, ...] = (
    "Index Dataset, choose the selected partition, then use Preview for source-image browsing before or after crops exist.",
    "Crop selection opens the source context and highlights the matching bounding box.",
    "Click a box to select it; repeated clicks on overlapping boxes cycle through them in annotation order.",
    "Use Draw Box with an approved PIDRay label to stage a new rectangle.",
    "Drag the selected box body to move it, or drag a corner handle to resize it.",
    "Use Relabel Box, Delete Box, or Cancel Box Edit for selected-box pending edits.",
    "Use one shared Save Pending action for crop corrections and annotation edits.",
    "Save Pending writes annotation JSON atomically and performs affected-image-only crop refresh when crops exist.",
)

ANNOTATION_EDITOR_GUIDANCE_TEXT = " ".join(ANNOTATION_EDITOR_GUIDANCE_STEPS)
EMPTY_STATE_GUIDANCE = (
    "Index Dataset, select a partition, then open a source image. "
    "Use Draw Box and Save Pending for annotation edits."
)
NO_SELECTION_GUIDANCE = "No box selected. Select a box, draw box, or save pending edits when ready."


class AnnotationEditorPanel(ttk.Frame):
    def __init__(
        self,
        master,
        state: CurationState,
        on_stage: Callable[[PendingChange], None] | None = None,
        on_pending_changed: Callable[[], None] | None = None,
        on_bbox_selected: Callable[[SourceImageContext, str | None], None] | None = None,
        on_previous_crop: Callable[[], bool] | None = None,
        on_next_crop: Callable[[], bool] | None = None,
    ) -> None:
        super().__init__(master, padding=8)
        self.state = state
        self._on_stage = on_stage
        self._on_pending_changed = on_pending_changed
        self._on_bbox_selected = on_bbox_selected
        self._on_previous_crop = on_previous_crop
        self._on_next_crop = on_next_crop
        self.status_var = tk.StringVar(value=EMPTY_STATE_GUIDANCE)
        self.details_var = tk.StringVar(value=NO_SELECTION_GUIDANCE)
        self.image_position_var = tk.StringVar(value="")
        self.draw_label_var = tk.StringVar(value=APPROVED_PIDRAY_LABELS[0])
        self.zoom_status_var = tk.StringVar(value="100%")
        self._records = []
        self._current_index = 0
        self._context: SourceImageContext | None = None
        self._image: Image.Image | None = None
        self._photo = None
        self._transform: CanvasTransform | None = None
        self._last_canvas_click: tuple[float, float] | None = None
        self._draw_start_image: tuple[float, float] | None = None
        self._draw_preview_rect: tuple[int, int, int, int] | None = None
        self._edit_start_image: tuple[float, float] | None = None
        self._edit_start_box: EditableBoundingBox | None = None
        self._edit_preview_rect: tuple[int, int, int, int] | None = None
        self._edit_kind: str | None = None
        self._edit_handle: str | None = None
        self._edit_dragged = False
        self._zoom_factor = 1.0
        self._pan_offset: tuple[float, float] = (0, 0)
        self._pan_start_canvas: tuple[float, float] | None = None
        self._pan_start_offset: tuple[float, float] | None = None
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        navigation = ttk.Frame(self)
        navigation.grid(row=0, column=0, sticky="ew")
        navigation.columnconfigure(3, weight=1)
        ttk.Button(navigation, text="Previous Crop", command=self.select_previous_crop_or_image).grid(
            row=0,
            column=0,
            sticky="w",
        )
        ttk.Button(navigation, text="Next Crop", command=self.select_next_crop_or_image).grid(
            row=0,
            column=1,
            padx=(4, 0),
            sticky="w",
        )
        ttk.Label(navigation, textvariable=self.image_position_var).grid(
            row=0,
            column=2,
            padx=(12, 0),
            sticky="w",
        )
        ttk.Button(navigation, text="Reset View", command=self.reset_view).grid(
            row=0,
            column=4,
            padx=(8, 0),
            sticky="e",
        )
        ttk.Label(navigation, textvariable=self.zoom_status_var, width=6).grid(
            row=0,
            column=5,
            padx=(4, 0),
            sticky="e",
        )
        ttk.Button(navigation, text="Open Full Preview", command=self.open_full_source).grid(
            row=0,
            column=6,
            padx=(4, 0),
            sticky="e",
        )

        editor_tools = ttk.Frame(self)
        editor_tools.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        editor_tools.columnconfigure(8, weight=1)
        ttk.Button(editor_tools, text="Draw Box", command=self.enter_draw_mode).grid(
            row=0,
            column=0,
            sticky="w",
        )
        ttk.Label(editor_tools, text="Label").grid(row=0, column=1, padx=(8, 0), sticky="w")
        self.label_combo = LabelAutocompleteEntry(
            editor_tools,
            variable=self.draw_label_var,
            width=22,
        )
        self.label_combo.grid(row=0, column=2, padx=(4, 0), sticky="w")
        ttk.Button(editor_tools, text="Cancel Draw", command=self.cancel_draw_mode).grid(
            row=0,
            column=3,
            padx=(4, 0),
            sticky="w",
        )
        ttk.Button(editor_tools, text="Relabel Box", command=self.stage_selected_relabel).grid(
            row=0,
            column=4,
            padx=(10, 0),
            sticky="w",
        )
        ttk.Button(editor_tools, text="Delete Box", command=self.stage_selected_delete).grid(
            row=0,
            column=5,
            padx=(4, 0),
            sticky="w",
        )
        ttk.Button(editor_tools, text="Cancel Box Edit", command=self.cancel_selected_pending).grid(
            row=0,
            column=6,
            padx=(4, 0),
            sticky="w",
        )

        status_label = ttk.Label(self, textvariable=self.status_var)
        status_label.grid(
            row=2,
            column=0,
            sticky="ew",
            pady=(8, 4),
        )
        status_label.bind(
            "<Configure>",
            lambda event: status_label.configure(wraplength=max(240, event.width - 8)),
        )

        self.canvas = tk.Canvas(self, background="#111111", highlightthickness=0)
        self.canvas.grid(row=3, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _event: self._render())
        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<MouseWheel>", self._on_canvas_mousewheel)
        self.canvas.bind("<Button-4>", self._on_canvas_mousewheel)
        self.canvas.bind("<Button-5>", self._on_canvas_mousewheel)
        self.canvas.bind("<ButtonPress-2>", self._on_pan_press)
        self.canvas.bind("<B2-Motion>", self._on_pan_drag)
        self.canvas.bind("<ButtonRelease-2>", self._on_pan_release)
        self.canvas.bind("<ButtonPress-3>", self._on_pan_press)
        self.canvas.bind("<B3-Motion>", self._on_pan_drag)
        self.canvas.bind("<ButtonRelease-3>", self._on_pan_release)

        details = ttk.LabelFrame(self, text="Selected Bounding Box", padding=8)
        details.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        details.columnconfigure(0, weight=1)
        details_label = ttk.Label(details, textvariable=self.details_var)
        details_label.grid(row=0, column=0, sticky="ew")
        details_label.bind(
            "<Configure>",
            lambda event: details_label.configure(wraplength=max(240, event.width - 8)),
        )

    def clear(self, message: str = EMPTY_STATE_GUIDANCE) -> None:
        self._records = []
        self._context = None
        self._image = None
        self._photo = None
        self._transform = None
        self._last_canvas_click = None
        self._draw_start_image = None
        self._draw_preview_rect = None
        self._reset_edit_drag()
        self._reset_view_state()
        self.status_var.set(message)
        self.image_position_var.set("")
        self.details_var.set(NO_SELECTION_GUIDANCE)
        self.canvas.delete("all")
        self._draw_empty(message)

    def load_partition(
        self,
        dataset_root: Path,
        partition_id: str,
        image_id: str | None = None,
    ) -> SourceImageContext | None:
        try:
            self._records = list(list_partition_source_images(dataset_root, partition_id))
        except Exception as exc:
            self.clear(f"Could not load partition source images: {exc}")
            return None
        if not self._records:
            self.clear(f"No source images found in {partition_id}.")
            return None
        selected_id = image_id or self.state.active_source_image_id or self.state.selected_image_id
        index = 0
        if selected_id:
            for candidate_index, record in enumerate(self._records):
                if record.image_id == selected_id:
                    index = candidate_index
                    break
        self._current_index = index
        return self._load_current_record()

    def load_crop(
        self,
        dataset_root: Path,
        partition_id: str,
        crop_id: str,
    ) -> SourceImageContext | None:
        try:
            context = load_source_context_for_crop(dataset_root, partition_id, crop_id)
        except Exception as exc:
            self.clear(f"Source context unavailable: {exc}")
            return None
        self._records = list(list_partition_source_images(dataset_root, partition_id))
        for index, record in enumerate(self._records):
            if record.image_id == context.image_id:
                self._current_index = index
                break
        self._set_context(context)
        return context

    def select_previous_image(self) -> None:
        if not self._records:
            return
        self._current_index = max(0, self._current_index - 1)
        self._load_current_record()

    def select_next_image(self) -> None:
        if not self._records:
            return
        self._current_index = min(len(self._records) - 1, self._current_index + 1)
        self._load_current_record()

    def select_previous_crop_or_image(self) -> None:
        if self._on_previous_crop is not None and self._on_previous_crop():
            return
        self.select_previous_image()

    def select_next_crop_or_image(self) -> None:
        if self._on_next_crop is not None and self._on_next_crop():
            return
        self.select_next_image()

    def reload_active_image(self, selected_bbox_id: str | None = None) -> SourceImageContext | None:
        if self.state.dataset_root is None or self.state.partition_id is None:
            return None
        image_id = None
        if self._context is not None:
            image_id = self._context.image_id
        image_id = image_id or self.state.active_source_image_id or self.state.selected_image_id
        if image_id is None:
            return None
        try:
            context = load_source_image_context(
                self.state.dataset_root,
                self.state.partition_id,
                image_id,
                selected_bbox_id=selected_bbox_id or self.state.selected_bbox_id,
            )
        except Exception as exc:
            self.status_var.set(f"Could not reload source image {image_id}: {exc}")
            return None
        self._set_context(context)
        return context

    def _load_current_record(self) -> SourceImageContext | None:
        if not self._records or self.state.dataset_root is None or self.state.partition_id is None:
            return None
        record = self._records[self._current_index]
        try:
            context = load_source_image_context(
                self.state.dataset_root,
                self.state.partition_id,
                record.image_id,
            )
        except Exception as exc:
            self.status_var.set(f"Could not load source image {record.image_id}: {exc}")
            self.details_var.set(NO_SELECTION_GUIDANCE)
            self._context = None
            self._image = None
            self._render()
            return None
        self._set_context(context)
        return context

    def _set_context(self, context: SourceImageContext) -> None:
        self._context = context
        self.state.active_source_image_id = context.image_id
        self.state.selected_image_id = context.image_id
        self.state.selected_bbox_id = context.selected_bbox_id
        self._last_canvas_click = None
        self._draw_start_image = None
        self._draw_preview_rect = None
        self._reset_edit_drag()
        self._reset_view_state()
        try:
            self._image = Image.open(context.image_path).convert("RGB")
        except Exception as exc:
            self._image = None
            self.status_var.set(f"Could not open source image: {exc}")
            self._render()
            return
        self._update_status()
        self._update_details()
        self.after_idle(self._render)

    def _reset_view_state(self) -> None:
        self._zoom_factor = 1.0
        self._pan_offset = (0, 0)
        self._pan_start_canvas = None
        self._pan_start_offset = None
        self._update_zoom_status()

    def reset_view(self) -> None:
        self._reset_view_state()
        self._render()

    def _update_zoom_status(self) -> None:
        self.zoom_status_var.set(f"{round(self._zoom_factor * 100)}%")

    def _update_status(self) -> None:
        if self._context is None:
            return
        position = ""
        if self._records:
            position = f"{self._current_index + 1}/{len(self._records)}"
        self.image_position_var.set(position)
        parts = [
            f"image={self._context.image_id}",
            f"boxes={len(self._context.boxes)}",
        ]
        if self._context.unsupported_shape_count:
            parts.append(f"unsupported/invalid={self._context.unsupported_shape_count}")
        if self._context.load_warnings:
            parts.append("; ".join(self._context.load_warnings[:2]))
        self.status_var.set(" | ".join(parts))

    def _update_details(self) -> None:
        if self._context is None:
            self.details_var.set(NO_SELECTION_GUIDANCE)
            return
        selected = self._context.selected_box
        if selected is None:
            self.details_var.set(NO_SELECTION_GUIDANCE)
            return
        self.details_var.set(
            " | ".join(
                (
                    f"image={self._context.image_id}",
                    f"bbox={selected.bbox_id}",
                    f"label={selected.label}",
                    f"shape_index={selected.shape_index}",
                    f"status={selected.status}",
                )
            )
        )

    def enter_draw_mode(self) -> None:
        if self._context is None:
            self.status_var.set("Load a source image before drawing a box.")
            return
        self.state.annotation_editor_mode = "draw"
        self._draw_start_image = None
        self._draw_preview_rect = None
        self.status_var.set("Draw mode: drag on the source image to stage a new box.")
        self._render()

    def cancel_draw_mode(self) -> None:
        self.state.annotation_editor_mode = "browse"
        self._draw_start_image = None
        self._draw_preview_rect = None
        self._update_status()
        self._render()

    def stage_selected_relabel(self) -> None:
        selected = self._selected_box()
        if self._context is None or selected is None:
            self.status_var.set("Select a bounding box before relabeling.")
            return
        label = selected_approved_label(self.draw_label_var.get())
        if label is None:
            self.status_var.set("Type and choose one approved PIDRay label before relabeling.")
            return
        try:
            change = stage_annotation_relabel(
                self._context,
                selected.bbox_id,
                label,
            )
        except ValueError as exc:
            self.status_var.set(str(exc))
            return
        self._stage_existing_change(
            change,
            status="pending_relabel",
            label=str(change.payload["label"]),
        )

    def stage_selected_delete(self) -> None:
        selected = self._selected_box()
        if self._context is None or selected is None:
            self.status_var.set("Select a bounding box before deleting.")
            return
        try:
            change = stage_annotation_delete(self._context, selected.bbox_id)
        except ValueError as exc:
            self.status_var.set(str(exc))
            return
        self._stage_existing_change(change, status="pending_delete")

    def cancel_selected_pending(self) -> None:
        bbox_id = self.state.selected_bbox_id
        if bbox_id is None:
            self.status_var.set("Select a bounding box before cancelling.")
            return
        before = len(self.state.pending_changes)
        self.state.pending_changes = [
            change
            for change in self.state.pending_changes
            if not self._change_targets_bbox(change, bbox_id)
        ]
        if self._on_pending_changed is not None:
            self._on_pending_changed()
        if len(self.state.pending_changes) == before:
            self.status_var.set("No pending edit exists for the selected box.")
            return
        self.reload_active_image(selected_bbox_id=bbox_id)
        self.status_var.set("Cancelled pending edits for selected box.")

    def _on_canvas_press(self, event) -> None:
        if self.state.annotation_editor_mode == "draw":
            self._start_draw(event.x, event.y)
            return
        if self._start_existing_edit(event.x, event.y):
            return
        if self._should_pan_from_left_drag(event.x, event.y):
            self._start_pan(event.x, event.y)
            return
        self._select_at_canvas_point(event.x, event.y)

    def _on_canvas_drag(self, event) -> None:
        if self._pan_start_canvas is not None:
            self._drag_pan(event.x, event.y)
            return
        if self._edit_kind is not None:
            self._drag_existing_edit(event.x, event.y)
            return
        if self.state.annotation_editor_mode != "draw" or self._context is None or self._transform is None:
            return
        if self._draw_start_image is None:
            return
        end_point = self._transform.canvas_to_image_point(event.x, event.y)
        try:
            self._draw_preview_rect = normalize_drawn_rectangle(
                self._context.image_size,
                self._draw_start_image,
                end_point,
                validate=False,
            )
        except ValueError:
            self._draw_preview_rect = None
        self._render()

    def _on_canvas_release(self, event) -> None:
        if self._pan_start_canvas is not None:
            self._finish_pan()
            return
        if self._edit_kind is not None:
            self._finish_existing_edit()
            return
        if self.state.annotation_editor_mode != "draw":
            return
        if self._context is None or self._transform is None or self._draw_start_image is None:
            return
        end_point = self._transform.canvas_to_image_point(event.x, event.y)
        try:
            label = selected_approved_label(self.draw_label_var.get())
            if label is None:
                raise ValueError("Type and choose one approved PIDRay label before drawing.")
            rectangle = normalize_drawn_rectangle(
                self._context.image_size,
                self._draw_start_image,
                end_point,
            )
            change = stage_annotation_add(self._context, rectangle, label)
        except ValueError as exc:
            self.status_var.set(str(exc))
            self._draw_start_image = None
            self._draw_preview_rect = None
            self._render()
            return
        self._stage_new_box(change, rectangle)

    def _on_canvas_mousewheel(self, event) -> None:
        if self._context is None or self._transform is None:
            return
        if getattr(event, "num", None) == 4:
            factor = VIEWER_ZOOM_STEP
        elif getattr(event, "num", None) == 5:
            factor = 1 / VIEWER_ZOOM_STEP
        else:
            factor = VIEWER_ZOOM_STEP if event.delta > 0 else 1 / VIEWER_ZOOM_STEP
        self._zoom_at(event.x, event.y, factor)

    def _zoom_at(self, canvas_x: float, canvas_y: float, factor: float) -> None:
        if self._context is None or self._transform is None:
            return
        old_zoom = self._zoom_factor
        self._zoom_factor = clamp_viewer_zoom(self._zoom_factor * factor)
        if self._zoom_factor == old_zoom:
            return
        canvas_size = (max(self.canvas.winfo_width(), 1), max(self.canvas.winfo_height(), 1))
        if self._transform.contains_canvas_point(canvas_x, canvas_y):
            image_point = self._transform.canvas_to_image_point(canvas_x, canvas_y)
            canvas_point = (canvas_x, canvas_y)
        else:
            center_x = canvas_size[0] / 2
            center_y = canvas_size[1] / 2
            image_point = self._transform.canvas_to_image_point(center_x, center_y)
            canvas_point = (center_x, center_y)
        self._pan_offset = viewer_pan_for_anchor(
            self._context.image_size,
            canvas_size,
            self._zoom_factor,
            image_point,
            canvas_point,
        )
        self._update_zoom_status()
        self._render()

    def _should_pan_from_left_drag(self, canvas_x: float, canvas_y: float) -> bool:
        if self._zoom_factor <= MIN_VIEWER_ZOOM or self._context is None or self._transform is None:
            return False
        if not self._transform.contains_canvas_point(canvas_x, canvas_y):
            return False
        image_point = self._transform.canvas_to_image_point(canvas_x, canvas_y)
        return hit_test_boxes(self._context, image_point) is None

    def _on_pan_press(self, event) -> None:
        self._start_pan(event.x, event.y)

    def _on_pan_drag(self, event) -> None:
        self._drag_pan(event.x, event.y)

    def _on_pan_release(self, _event) -> None:
        self._finish_pan()

    def _start_pan(self, canvas_x: float, canvas_y: float) -> None:
        if self._context is None:
            return
        self._pan_start_canvas = (canvas_x, canvas_y)
        self._pan_start_offset = self._pan_offset
        self.canvas.configure(cursor="fleur")

    def _drag_pan(self, canvas_x: float, canvas_y: float) -> None:
        if (
            self._context is None
            or self._pan_start_canvas is None
            or self._pan_start_offset is None
        ):
            return
        canvas_size = (max(self.canvas.winfo_width(), 1), max(self.canvas.winfo_height(), 1))
        dx = canvas_x - self._pan_start_canvas[0]
        dy = canvas_y - self._pan_start_canvas[1]
        candidate = (self._pan_start_offset[0] + dx, self._pan_start_offset[1] + dy)
        self._pan_offset = clamp_viewer_pan(
            self._context.image_size,
            canvas_size,
            self._zoom_factor,
            candidate,
        )
        self._render()

    def _finish_pan(self) -> None:
        self._pan_start_canvas = None
        self._pan_start_offset = None
        self.canvas.configure(cursor="")

    def _start_draw(self, canvas_x: float, canvas_y: float) -> None:
        if self._context is None or self._transform is None:
            return
        if not self._transform.contains_canvas_point(canvas_x, canvas_y):
            self.status_var.set("Start the new box inside the source image.")
            return
        self._draw_start_image = self._transform.canvas_to_image_point(canvas_x, canvas_y)
        self._draw_preview_rect = None
        self.state.selected_bbox_id = None

    def _stage_new_box(
        self,
        change: PendingChange,
        rectangle: tuple[int, int, int, int],
    ) -> None:
        if self._context is None:
            return
        if self._on_stage is not None:
            self._on_stage(change)
        else:
            self.state.pending_changes.append(change)
        pending_box = EditableBoundingBox(
            bbox_id=change.target_id,
            shape_index=max((box.shape_index for box in self._context.boxes), default=-1) + 1,
            label=str(change.payload["label"]),
            points=rectangle,
            status="pending_add",
        )
        self._context = replace(
            self._context,
            boxes=(*self._context.boxes, pending_box),
            selected_bbox_id=change.target_id,
        ).with_selection(change.target_id)
        self.state.selected_bbox_id = change.target_id
        self.state.annotation_editor_mode = "browse"
        self._draw_start_image = None
        self._draw_preview_rect = None
        self.status_var.set(
            f"Staged new {change.payload['label']} box. Use Save Pending to write JSON."
        )
        self._update_details()
        self._render()

    def _stage_existing_change(
        self,
        change: PendingChange,
        status: str,
        points: tuple[int, int, int, int] | None = None,
        label: str | None = None,
    ) -> None:
        if self._context is None:
            return
        if self._on_stage is not None:
            self._on_stage(change)
        else:
            self.state.pending_changes.append(change)
        boxes = []
        for box in self._context.boxes:
            if box.bbox_id == change.target_id:
                boxes.append(
                    replace(
                        box,
                        points=points or box.points,
                        label=label or box.label,
                        status=status,
                    )
                )
            else:
                boxes.append(box)
        self._context = replace(self._context, boxes=tuple(boxes)).with_selection(change.target_id)
        self.state.selected_bbox_id = change.target_id
        self.status_var.set(f"Staged {change.operation}. Use Save Pending to write JSON.")
        self._update_details()
        self._render()

    def _selected_box(self) -> EditableBoundingBox | None:
        if self._context is None or self.state.selected_bbox_id is None:
            return None
        for box in self._context.boxes:
            if box.bbox_id == self.state.selected_bbox_id:
                return box
        return None

    def _change_targets_bbox(self, change: PendingChange, bbox_id: str) -> bool:
        return (
            change.target_id == bbox_id
            or change.payload.get("bbox_id") == bbox_id
            or change.payload.get("temporary_bbox_id") == bbox_id
        )

    def _reset_edit_drag(self) -> None:
        self._edit_start_image = None
        self._edit_start_box = None
        self._edit_preview_rect = None
        self._edit_kind = None
        self._edit_handle = None
        self._edit_dragged = False

    def _start_existing_edit(self, canvas_x: float, canvas_y: float) -> bool:
        if self._context is None or self._transform is None:
            return False
        selected = self._selected_box()
        if selected is None or selected.status in {"pending_add", "pending_delete"}:
            return False
        handle = self._hit_resize_handle(selected, canvas_x, canvas_y)
        image_point = self._transform.canvas_to_image_point(canvas_x, canvas_y)
        if handle is not None:
            self._edit_kind = "resize"
            self._edit_handle = handle
        elif self._point_in_box(image_point, selected.points):
            top_hit = hit_test_boxes(self._context, image_point)
            if top_hit is not None and top_hit != selected.bbox_id:
                return False
            self._edit_kind = "move"
        else:
            return False
        self._edit_start_image = image_point
        self._edit_start_box = selected
        self._edit_preview_rect = selected.points
        self._edit_dragged = False
        self.state.annotation_editor_mode = self._edit_kind
        return True

    def _drag_existing_edit(self, canvas_x: float, canvas_y: float) -> None:
        if (
            self._context is None
            or self._transform is None
            or self._edit_start_image is None
            or self._edit_start_box is None
        ):
            return
        image_point = self._transform.canvas_to_image_point(canvas_x, canvas_y)
        try:
            if self._edit_kind == "move":
                delta = (
                    image_point[0] - self._edit_start_image[0],
                    image_point[1] - self._edit_start_image[1],
                )
                self._edit_preview_rect = move_rectangle(
                    self._context.image_size,
                    self._edit_start_box.points,
                    delta,
                )
            elif self._edit_kind == "resize" and self._edit_handle:
                self._edit_preview_rect = resize_rectangle(
                    self._context.image_size,
                    self._edit_start_box.points,
                    self._edit_handle,
                    image_point,
                    validate=False,
                )
        except ValueError as exc:
            self.status_var.set(str(exc))
            return
        self._edit_dragged = True
        self._render()

    def _finish_existing_edit(self) -> None:
        if self._context is None or self._edit_start_box is None:
            self._reset_edit_drag()
            self.state.annotation_editor_mode = "browse"
            return
        if not self._edit_dragged or self._edit_preview_rect is None:
            self._reset_edit_drag()
            self.state.annotation_editor_mode = "browse"
            self._render()
            return
        try:
            change = stage_annotation_update_box(
                self._context,
                self._edit_start_box.bbox_id,
                self._edit_preview_rect,
            )
        except ValueError as exc:
            self.status_var.set(str(exc))
            self._reset_edit_drag()
            self.state.annotation_editor_mode = "browse"
            self._render()
            return
        points = self._edit_preview_rect
        self._reset_edit_drag()
        self.state.annotation_editor_mode = "browse"
        self._stage_existing_change(change, status="pending_update", points=points)

    def _hit_resize_handle(self, box: EditableBoundingBox, canvas_x: float, canvas_y: float) -> str | None:
        if self._transform is None:
            return None
        x1, y1, x2, y2 = self._transform.image_to_canvas_rect(box.points)
        handles = {
            "nw": (x1, y1),
            "ne": (x2, y1),
            "sw": (x1, y2),
            "se": (x2, y2),
        }
        for handle, (x, y) in handles.items():
            if abs(canvas_x - x) <= HANDLE_SIZE and abs(canvas_y - y) <= HANDLE_SIZE:
                return handle
        return None

    def _point_in_box(
        self,
        point: tuple[float, float],
        rectangle: tuple[int, int, int, int],
    ) -> bool:
        x, y = point
        return rectangle[0] <= x <= rectangle[2] and rectangle[1] <= y <= rectangle[3]

    def _select_at_canvas_point(self, canvas_x: float, canvas_y: float) -> None:
        if self._context is None or self._transform is None:
            return
        if not self._transform.contains_canvas_point(canvas_x, canvas_y):
            self._select_bbox(None)
            self._last_canvas_click = None
            return
        image_point = self._transform.canvas_to_image_point(canvas_x, canvas_y)
        previous_image_point = None
        repeat_tolerance = 4.0 / max(self._transform.scale, 0.01)
        if self._last_canvas_click is not None:
            previous_image_point = self._transform.canvas_to_image_point(*self._last_canvas_click)
        bbox_id = hit_test_boxes(
            self._context,
            image_point,
            previous_click_point=previous_image_point,
            previous_selected_bbox_id=self.state.selected_bbox_id,
            repeat_tolerance=repeat_tolerance,
        )
        self._last_canvas_click = (canvas_x, canvas_y)
        self._select_bbox(bbox_id)

    def _select_bbox(self, bbox_id: str | None) -> None:
        if self._context is None:
            return
        self._context = self._context.with_selection(bbox_id)
        self.state.selected_bbox_id = bbox_id
        self._update_details()
        self._render()
        if self._on_bbox_selected is not None:
            self._on_bbox_selected(self._context, bbox_id)

    def _render(self) -> None:
        self.canvas.delete("all")
        if self._context is None or self._image is None:
            self._draw_empty("No source image selected.")
            return
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        self._pan_offset = clamp_viewer_pan(
            self._context.image_size,
            (width, height),
            self._zoom_factor,
            self._pan_offset,
        )
        self._transform = zoomed_canvas_transform(
            self._context.image_size,
            (width, height),
            self._zoom_factor,
            self._pan_offset,
        )
        fitted_size = (
            max(1, int(self._context.image_size[0] * self._transform.scale)),
            max(1, int(self._context.image_size[1] * self._transform.scale)),
        )
        fitted = self._image.resize(fitted_size, Image.Resampling.NEAREST)
        self._photo = ImageTk.PhotoImage(fitted)
        self.canvas.create_image(
            self._transform.offset_x,
            self._transform.offset_y,
            image=self._photo,
            anchor=tk.NW,
        )
        for box in sorted(self._context.boxes, key=lambda item: item.shape_index):
            self._draw_box(box)
        if self._draw_preview_rect is not None:
            self._draw_preview_box(self._draw_preview_rect)
        if self._edit_preview_rect is not None and self._edit_dragged:
            self._draw_preview_box(self._edit_preview_rect, outline="#64d2ff")

    def _draw_box(self, box) -> None:
        if self._transform is None:
            return
        x1, y1, x2, y2 = self._transform.image_to_canvas_rect(box.points)
        selected = box.bbox_id == self.state.selected_bbox_id
        outline = "#ff453a" if selected else "#31d158"
        if box.status in {"pending_update", "pending_relabel"} and not selected:
            outline = "#64d2ff"
        elif box.status == "pending_delete" and not selected:
            outline = "#ff9f0a"
        width = 3 if selected else 2
        dash = (4, 3) if box.status.startswith("pending") else None
        self.canvas.create_rectangle(x1, y1, x2, y2, outline=outline, width=width, dash=dash)
        label = box.label or "(no label)"
        self.canvas.create_text(
            x1 + 4,
            max(10, y1 + 10),
            text=label,
            fill=outline,
            anchor=tk.W,
        )
        if selected and box.status not in {"pending_add", "pending_delete"}:
            self._draw_resize_handles(box)

    def _draw_resize_handles(self, box: EditableBoundingBox) -> None:
        if self._transform is None:
            return
        x1, y1, x2, y2 = self._transform.image_to_canvas_rect(box.points)
        for x, y in ((x1, y1), (x2, y1), (x1, y2), (x2, y2)):
            self.canvas.create_rectangle(
                x - HANDLE_SIZE,
                y - HANDLE_SIZE,
                x + HANDLE_SIZE,
                y + HANDLE_SIZE,
                fill="#ff453a",
                outline="#ffffff",
            )

    def _draw_preview_box(self, rectangle: tuple[int, int, int, int], outline: str = "#ffd60a") -> None:
        if self._transform is None:
            return
        x1, y1, x2, y2 = self._transform.image_to_canvas_rect(rectangle)
        self.canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            outline=outline,
            width=2,
            dash=(6, 4),
        )

    def _draw_empty(self, message: str) -> None:
        width = max(self.canvas.winfo_width(), 320)
        height = max(self.canvas.winfo_height(), 160)
        self.canvas.create_text(
            width // 2,
            height // 2,
            text=message,
            fill="#f0f0f0",
            anchor=tk.CENTER,
        )

    def open_full_source(self) -> None:
        if self._context is None or self._image is None:
            return
        window = tk.Toplevel(self)
        window.title(f"Source Image - {self._context.image_id}")
        window.geometry("1200x800")
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)
        canvas = tk.Canvas(window, background="#111111", highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        holder = {"photo": None}

        def render(_event=None) -> None:
            canvas.delete("all")
            transform = CanvasTransform.fit(
                self._context.image_size,
                (max(canvas.winfo_width(), 1), max(canvas.winfo_height(), 1)),
            )
            fitted_size = (
                max(1, int(self._context.image_size[0] * transform.scale)),
                max(1, int(self._context.image_size[1] * transform.scale)),
            )
            fitted = self._image.resize(fitted_size, Image.Resampling.NEAREST)
            holder["photo"] = ImageTk.PhotoImage(fitted)
            canvas.create_image(transform.offset_x, transform.offset_y, image=holder["photo"], anchor=tk.NW)
            for box in sorted(self._context.boxes, key=lambda item: item.shape_index):
                x1, y1, x2, y2 = transform.image_to_canvas_rect(box.points)
                selected = box.bbox_id == self.state.selected_bbox_id
                outline = "#ff453a" if selected else "#31d158"
                canvas.create_rectangle(x1, y1, x2, y2, outline=outline, width=3 if selected else 2)

        canvas.bind("<Configure>", render)
        window.after_idle(render)
