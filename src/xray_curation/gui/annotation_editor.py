from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from xray_curation.domain.labels import APPROVED_PIDRAY_LABELS
from xray_curation.domain.operations import PendingChange
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
    "Index Dataset, select a partition, then open Preview for source image browsing and source-image browsing. "
    "You can inspect boxes before crops exist, use Draw Box with an approved PIDRay label, "
    "and save staged edits with Save Pending."
)
NO_SELECTION_GUIDANCE = (
    "No bounding box selected. Click a box to select it, click overlapping boxes repeatedly to cycle, "
    "or use Draw Box to add one. Use Relabel Box, Delete Box, Cancel Box Edit, and Save Pending "
    "for reviewable annotation edits."
)


class AnnotationEditorPanel(ttk.Frame):
    def __init__(
        self,
        master,
        state: CurationState,
        on_stage: Callable[[PendingChange], None] | None = None,
        on_pending_changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master, padding=8)
        self.state = state
        self._on_stage = on_stage
        self._on_pending_changed = on_pending_changed
        self.status_var = tk.StringVar(value=EMPTY_STATE_GUIDANCE)
        self.details_var = tk.StringVar(value=NO_SELECTION_GUIDANCE)
        self.image_position_var = tk.StringVar(value="")
        self.draw_label_var = tk.StringVar(value=APPROVED_PIDRAY_LABELS[0])
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
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        toolbar = ttk.Frame(self)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(11, weight=1)
        ttk.Button(toolbar, text="Previous Image", command=self.select_previous_image).grid(
            row=0,
            column=0,
            sticky="w",
        )
        ttk.Button(toolbar, text="Next Image", command=self.select_next_image).grid(
            row=0,
            column=1,
            padx=(4, 0),
            sticky="w",
        )
        ttk.Label(toolbar, textvariable=self.image_position_var).grid(
            row=0,
            column=2,
            padx=(12, 0),
            sticky="w",
        )
        ttk.Button(toolbar, text="Draw Box", command=self.enter_draw_mode).grid(
            row=0,
            column=4,
            padx=(12, 0),
            sticky="w",
        )
        ttk.Label(toolbar, text="Label").grid(row=0, column=5, padx=(8, 0), sticky="w")
        ttk.Combobox(
            toolbar,
            textvariable=self.draw_label_var,
            values=APPROVED_PIDRAY_LABELS,
            state="readonly",
            width=22,
        ).grid(row=0, column=6, padx=(4, 0), sticky="w")
        ttk.Button(toolbar, text="Cancel Draw", command=self.cancel_draw_mode).grid(
            row=0,
            column=7,
            padx=(4, 0),
            sticky="w",
        )
        ttk.Button(toolbar, text="Relabel Box", command=self.stage_selected_relabel).grid(
            row=0,
            column=8,
            padx=(8, 0),
            sticky="w",
        )
        ttk.Button(toolbar, text="Delete Box", command=self.stage_selected_delete).grid(
            row=0,
            column=9,
            padx=(4, 0),
            sticky="w",
        )
        ttk.Button(toolbar, text="Cancel Box Edit", command=self.cancel_selected_pending).grid(
            row=0,
            column=10,
            padx=(4, 0),
            sticky="w",
        )
        ttk.Button(toolbar, text="Open Full Preview", command=self.open_full_source).grid(
            row=0,
            column=12,
            sticky="e",
        )

        ttk.Label(self, textvariable=self.status_var).grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(8, 4),
        )

        guidance = ttk.LabelFrame(self, text="Annotation Editor Workflow", padding=6)
        guidance.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        guidance.columnconfigure(0, weight=1)
        ttk.Label(
            guidance,
            text=ANNOTATION_EDITOR_GUIDANCE_TEXT,
            wraplength=1180,
        ).grid(row=0, column=0, sticky="ew")

        self.canvas = tk.Canvas(self, background="#111111", highlightthickness=0)
        self.canvas.grid(row=3, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _event: self._render())
        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)

        details = ttk.LabelFrame(self, text="Selected Bounding Box", padding=8)
        details.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        details.columnconfigure(0, weight=1)
        ttk.Label(details, textvariable=self.details_var).grid(row=0, column=0, sticky="ew")

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
        try:
            change = stage_annotation_relabel(
                self._context,
                selected.bbox_id,
                self.draw_label_var.get(),
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
        self._select_at_canvas_point(event.x, event.y)

    def _on_canvas_drag(self, event) -> None:
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
        if self._edit_kind is not None:
            self._finish_existing_edit()
            return
        if self.state.annotation_editor_mode != "draw":
            return
        if self._context is None or self._transform is None or self._draw_start_image is None:
            return
        end_point = self._transform.canvas_to_image_point(event.x, event.y)
        try:
            rectangle = normalize_drawn_rectangle(
                self._context.image_size,
                self._draw_start_image,
                end_point,
            )
            change = stage_annotation_add(self._context, rectangle, self.draw_label_var.get())
        except ValueError as exc:
            self.status_var.set(str(exc))
            self._draw_start_image = None
            self._draw_preview_rect = None
            self._render()
            return
        self._stage_new_box(change, rectangle)

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

    def _render(self) -> None:
        self.canvas.delete("all")
        if self._context is None or self._image is None:
            self._draw_empty("No source image selected.")
            return
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        self._transform = CanvasTransform.fit(
            self._context.image_size,
            (width, height),
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
