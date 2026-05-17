from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageTk

from xray_curation.domain.labels import APPROVED_PIDRAY_LABELS
from xray_curation.gui.annotation_editor import AnnotationEditorPanel
from xray_curation.gui.label_widgets import (
    attach_label_autocomplete,
    selected_approved_label,
)
from xray_curation.gui.operation_panels import (
    LabelStandardizationPanel,
    PendingChangesPanel,
    UtilityActionsPanel,
)
from xray_curation.gui.state import CurationState
from xray_curation.gui.workers import run_operation
from xray_curation.services.annotation_store import (
    add_pending_change,
    cancel_pending_change,
    commit_shared_pending_changes,
    stage_move_group_change,
    stage_relabel_change,
    stage_rename_change,
    stage_restore_change,
    stage_soft_delete_change,
)
from xray_curation.services.annotation_editor import list_partition_source_images
from xray_curation.services.crop_generator import refresh_affected_image_crops
from xray_curation.services.crop_manifest import (
    apply_external_moves,
    crop_manifest_path,
    find_crop,
    find_crop_for_bbox,
    preview_external_moves,
    query_crops,
    read_crop_manifest,
    relocate_crop_file,
    update_crop,
    write_crop_manifest,
)
from xray_curation.services.label_standardizer import (
    apply_label_standardization_for_partition,
    preview_label_standardization_for_partition,
)
from xray_curation.services.validation import (
    ensure_no_unsaved_changes,
    summarize_commit_and_refresh,
    stage_missing_crop_deletions,
    validate_pending_change_conflicts,
)

ALL_CLASSES = "All Classes"
ALL_STATUS = "All"
THUMBNAIL_PAGE_SIZE = 120
THUMBNAIL_CARD_WIDTH = 132
THUMBNAIL_CARD_HEIGHT = 112
THUMBNAIL_GRID_PADDING = 10
MIN_BROWSER_ZOOM = 70
MAX_BROWSER_ZOOM = 180
GUI_HOW_TO_TEXT = """Typical workflow

1. Choose a dataset root and select one partition.
2. Use Resume when crops already exist, or Generate Crops only for the selected partition.
3. Use Image Browser for visual browsing. Double-click an item to open Image Viewer.
4. Use the Crops tab to filter/select one crop, or multi-select thumbnails in Image Browser.
5. Use Image Viewer to inspect the source image, select boxes, draw boxes, relabel, delete, move, or resize.
6. In Image Viewer, Previous Crop and Next Crop move through the current filtered crop list.
7. Review the Pending tab.
8. Click Save Pending only when the pending list looks correct.

Right panel list

The Crops table shows all generated items in the image currently open in Image Viewer. The Class, Status, and Search filters still control the browser thumbnails and Previous/Next crop navigation across the selected partition.

What Soft Delete means

Soft Delete does not delete the original X-ray image. It also does not immediately remove the crop file from disk.

Soft Delete stages a pending change for the selected crop/bounding box. Before saving, you can use Cancel Selected or Restore.

When Save Pending succeeds:
- the source annotation JSON is written atomically;
- the bounding box is kept, but its flags.curation_status becomes soft_deleted;
- the crop manifest marks the crop status as soft_deleted;
- the crop file moves to crops/_soft_deleted/<Class Label>/;
- the GUI reloads the crop list and previews.

How it appears afterward

If the Status filter is Active, a soft-deleted crop is hidden. If the Status filter is All or soft_deleted, it can still be reviewed and restored.

Relabel and Move Group move the saved crop file into crops/<New Class Label>/ after Save Pending.

Use Delete Box in the annotation editor only when the bounding box itself should be removed from the annotation JSON. Delete Box is stronger than Soft Delete.

What Save Pending applies

Save Pending applies every staged crop correction and annotation edit together. Crop files are derived cache files; the annotation JSON and crop manifest are the important state. Original images are never modified.
"""


def unique_crop_row_id(crop_id: str, seen: dict[str, int]) -> str:
    count = seen.get(crop_id, 0)
    seen[crop_id] = count + 1
    return crop_id if count == 0 else f"{crop_id}::{count}"


def crop_row_to_select_after_refresh(
    previous_crop_id: str | None,
    row_ids: tuple[str, ...] | list[str],
    row_to_crop_id: dict[str, str],
    select_first: bool = True,
) -> str | None:
    if previous_crop_id is not None:
        for row_id in row_ids:
            if row_to_crop_id.get(row_id, row_id) == previous_crop_id:
                return row_id
    if select_first and row_ids:
        return row_ids[0]
    return None


def crops_for_active_image(
    manifest: dict,
    active_image_id: str | None,
    status: str | None = None,
    text: str | None = None,
) -> list[dict]:
    if not active_image_id:
        return []
    return query_crops(
        manifest,
        source_image_id=active_image_id,
        status=status,
        text=text,
    )


def crop_id_after_navigation(
    current_crop_id: str | None,
    crops: list[dict],
    offset: int,
) -> str | None:
    crop_ids = [str(crop.get("crop_id", "")) for crop in crops if crop.get("crop_id")]
    if not crop_ids:
        return None
    if current_crop_id in crop_ids:
        index = crop_ids.index(str(current_crop_id))
        index = max(0, min(len(crop_ids) - 1, index + offset))
    else:
        index = 0
    return crop_ids[index]


def crop_id_in_sequence(crop_id: str | None, crops: list[dict]) -> bool:
    if crop_id is None:
        return False
    return any(str(crop.get("crop_id", "")) == crop_id for crop in crops)


def navigation_anchor_after_crop_selection(
    previous_anchor_crop_id: str | None,
    selected_crop_id: str | None,
    navigation_crops: list[dict],
) -> str | None:
    if crop_id_in_sequence(selected_crop_id, navigation_crops):
        return selected_crop_id
    if crop_id_in_sequence(previous_anchor_crop_id, navigation_crops):
        return previous_anchor_crop_id
    return None


def browser_grid_column_count(
    canvas_width: int,
    card_width: int = THUMBNAIL_CARD_WIDTH,
    padding: int = THUMBNAIL_GRID_PADDING,
) -> int:
    return max(1, max(canvas_width, card_width + padding) // (card_width + padding))


def browser_grid_position(
    index: int,
    columns: int,
    card_width: int = THUMBNAIL_CARD_WIDTH,
    card_height: int = THUMBNAIL_CARD_HEIGHT,
    padding: int = THUMBNAIL_GRID_PADDING,
) -> tuple[int, int]:
    column = index % max(columns, 1)
    row = index // max(columns, 1)
    return padding + column * (card_width + padding), padding + row * (card_height + padding)


def browser_card_size(
    zoom_percent: int,
    base_width: int = THUMBNAIL_CARD_WIDTH,
    base_height: int = THUMBNAIL_CARD_HEIGHT,
) -> tuple[int, int]:
    zoom = min(MAX_BROWSER_ZOOM, max(MIN_BROWSER_ZOOM, int(zoom_percent)))
    scale = zoom / 100
    return max(88, round(base_width * scale)), max(82, round(base_height * scale))


def browser_page_count(total_items: int, page_size: int = THUMBNAIL_PAGE_SIZE) -> int:
    if total_items <= 0:
        return 0
    return (total_items + max(1, page_size) - 1) // max(1, page_size)


def clamp_browser_page(
    page_index: int,
    total_items: int,
    page_size: int = THUMBNAIL_PAGE_SIZE,
) -> int:
    page_count = browser_page_count(total_items, page_size)
    if page_count == 0:
        return 0
    return max(0, min(page_index, page_count - 1))


def browser_page_slice(
    page_index: int,
    total_items: int,
    page_size: int = THUMBNAIL_PAGE_SIZE,
) -> tuple[int, int]:
    if total_items <= 0:
        return 0, 0
    page_index = clamp_browser_page(page_index, total_items, page_size)
    start = page_index * max(1, page_size)
    end = min(total_items, start + max(1, page_size))
    return start, end


def browser_page_for_item_index(
    item_index: int | None,
    total_items: int,
    page_size: int = THUMBNAIL_PAGE_SIZE,
) -> int | None:
    if item_index is None or item_index < 0 or item_index >= total_items:
        return None
    return item_index // max(1, page_size)


class CropBrowser(ttk.Frame):
    def __init__(self, master, state: CurationState) -> None:
        super().__init__(master, padding=(0, 8, 0, 0))
        self.state = state
        self.label_var = tk.StringVar(value=ALL_CLASSES)
        self.status_var = tk.StringVar(value=ALL_STATUS)
        self.query_var = tk.StringVar(value="")
        self.status_var_message = tk.StringVar(value="No crop manifest loaded.")
        self.browser_selection_var = tk.StringVar(value="No browser item selected.")
        self.browser_zoom_var = tk.IntVar(value=100)
        self.browser_zoom_text_var = tk.StringVar(value="100%")
        self.browser_page_var = tk.StringVar(value="Page 0 of 0")
        self.filtered_crops: list[dict] = []
        self.navigation_crops: list[dict] = []
        self._selected_crop_preview: dict | None = None
        self._crop_preview_image: Image.Image | None = None
        self._crop_preview_photo = None
        self._browser_all_items: list[dict] = []
        self._thumbnail_items: list[dict] = []
        self._thumbnail_photos: list[ImageTk.PhotoImage] = []
        self._thumbnail_hitboxes: list[tuple[int, int, int, int, dict]] = []
        self._browser_selected_item_ids: set[str] = set()
        self._browser_page_index = 0
        self._tree_crop_ids: dict[str, str] = {}
        self._navigation_anchor_crop_id: str | None = None
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        panes = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        panes.grid(row=0, column=0, sticky="nsew")

        left = ttk.Frame(panes, padding=(0, 0, 8, 0))
        right = ttk.Frame(panes, padding=(8, 0, 0, 0))
        panes.add(left, weight=5)
        panes.add(right, weight=2)

        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        self._build_preview_area(left)

        self.tabs = ttk.Notebook(right)
        self.tabs.grid(row=0, column=0, sticky="nsew")

        crops_tab = ttk.Frame(self.tabs, padding=8)
        tools_tab = ttk.Frame(self.tabs, padding=8)
        pending_tab = ttk.Frame(self.tabs, padding=8)
        help_tab = ttk.Frame(self.tabs, padding=8)
        crops_tab.columnconfigure(0, weight=1)
        crops_tab.rowconfigure(2, weight=1)
        tools_tab.columnconfigure(0, weight=1)
        pending_tab.columnconfigure(0, weight=1)
        pending_tab.rowconfigure(0, weight=1)
        help_tab.columnconfigure(0, weight=1)
        help_tab.rowconfigure(0, weight=1)

        self._build_filters(crops_tab)
        self._build_navigation(crops_tab)
        self._build_crop_table(crops_tab)
        self._build_actions(crops_tab)
        ttk.Label(crops_tab, textvariable=self.status_var_message).grid(
            row=4,
            column=0,
            sticky="ew",
            pady=(6, 0),
        )

        self.utility_panel = UtilityActionsPanel(
            tools_tab,
            on_missing_crops=self._detect_missing_crops,
            on_external_moves=self._preview_external_moves,
            on_refresh=self._reload_current_partition,
            on_save_pending=self._save_pending,
        )
        self.utility_panel.grid(row=0, column=0, sticky="ew")
        self.label_panel = LabelStandardizationPanel(
            tools_tab,
            on_preview=self._preview_label_standardization,
            on_apply=self._apply_label_standardization,
        )
        self.label_panel.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        self.pending_panel = PendingChangesPanel(pending_tab)
        self.pending_panel.grid(row=0, column=0, sticky="nsew")

        self._build_help_tab(help_tab)

        self.tabs.add(crops_tab, text="Crops")
        self.tabs.add(tools_tab, text="Tools")
        self.tabs.add(pending_tab, text="Pending")
        self.tabs.add(help_tab, text="How To")

    def _build_preview_area(self, parent: ttk.Frame) -> None:
        self.workspace_tabs = ttk.Notebook(parent)
        self.workspace_tabs.grid(row=0, column=0, sticky="nsew")

        self.browser_tab = ttk.Frame(self.workspace_tabs, padding=(0, 6, 6, 0))
        self.viewer_tab = ttk.Frame(self.workspace_tabs, padding=(0, 6, 6, 0))
        self.browser_tab.columnconfigure(0, weight=1)
        self.browser_tab.rowconfigure(2, weight=1)
        self.viewer_tab.columnconfigure(0, weight=1)
        self.viewer_tab.rowconfigure(0, weight=1)

        self._build_browser_tab(self.browser_tab)
        self._build_viewer_tab(self.viewer_tab)

        self.workspace_tabs.add(self.browser_tab, text="Image Browser")
        self.workspace_tabs.add(self.viewer_tab, text="Image Viewer")

    def _build_browser_tab(self, parent: ttk.Frame) -> None:
        toolbar = ttk.Frame(parent)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        toolbar.columnconfigure(6, weight=1)
        ttk.Button(toolbar, text="Open Viewer", command=self._open_selected_browser_item).grid(row=0, column=0)
        ttk.Button(toolbar, text="Move Class", command=self._bulk_move_group).grid(row=0, column=1, padx=(4, 0))
        ttk.Button(toolbar, text="Soft Delete", command=self._bulk_soft_delete).grid(row=0, column=2, padx=(4, 0))
        ttk.Button(toolbar, text="Restore", command=self._bulk_restore).grid(row=0, column=3, padx=(4, 0))
        ttk.Button(toolbar, text="Clear Selection", command=self._clear_browser_selection).grid(
            row=0,
            column=4,
            padx=(4, 0),
        )
        ttk.Label(toolbar, text="Zoom").grid(row=0, column=5, padx=(12, 4), sticky="e")
        ttk.Scale(
            toolbar,
            from_=MIN_BROWSER_ZOOM,
            to=MAX_BROWSER_ZOOM,
            variable=self.browser_zoom_var,
            command=self._on_browser_zoom_changed,
            length=150,
        ).grid(row=0, column=6, sticky="e")
        ttk.Label(toolbar, textvariable=self.browser_zoom_text_var, width=5).grid(
            row=0,
            column=7,
            padx=(4, 8),
            sticky="e",
        )
        ttk.Label(toolbar, textvariable=self.browser_selection_var).grid(
            row=0,
            column=8,
            sticky="e",
            padx=(8, 0),
        )

        pagebar = ttk.Frame(parent)
        pagebar.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        pagebar.columnconfigure(2, weight=1)
        self.previous_page_button = ttk.Button(
            pagebar,
            text="Previous Page",
            command=self._select_previous_browser_page,
        )
        self.previous_page_button.grid(row=0, column=0, sticky="w")
        self.next_page_button = ttk.Button(
            pagebar,
            text="Next Page",
            command=self._select_next_browser_page,
        )
        self.next_page_button.grid(row=0, column=1, sticky="w", padx=(4, 0))
        ttk.Label(pagebar, textvariable=self.browser_page_var).grid(
            row=0,
            column=2,
            sticky="e",
        )

        grid_frame = ttk.Frame(parent)
        grid_frame.grid(row=2, column=0, sticky="nsew")
        grid_frame.columnconfigure(0, weight=1)
        grid_frame.rowconfigure(0, weight=1)

        self.thumbnail_canvas = tk.Canvas(grid_frame, background="#181818", highlightthickness=0)
        self.thumbnail_canvas.grid(row=0, column=0, sticky="nsew")
        self.thumbnail_canvas.bind("<Button-1>", self._on_thumbnail_click)
        self.thumbnail_canvas.bind("<Double-Button-1>", self._on_thumbnail_double_click)
        self.thumbnail_canvas.bind("<Configure>", lambda _event: self._render_thumbnail_grid())
        self.thumbnail_canvas.bind("<MouseWheel>", self._on_thumbnail_mousewheel)

        thumb_scroll = ttk.Scrollbar(grid_frame, orient=tk.VERTICAL, command=self.thumbnail_canvas.yview)
        thumb_scroll.grid(row=0, column=1, sticky="ns")
        self.thumbnail_canvas.configure(yscrollcommand=thumb_scroll.set)

    def _build_viewer_tab(self, parent: ttk.Frame) -> None:
        previews = ttk.Panedwindow(parent, orient=tk.HORIZONTAL)
        previews.grid(row=0, column=0, sticky="nsew")

        source = ttk.LabelFrame(previews, text="Image Preview and Annotation Editor", padding=4)
        crop_frame = ttk.LabelFrame(previews, text="Crop Preview", padding=4)
        previews.add(source, weight=4)
        previews.add(crop_frame, weight=1)

        source.columnconfigure(0, weight=1)
        source.rowconfigure(0, weight=1)
        crop_frame.columnconfigure(0, weight=1)
        crop_frame.rowconfigure(0, weight=1)

        self.annotation_editor = AnnotationEditorPanel(
            source,
            self.state,
            on_stage=self._stage,
            on_pending_changed=self._sync_pending_panel,
            on_bbox_selected=self._sync_crop_preview_from_bbox,
            on_previous_crop=self._select_previous_crop_from_viewer,
            on_next_crop=self._select_next_crop_from_viewer,
        )
        self.annotation_editor.grid(row=0, column=0, sticky="nsew")

        self.crop_preview_canvas = tk.Canvas(crop_frame, background="#121212", highlightthickness=0)
        self.crop_preview_canvas.grid(row=0, column=0, sticky="nsew")
        self.crop_preview_canvas.bind("<Configure>", lambda _event: self._render_selected_crop_preview())

    def clear(self, message: str = "Choose a dataset root and load a partition.") -> None:
        self.state.crop_manifest = None
        self.state.selected_crop_id = None
        self.state.selected_image_id = None
        self.state.active_source_image_id = None
        self.state.selected_bbox_id = None
        self.filtered_crops = []
        self.navigation_crops = []
        self._selected_crop_preview = None
        self._crop_preview_image = None
        self._browser_all_items = []
        self._thumbnail_items = []
        self._thumbnail_photos = []
        self._thumbnail_hitboxes = []
        self._browser_selected_item_ids = set()
        self._browser_page_index = 0
        self._tree_crop_ids = {}
        self._navigation_anchor_crop_id = None
        self.tree.delete(*self.tree.get_children())
        self.pending_panel.set_changes(self.state.pending_changes)
        self.annotation_editor.clear(message)
        self._render_selected_crop_preview()
        self._render_thumbnail_grid()
        self._update_browser_selection_status()
        self._update_browser_page_status()
        self.status_var_message.set(message)
        if hasattr(self, "tabs"):
            self.tabs.select(0)
        if hasattr(self, "workspace_tabs"):
            self.workspace_tabs.select(self.browser_tab)

    def _build_filters(self, parent: ttk.Frame) -> None:
        filters = ttk.LabelFrame(parent, text="Crop Filters", padding=8)
        filters.grid(row=0, column=0, sticky="ew")
        filters.columnconfigure(1, weight=1)
        ttk.Label(filters, text="Class").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            filters,
            textvariable=self.label_var,
            values=(ALL_CLASSES, *APPROVED_PIDRAY_LABELS),
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ttk.Label(filters, text="Status").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(
            filters,
            textvariable=self.status_var,
            values=(ALL_STATUS, "active", "soft_deleted"),
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))
        ttk.Label(filters, text="Search").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(filters, textvariable=self.query_var).grid(
            row=2,
            column=1,
            sticky="ew",
            padx=(6, 0),
            pady=(6, 0),
        )
        ttk.Button(filters, text="Apply Filters", command=self.refresh).grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(8, 0),
        )

    def _build_navigation(self, parent: ttk.Frame) -> None:
        nav = ttk.Frame(parent)
        nav.grid(row=1, column=0, sticky="ew", pady=(8, 4))
        nav.columnconfigure(2, weight=1)
        ttk.Button(nav, text="Previous", command=self.select_previous).grid(row=0, column=0)
        ttk.Button(nav, text="Next", command=self.select_next).grid(row=0, column=1, padx=(4, 0))
        ttk.Button(nav, text="Full Preview", command=self._open_full_preview).grid(
            row=0,
            column=3,
            sticky="e",
        )

    def _build_crop_table(self, parent: ttk.Frame) -> None:
        table = ttk.Frame(parent)
        table.grid(row=2, column=0, sticky="nsew")
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table,
            columns=("label", "image", "status"),
            show="headings",
            height=12,
            selectmode="browse",
        )
        self.tree.heading("label", text="Class")
        self.tree.heading("image", text="Image")
        self.tree.heading("status", text="Status")
        self.tree.column("label", width=160, stretch=True)
        self.tree.column("image", width=120, stretch=True)
        self.tree.column("status", width=90, stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        scrollbar = ttk.Scrollbar(table, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)

    def _build_actions(self, parent: ttk.Frame) -> None:
        actions = ttk.LabelFrame(parent, text="Selected Crop Actions", padding=8)
        actions.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        for index in range(3):
            actions.columnconfigure(index, weight=1)
        buttons = (
            ("Relabel", self._stage_relabel),
            ("Rename", self._stage_rename),
            ("Move Group", self._stage_move_group),
            ("Soft Delete", self._stage_soft_delete),
            ("Restore", self._stage_restore),
            ("Cancel Selected", self._cancel_selected),
            ("Save Pending", self._save_pending),
        )
        for index, (text, command) in enumerate(buttons):
            ttk.Button(actions, text=text, command=command).grid(
                row=index // 3,
                column=index % 3,
                sticky="ew",
                padx=(0 if index % 3 == 0 else 4, 0),
                pady=(0 if index < 3 else 4, 0),
            )

    def _build_help_tab(self, parent: ttk.Frame) -> None:
        text = tk.Text(
            parent,
            wrap="word",
            height=12,
            borderwidth=0,
            highlightthickness=0,
            padx=8,
            pady=8,
        )
        text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=scrollbar.set)
        text.insert("1.0", GUI_HOW_TO_TEXT)
        text.configure(state="disabled")

    def _fit_image(self, image: Image.Image, width: int, height: int) -> Image.Image:
        width = max(width, 1)
        height = max(height, 1)
        scale = min(width / image.width, height / image.height)
        scale = max(scale, 0.01)
        size = (
            max(1, int(image.width * scale)),
            max(1, int(image.height * scale)),
        )
        return image.resize(size, Image.Resampling.LANCZOS)

    def _draw_empty(self, canvas: tk.Canvas, message: str) -> None:
        canvas.delete("all")
        width = max(canvas.winfo_width(), 320)
        height = max(canvas.winfo_height(), 120)
        canvas.create_text(
            width // 2,
            height // 2,
            text=message,
            fill="#f0f0f0",
            anchor=tk.CENTER,
        )

    def _set_selected_crop_preview(self, crop: dict | None) -> None:
        self._selected_crop_preview = crop
        self._crop_preview_image = None
        if crop is not None:
            crop_path = Path(str(crop.get("crop_path", "")))
            if crop_path.is_file():
                try:
                    self._crop_preview_image = Image.open(crop_path).convert("RGB")
                except Exception:
                    self._crop_preview_image = None
        self._render_selected_crop_preview()

    def _sync_crop_preview_from_bbox(self, context, bbox_id: str | None) -> None:
        if bbox_id is None:
            self.state.selected_crop_id = None
            self._set_selected_crop_preview(None)
            self.tree.selection_remove(self.tree.selection())
            self._render_thumbnail_grid()
            return
        if not self.state.crop_manifest:
            self.state.selected_crop_id = None
            self._set_selected_crop_preview(None)
            self.status_var_message.set(
                f"Selected bbox {bbox_id}; no crop manifest is loaded for preview."
            )
            self._render_thumbnail_grid()
            return
        crop = find_crop_for_bbox(self.state.crop_manifest, context.image_id, bbox_id)
        if crop is None:
            self.state.selected_crop_id = None
            self._set_selected_crop_preview(None)
            self.tree.selection_remove(self.tree.selection())
            self.status_var_message.set(f"Selected bbox {bbox_id}; no generated crop found.")
            self._render_thumbnail_grid()
            return
        crop_id = str(crop["crop_id"])
        self.state.selected_crop_id = crop_id
        self._navigation_anchor_crop_id = navigation_anchor_after_crop_selection(
            self._navigation_anchor_crop_id,
            crop_id,
            self.navigation_crops,
        )
        self._set_selected_crop_preview(crop)
        row_id = self._tree_iid_for_crop(crop_id)
        if row_id is None:
            self.refresh(select_first=False, reset_browser_page=False)
            row_id = self._tree_iid_for_crop(crop_id)
        if row_id:
            self.tree.selection_set(row_id)
            self.tree.focus(row_id)
            self.tree.see(row_id)
        else:
            self.tree.selection_remove(self.tree.selection())
        page_changed = self._show_browser_item("crop", crop_id)
        self.status_var_message.set(f"Selected bbox {bbox_id}; showing linked crop {crop_id}.")
        if not page_changed:
            self._render_thumbnail_grid()

    def _render_selected_crop_preview(self) -> None:
        if not hasattr(self, "crop_preview_canvas"):
            return
        self.crop_preview_canvas.delete("all")
        if self._selected_crop_preview is None:
            self._draw_empty(self.crop_preview_canvas, "No crop selected.")
            return
        if self._crop_preview_image is None:
            self._draw_empty(self.crop_preview_canvas, "Crop image not available.")
            return
        width = max(self.crop_preview_canvas.winfo_width(), 1)
        height = max(self.crop_preview_canvas.winfo_height(), 1)
        fitted = self._fit_image(self._crop_preview_image, width, height)
        self._crop_preview_photo = ImageTk.PhotoImage(fitted)
        self.crop_preview_canvas.create_image(
            width // 2,
            height // 2,
            image=self._crop_preview_photo,
            anchor=tk.CENTER,
        )

    def _set_crop_thumbnails(self, crops: list[dict], reset_page: bool = True) -> None:
        seen_ids: dict[str, int] = {}
        items = []
        for crop in crops:
            crop_id = str(crop.get("crop_id", ""))
            row_id = unique_crop_row_id(crop_id, seen_ids)
            items.append(
                {
                    "kind": "crop",
                    "item_id": f"crop:{row_id}",
                    "id": crop_id,
                    "image_id": str(crop.get("image_id", "")),
                    "label": str(crop.get("label", "")),
                    "path": str(crop.get("crop_path", "")),
                    "status": str(crop.get("status", "active")),
                }
            )
        self._set_browser_items(
            items,
            reset_page=reset_page,
            active_kind="crop",
            active_id=self.state.selected_crop_id,
        )

    def _set_source_thumbnails(
        self,
        dataset_root: Path,
        partition_id: str,
        reset_page: bool = True,
    ) -> None:
        try:
            records = list(list_partition_source_images(dataset_root, partition_id))
        except Exception:
            self._set_browser_items([], reset_page=reset_page)
            return
        self._set_browser_items(
            [
                {
                    "kind": "source",
                    "item_id": f"source:{record.image_id}",
                    "id": record.image_id,
                    "image_id": record.image_id,
                    "label": record.image_id,
                    "path": str(record.image_path),
                    "status": "",
                }
                for record in records
            ],
            reset_page=reset_page,
            active_kind="source",
            active_id=self.state.active_source_image_id,
        )

    def _set_browser_items(
        self,
        items: list[dict],
        reset_page: bool = True,
        active_kind: str | None = None,
        active_id: str | None = None,
    ) -> None:
        self._browser_all_items = items
        valid_ids = {str(item.get("item_id", "")) for item in items}
        self._browser_selected_item_ids.intersection_update(valid_ids)
        if reset_page:
            self._browser_page_index = 0
        elif active_kind is not None and active_id:
            active_page = self._browser_page_for_item(active_kind, active_id)
            if active_page is not None:
                self._browser_page_index = active_page
            else:
                self._browser_page_index = clamp_browser_page(
                    self._browser_page_index,
                    len(self._browser_all_items),
                )
        else:
            self._browser_page_index = clamp_browser_page(
                self._browser_page_index,
                len(self._browser_all_items),
            )
        self._apply_browser_page()

    def _browser_page_for_item(self, kind: str, record_id: str) -> int | None:
        for index, item in enumerate(self._browser_all_items):
            if item.get("kind") == kind and str(item.get("id", "")) == record_id:
                return browser_page_for_item_index(index, len(self._browser_all_items))
        return None

    def _show_browser_item(self, kind: str, record_id: str) -> bool:
        page_index = self._browser_page_for_item(kind, record_id)
        if page_index is None:
            return False
        if page_index != self._browser_page_index:
            self._browser_page_index = page_index
            self._apply_browser_page()
            return True
        return False

    def _apply_browser_page(self) -> None:
        start, end = browser_page_slice(
            self._browser_page_index,
            len(self._browser_all_items),
        )
        self._browser_page_index = clamp_browser_page(
            self._browser_page_index,
            len(self._browser_all_items),
        )
        self._thumbnail_items = self._browser_all_items[start:end]
        if hasattr(self, "thumbnail_canvas"):
            self.thumbnail_canvas.yview_moveto(0)
        self._render_thumbnail_grid()
        self._update_browser_selection_status()
        self._update_browser_page_status()

    def _update_browser_page_status(self) -> None:
        total = len(self._browser_all_items)
        page_count = browser_page_count(total)
        if page_count == 0:
            self.browser_page_var.set("Page 0 of 0")
        else:
            start, end = browser_page_slice(self._browser_page_index, total)
            self.browser_page_var.set(
                f"Page {self._browser_page_index + 1} of {page_count} | "
                f"{start + 1}-{end} of {total}"
            )
        if hasattr(self, "previous_page_button"):
            if self._browser_page_index <= 0 or page_count <= 1:
                self.previous_page_button.state(["disabled"])
            else:
                self.previous_page_button.state(["!disabled"])
        if hasattr(self, "next_page_button"):
            if page_count <= 1 or self._browser_page_index >= page_count - 1:
                self.next_page_button.state(["disabled"])
            else:
                self.next_page_button.state(["!disabled"])

    def _select_previous_browser_page(self) -> None:
        if self._browser_page_index <= 0:
            return
        self._browser_page_index -= 1
        self._apply_browser_page()

    def _select_next_browser_page(self) -> None:
        if self._browser_page_index >= browser_page_count(len(self._browser_all_items)) - 1:
            return
        self._browser_page_index += 1
        self._apply_browser_page()

    def _render_thumbnail_grid(self) -> None:
        if not hasattr(self, "thumbnail_canvas"):
            return
        canvas = self.thumbnail_canvas
        canvas.delete("all")
        self._thumbnail_photos = []
        self._thumbnail_hitboxes = []
        if not self._thumbnail_items:
            self._draw_empty(canvas, "No thumbnails to show.")
            canvas.configure(scrollregion=(0, 0, max(canvas.winfo_width(), 320), max(canvas.winfo_height(), 240)))
            return

        card_w, card_h = browser_card_size(self.browser_zoom_var.get())
        columns = browser_grid_column_count(canvas.winfo_width(), card_width=card_w)
        image_w = card_w - 16
        image_h = card_h - 38
        for index, item in enumerate(self._thumbnail_items):
            x, y = browser_grid_position(index, columns, card_width=card_w, card_height=card_h)
            item_id = str(item.get("item_id", ""))
            selected = item_id in self._browser_selected_item_ids
            active = (
                (item["kind"] == "crop" and item["id"] == self.state.selected_crop_id)
                or (item["kind"] == "source" and item["id"] == self.state.active_source_image_id)
            )
            outline = "#ff453a" if selected else "#64d2ff" if active else "#4a4a4a"
            canvas.create_rectangle(
                x,
                y,
                x + card_w,
                y + card_h,
                outline=outline,
                width=3 if selected else 2 if active else 1,
                fill="#202020",
            )
            path = Path(item["path"])
            if path.is_file():
                try:
                    image = Image.open(path).convert("RGB")
                    fitted = self._fit_image(image, image_w, image_h)
                    photo = ImageTk.PhotoImage(fitted)
                    self._thumbnail_photos.append(photo)
                    canvas.create_image(
                        x + card_w // 2,
                        y + 8 + image_h // 2,
                        image=photo,
                        anchor=tk.CENTER,
                    )
                except Exception:
                    canvas.create_text(
                        x + card_w // 2,
                        y + 8 + image_h // 2,
                        text="Preview\nfailed",
                        fill="#f0f0f0",
                        anchor=tk.CENTER,
                    )
            else:
                canvas.create_text(
                    x + card_w // 2,
                    y + 8 + image_h // 2,
                    text="Missing\nimage",
                    fill="#f0f0f0",
                    anchor=tk.CENTER,
                )
            caption = item["label"] or item["image_id"]
            if len(caption) > 18:
                caption = caption[:15] + "..."
            if item["kind"] == "crop":
                caption = f"{caption}\n{item['image_id']}"
            canvas.create_text(
                x + 8,
                y + card_h - 20,
                text=caption,
                fill="#f0f0f0",
                anchor=tk.W,
            )
            self._thumbnail_hitboxes.append((x, y, x + card_w, y + card_h, item))

        rows = (len(self._thumbnail_items) + columns - 1) // columns
        total_height = THUMBNAIL_GRID_PADDING + rows * (card_h + THUMBNAIL_GRID_PADDING)
        canvas.configure(
            scrollregion=(0, 0, max(canvas.winfo_width(), 320), max(total_height, canvas.winfo_height()))
        )

    def _on_browser_zoom_changed(self, value: str) -> None:
        zoom = round(float(value))
        self.browser_zoom_var.set(zoom)
        self.browser_zoom_text_var.set(f"{zoom}%")
        self._render_thumbnail_grid()

    def _on_thumbnail_click(self, event) -> None:
        item = self._browser_item_at_event(event)
        if item is None:
            self._clear_browser_selection()
            return
        item_id = str(item.get("item_id", ""))
        multi_select = bool(event.state & 0x0005)
        if multi_select:
            if item_id in self._browser_selected_item_ids:
                self._browser_selected_item_ids.remove(item_id)
            else:
                self._browser_selected_item_ids.add(item_id)
        else:
            self._browser_selected_item_ids = {item_id}
        self._update_browser_selection_status()
        self._render_thumbnail_grid()

    def _on_thumbnail_double_click(self, event) -> None:
        item = self._browser_item_at_event(event)
        if item is not None:
            self._open_browser_item(item)

    def _on_thumbnail_mousewheel(self, event) -> None:
        direction = -1 if event.delta > 0 else 1
        self.thumbnail_canvas.yview_scroll(direction * 3, "units")

    def _browser_item_at_event(self, event) -> dict | None:
        canvas_x = int(self.thumbnail_canvas.canvasx(event.x))
        canvas_y = int(self.thumbnail_canvas.canvasy(event.y))
        for left, top, right, bottom, item in self._thumbnail_hitboxes:
            if left <= canvas_x <= right and top <= canvas_y <= bottom:
                return item
        return None

    def _open_browser_item(self, item: dict) -> None:
        if item["kind"] == "crop":
            self._open_crop_id(item["id"], open_viewer=True)
        elif self.state.dataset_root and self.state.partition_id:
            self.tree.selection_remove(self.tree.selection())
            self.state.selected_crop_id = None
            self._navigation_anchor_crop_id = None
            self._set_selected_crop_preview(None)
            self.annotation_editor.load_partition(
                self.state.dataset_root,
                self.state.partition_id,
                image_id=item["image_id"],
            )
            self.workspace_tabs.select(self.viewer_tab)
            self.refresh(select_first=False, reset_browser_page=False)
            self._render_thumbnail_grid()

    def _open_crop_id(self, crop_id: str, open_viewer: bool = True) -> None:
        self.state.selected_crop_id = crop_id
        self._navigation_anchor_crop_id = navigation_anchor_after_crop_selection(
            self._navigation_anchor_crop_id,
            crop_id,
            self.navigation_crops,
        )
        if self.state.crop_manifest:
            try:
                self._set_selected_crop_preview(find_crop(self.state.crop_manifest, crop_id))
            except Exception:
                self._set_selected_crop_preview(None)
        if self.state.dataset_root and self.state.partition_id:
            context = self.annotation_editor.load_crop(
                self.state.dataset_root,
                self.state.partition_id,
                crop_id,
            )
            if context:
                self.state.selected_image_id = context.image_id
                self.state.active_source_image_id = context.image_id
                self.state.selected_bbox_id = context.selected_bbox_id
        if open_viewer:
            self.workspace_tabs.select(self.viewer_tab)
        self.refresh(select_first=False, reset_browser_page=False)
        row_id = self._tree_iid_for_crop(crop_id)
        if row_id:
            self.tree.selection_set(row_id)
            self.tree.focus(row_id)
            self.tree.see(row_id)

    def _open_selected_browser_item(self) -> None:
        selected_items = [
            item
            for item in self._browser_all_items
            if str(item.get("item_id", "")) in self._browser_selected_item_ids
        ]
        if not selected_items:
            messagebox.showwarning("No image selected", "Select an image in the browser first.")
            return
        self._open_browser_item(selected_items[0])

    def _clear_browser_selection(self) -> None:
        self._browser_selected_item_ids = set()
        self._update_browser_selection_status()
        self._render_thumbnail_grid()

    def _update_browser_selection_status(self) -> None:
        selected_count = len(self._browser_selected_item_ids)
        shown_count = len(self._thumbnail_items)
        total_count = len(self._browser_all_items)
        count_text = (
            f"{shown_count} on page"
            if shown_count == total_count
            else f"{shown_count} on page, {total_count} total"
        )
        if selected_count:
            self.browser_selection_var.set(f"{selected_count} selected | {count_text}")
        elif shown_count:
            self.browser_selection_var.set(f"{count_text} | Ctrl/Shift-click for multi-select")
        else:
            self.browser_selection_var.set("No browser item selected.")

    def _selected_browser_crops(self) -> list[dict]:
        if not self.state.crop_manifest:
            return []
        crops = []
        seen_crop_ids = set()
        for item in self._browser_all_items:
            if str(item.get("item_id", "")) not in self._browser_selected_item_ids:
                continue
            if item.get("kind") != "crop":
                continue
            crop_id = str(item.get("id", ""))
            if crop_id in seen_crop_ids:
                continue
            try:
                crops.append(find_crop(self.state.crop_manifest, crop_id))
                seen_crop_ids.add(crop_id)
            except Exception:
                continue
        return crops

    def _stage_many(self, changes, message: str) -> None:
        count = 0
        for change in changes:
            self.state.pending_changes = add_pending_change(self.state.pending_changes, change)
            count += 1
        self._sync_pending_panel()
        self.status_var_message.set(f"Staged {count} {message}.")

    def _bulk_move_group(self) -> None:
        crops = self._selected_browser_crops()
        if not crops:
            self.status_var_message.set("Select generated crop images before moving classes.")
            return
        label = self._ask_label("Move Selected Crops")
        if not label:
            return
        self._stage_many((stage_move_group_change(crop, label) for crop in crops), "move change(s)")

    def _bulk_soft_delete(self) -> None:
        crops = self._selected_browser_crops()
        if not crops:
            self.status_var_message.set("Select generated crop images before soft-deleting.")
            return
        self._stage_many((stage_soft_delete_change(crop) for crop in crops), "soft-delete change(s)")

    def _bulk_restore(self) -> None:
        crops = self._selected_browser_crops()
        if not crops:
            self.status_var_message.set("Select generated crop images before restoring.")
            return
        self._stage_many((stage_restore_change(crop) for crop in crops), "restore change(s)")

    def load_partition(self, dataset_root: Path, partition_id: str) -> None:
        self.state.dataset_root = dataset_root
        self.state.partition_id = partition_id
        self.workspace_tabs.select(self.browser_tab)
        self.annotation_editor.load_partition(dataset_root, partition_id)
        self._set_selected_crop_preview(None)
        manifest_path = crop_manifest_path(dataset_root, partition_id)
        if not manifest_path.exists():
            self.state.crop_manifest = None
            self.state.selected_crop_id = None
            self.filtered_crops = []
            self.navigation_crops = []
            self._navigation_anchor_crop_id = None
            self._tree_crop_ids = {}
            self.tree.delete(*self.tree.get_children())
            self._set_source_thumbnails(dataset_root, partition_id)
            self.status_var_message.set(
                f"{partition_id}: no crop manifest yet. Browsing source images from the selected partition."
            )
            return
        try:
            self.state.crop_manifest = read_crop_manifest(dataset_root, partition_id)
        except Exception as exc:
            self.state.crop_manifest = None
            self.filtered_crops = []
            self.navigation_crops = []
            self._navigation_anchor_crop_id = None
            self._tree_crop_ids = {}
            self.tree.delete(*self.tree.get_children())
            self._set_source_thumbnails(dataset_root, partition_id)
            self.status_var_message.set(
                f"Could not load crop manifest: {exc}. Source-image browsing is still available."
            )
            return
        self.status_var_message.set(f"Loaded crops for {partition_id}.")
        self.refresh()

    def refresh(self, select_first: bool = True, reset_browser_page: bool = True) -> None:
        previous_selection = self.state.selected_crop_id
        self.tree.delete(*self.tree.get_children())
        self._tree_crop_ids = {}
        manifest = self.state.crop_manifest
        if not manifest:
            self.filtered_crops = []
            self.status_var_message.set(
                "No crops to show. Generate crops for the selected partition first."
            )
            return
        label = self.label_var.get()
        status = self.status_var.get()
        query_label = None if label == ALL_CLASSES else label
        query_status = None if status == ALL_STATUS else status
        query_text = self.query_var.get() or None
        navigation_crops = query_crops(
            manifest,
            label=query_label,
            status=query_status,
            text=query_text,
        )
        crops = crops_for_active_image(
            manifest,
            self.state.active_source_image_id,
            status=query_status,
            text=query_text,
        )
        self.filtered_crops = crops
        self.navigation_crops = navigation_crops
        self._navigation_anchor_crop_id = navigation_anchor_after_crop_selection(
            self._navigation_anchor_crop_id,
            previous_selection,
            navigation_crops,
        )
        seen_row_ids: dict[str, int] = {}
        for crop in crops:
            crop_id = str(crop["crop_id"])
            row_id = unique_crop_row_id(crop_id, seen_row_ids)
            self._tree_crop_ids[row_id] = crop_id
            self.tree.insert(
                "",
                tk.END,
                iid=row_id,
                values=(
                    crop.get("label", ""),
                    crop.get("image_id", ""),
                    crop.get("status", "active"),
                ),
            )
        self._set_crop_thumbnails(navigation_crops, reset_page=reset_browser_page)
        if self.state.active_source_image_id:
            self.status_var_message.set(
                f"Showing {len(crops)} item(s) in image {self.state.active_source_image_id}; "
                f"{len(navigation_crops)} crop(s) in current filter."
            )
        else:
            self.status_var_message.set(f"Showing {len(navigation_crops)} crop(s) in current filter.")
        children = self.tree.get_children()
        if not children:
            self.state.selected_crop_id = None
            self._set_selected_crop_preview(None)
            return
        selected = crop_row_to_select_after_refresh(
            previous_selection,
            list(children),
            self._tree_crop_ids,
            select_first=select_first,
        )
        if selected is None:
            self.tree.selection_remove(self.tree.selection())
            self.state.selected_crop_id = None
            self._set_selected_crop_preview(None)
            self._render_thumbnail_grid()
            return
        self.tree.selection_set(selected)
        self.tree.focus(selected)
        self.tree.see(selected)
        self._on_select(open_viewer=False)

    def _tree_iid_for_crop(self, crop_id: str | None) -> str | None:
        if crop_id is None:
            return None
        for row_id, mapped_crop_id in self._tree_crop_ids.items():
            if mapped_crop_id == crop_id:
                return row_id
        return None

    def select_previous(self) -> None:
        self._move_selection(-1)

    def select_next(self) -> None:
        self._move_selection(1)

    def _select_previous_crop_from_viewer(self) -> bool:
        if not self.state.crop_manifest or not self.navigation_crops:
            return False
        self.select_previous()
        return True

    def _select_next_crop_from_viewer(self) -> bool:
        if not self.state.crop_manifest or not self.navigation_crops:
            return False
        self.select_next()
        return True

    def _move_selection(self, offset: int) -> None:
        anchor_crop_id = self._navigation_anchor_crop_id or self.state.selected_crop_id
        crop_id = crop_id_after_navigation(anchor_crop_id, self.navigation_crops, offset)
        if crop_id is None:
            return
        self._open_crop_id(crop_id, open_viewer=True)

    def _on_select(self, _event=None, open_viewer: bool = True) -> None:
        selection = self.tree.selection()
        row_id = selection[0] if selection else None
        self.state.selected_crop_id = self._tree_crop_ids.get(row_id, row_id) if row_id else None
        self._navigation_anchor_crop_id = navigation_anchor_after_crop_selection(
            self._navigation_anchor_crop_id,
            self.state.selected_crop_id,
            self.navigation_crops,
        )
        if self.state.selected_crop_id and self.state.dataset_root and self.state.partition_id:
            if self.state.crop_manifest:
                try:
                    self._set_selected_crop_preview(
                        find_crop(self.state.crop_manifest, self.state.selected_crop_id)
                    )
                except Exception:
                    self._set_selected_crop_preview(None)
            context = self.annotation_editor.load_crop(
                self.state.dataset_root,
                self.state.partition_id,
                self.state.selected_crop_id,
            )
            if context:
                self.state.selected_image_id = context.image_id
                self.state.active_source_image_id = context.image_id
                self.state.selected_bbox_id = context.selected_bbox_id
                if open_viewer:
                    self.workspace_tabs.select(self.viewer_tab)
                self._render_thumbnail_grid()

    def _open_full_preview(self) -> None:
        self.annotation_editor.open_full_source()

    def _selected_crop(self) -> dict | None:
        if not self.state.crop_manifest or not self.state.selected_crop_id:
            messagebox.showwarning("No crop selected", "Select a crop first.")
            return None
        return find_crop(self.state.crop_manifest, self.state.selected_crop_id)

    def _stage(self, change) -> None:
        self.state.pending_changes = add_pending_change(self.state.pending_changes, change)
        self._sync_pending_panel()
        self.status_var_message.set(f"Staged {change.operation} for {change.target_id}.")

    def _sync_pending_panel(self) -> None:
        self.pending_panel.set_changes(self.state.pending_changes)

    def _ask_label(self, title: str, initial_label: str | None = None) -> str | None:
        selected: dict[str, str | None] = {"value": None}
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.columnconfigure(0, weight=1)

        initial = selected_approved_label(initial_label or "") or ""
        label_var = tk.StringVar(value=initial)
        ttk.Label(dialog, text="Type to search approved PIDRay labels").grid(
            row=0,
            column=0,
            sticky="w",
            padx=12,
            pady=(12, 4),
        )
        combo = ttk.Combobox(
            dialog,
            textvariable=label_var,
            values=APPROVED_PIDRAY_LABELS,
            state="normal",
            width=32,
        )
        combo.grid(row=1, column=0, sticky="ew", padx=12)
        attach_label_autocomplete(combo, label_var)

        buttons = ttk.Frame(dialog)
        buttons.grid(row=2, column=0, sticky="e", padx=12, pady=12)

        def choose() -> None:
            label = selected_approved_label(label_var.get())
            if label is None:
                messagebox.showwarning(
                    "Choose approved label",
                    "Type part of a label, then choose one approved PIDRay label from the dropdown.",
                    parent=dialog,
                )
                combo.focus_set()
                return
            selected["value"] = label
            dialog.destroy()

        ttk.Button(buttons, text="Cancel", command=dialog.destroy).grid(row=0, column=0)
        ttk.Button(buttons, text="OK", command=choose).grid(row=0, column=1, padx=(4, 0))
        dialog.bind("<Return>", lambda _event: choose())
        combo.focus_set()
        self.wait_window(dialog)
        return selected["value"]

    def _stage_relabel(self) -> None:
        crop = self._selected_crop()
        if crop is None:
            return
        label = self._ask_label("Relabel Crop", str(crop.get("label", "")))
        if label:
            self._stage(stage_relabel_change(crop, label))

    def _stage_rename(self) -> None:
        crop = self._selected_crop()
        if crop is None:
            return
        name = simpledialog.askstring("Rename Crop", "Display name")
        if name and name.strip():
            self._stage(stage_rename_change(crop, name.strip()))

    def _stage_move_group(self) -> None:
        crop = self._selected_crop()
        if crop is None:
            return
        label = self._ask_label("Move Crop Group", str(crop.get("label", "")))
        if label:
            self._stage(stage_move_group_change(crop, label))

    def _stage_soft_delete(self) -> None:
        crop = self._selected_crop()
        if crop is not None:
            self._stage(stage_soft_delete_change(crop))

    def _stage_restore(self) -> None:
        crop = self._selected_crop()
        if crop is not None:
            self._stage(stage_restore_change(crop))

    def _cancel_selected(self) -> None:
        crop = self._selected_crop()
        if crop is None:
            return
        before = len(self.state.pending_changes)
        self.state.pending_changes = [
            change
            for change in self.state.pending_changes
            if change.target_id != crop["crop_id"]
        ]
        if len(self.state.pending_changes) == before:
            change_id = f"relabel:{crop['crop_id']}"
            self.state.pending_changes = cancel_pending_change(self.state.pending_changes, change_id)
        self.pending_panel.set_changes(self.state.pending_changes)
        self.status_var_message.set("Cancelled pending changes for selected crop.")

    def _save_pending(self) -> None:
        if not self.state.pending_changes:
            self.status_var_message.set("No pending changes to save.")
            return
        conflicts = validate_pending_change_conflicts(self.state.pending_changes)
        if not conflicts.success:
            messagebox.showerror("Conflicting pending edits", "\n".join(conflicts.errors))
            self.status_var_message.set("Resolve conflicting pending edits before saving.")
            return
        changes = list(self.state.pending_changes)
        dataset_root = self.state.dataset_root
        partition_id = self.state.partition_id
        selected_bbox_id = self.state.selected_bbox_id
        self.state.worker_status = "saving_pending"
        self.state.worker_progress = 0
        self.status_var_message.set("Saving pending changes...")

        def work():
            commit_result = commit_shared_pending_changes(changes)
            refresh_result = None
            affected_image_ids = commit_result.summary.get("affected_image_ids", [])
            if commit_result.success and dataset_root and partition_id and affected_image_ids:
                refresh_result = refresh_affected_image_crops(
                    dataset_root,
                    partition_id,
                    affected_image_ids,
                )
            return commit_result, refresh_result

        def on_success(payload):
            commit_result, refresh_result = payload
            if not commit_result.success:
                self.state.worker_status = "error"
                messagebox.showerror("Save failed", "\n".join(commit_result.errors))
                self.status_var_message.set("Save failed; pending changes were kept.")
                return
            if refresh_result is not None and not refresh_result.success:
                self.state.worker_status = "error"
                messagebox.showerror("Refresh failed", "\n".join(refresh_result.errors))
                self.status_var_message.set("Refresh failed; pending changes were kept.")
                return
            if dataset_root and partition_id and crop_manifest_path(dataset_root, partition_id).exists():
                self.state.crop_manifest = read_crop_manifest(dataset_root, partition_id)
            self._apply_pending_to_manifest(changes)
            if dataset_root and partition_id and crop_manifest_path(dataset_root, partition_id).exists():
                self.state.crop_manifest = read_crop_manifest(dataset_root, partition_id)
            self.state.pending_changes.clear()
            self._sync_pending_panel()
            self.state.worker_status = "idle"
            self.state.worker_progress = 100
            summary = summarize_commit_and_refresh(commit_result, refresh_result)
            self.status_var_message.set(
                f"Saved {summary['changes_applied']} change(s); refreshed {summary['refreshed_count']} image(s)."
            )
            self.annotation_editor.reload_active_image(selected_bbox_id=selected_bbox_id)
            self.refresh(select_first=False, reset_browser_page=False)

        def on_error(exc):
            self.state.worker_status = "error"
            messagebox.showerror("Save failed", str(exc))
            self.status_var_message.set("Save failed; pending changes were kept.")

        run_operation(self, "save_pending", work, on_success, on_error)

    def _apply_pending_to_manifest(self, changes) -> None:
        if not self.state.crop_manifest or not self.state.dataset_root or not self.state.partition_id:
            return
        for change in changes:
            updates = {}
            if change.operation in {"relabel", "move_group"}:
                updates["label"] = change.payload["label"]
                updates["status"] = "active"
            elif change.operation == "rename":
                updates["display_name"] = change.payload["display_name"]
            elif change.operation == "soft_delete":
                updates["status"] = "soft_deleted"
            elif change.operation == "restore":
                updates["status"] = "active"
            if updates:
                crop = find_crop(self.state.crop_manifest, change.target_id)
                target_label = str(updates.get("label", crop.get("label", "")))
                target_status = str(updates.get("status", crop.get("status", "active")))
                updates.update(
                    relocate_crop_file(
                        self.state.dataset_root,
                        self.state.partition_id,
                        crop,
                        label=target_label,
                        status=target_status,
                    )
                )
                update_crop(self.state.crop_manifest, change.target_id, updates)
        write_crop_manifest(self.state.dataset_root, self.state.partition_id, self.state.crop_manifest)

    def _guard_utility(self, operation: str) -> bool:
        result = ensure_no_unsaved_changes(self.state.pending_changes, operation)
        if result.success:
            return True
        messagebox.showwarning("Unsaved changes", "\n".join(result.errors))
        self.utility_panel.set_result(result.operation, result.summary)
        return False

    def _active_partition(self) -> tuple[Path, str] | None:
        if not self.state.dataset_root or not self.state.partition_id:
            messagebox.showwarning("No partition", "Load a crop manifest first.")
            return None
        return self.state.dataset_root, self.state.partition_id

    def _detect_missing_crops(self) -> None:
        active = self._active_partition()
        if active is None or not self._guard_utility("missing crop detection"):
            return
        dataset_root, partition_id = active
        self.utility_panel.set_status("Checking crop files for the selected partition...")

        def work():
            return stage_missing_crop_deletions(dataset_root, partition_id)

        def on_success(payload):
            result, changes = payload
            for change in changes:
                self.state.pending_changes = add_pending_change(self.state.pending_changes, change)
            self.pending_panel.set_changes(self.state.pending_changes)
            self.utility_panel.set_result(result.operation, result.summary)

        def on_error(exc):
            messagebox.showerror("Missing crop detection failed", str(exc))
            self.utility_panel.set_status("Missing crop detection failed.")

        run_operation(self, "missing_crop_detection", work, on_success, on_error)

    def _preview_external_moves(self) -> None:
        active = self._active_partition()
        if active is None or not self._guard_utility("external moved-crop import"):
            return
        external_root = filedialog.askdirectory(title="Select external moved-crop folder")
        if not external_root:
            return
        dataset_root, partition_id = active
        self.utility_panel.set_status("Previewing external moved crops...")

        def work():
            return preview_external_moves(dataset_root, partition_id, external_root)

        def on_success(result):
            self.utility_panel.set_result(result.operation, result.summary)
            moves_found = result.summary.get("moves_found", 0)
            if moves_found <= 0:
                return
            if messagebox.askyesno("Apply external moves", f"Apply {moves_found} moved crop(s)?"):
                self._apply_external_moves(dataset_root, partition_id, external_root)

        def on_error(exc):
            messagebox.showerror("External move preview failed", str(exc))
            self.utility_panel.set_status("External move preview failed.")

        run_operation(self, "external_move_preview", work, on_success, on_error)

    def _apply_external_moves(
        self,
        dataset_root: Path,
        partition_id: str,
        external_root: str,
    ) -> None:
        self.utility_panel.set_status("Applying external moved crops...")

        def work():
            return apply_external_moves(dataset_root, partition_id, external_root)

        def on_success(result):
            self.utility_panel.set_result(result.operation, result.summary)
            self.load_partition(dataset_root, partition_id)

        def on_error(exc):
            messagebox.showerror("External move apply failed", str(exc))
            self.utility_panel.set_status("External move apply failed.")

        run_operation(self, "external_move_apply", work, on_success, on_error)

    def _reload_current_partition(self) -> None:
        active = self._active_partition()
        if active is None:
            return
        dataset_root, partition_id = active
        self.load_partition(dataset_root, partition_id)
        self.utility_panel.set_status("Reloaded selected partition manifest.")

    def _preview_label_standardization(self) -> None:
        active = self._active_partition()
        if active is None or not self._guard_utility("label standardization preview"):
            return
        dataset_root, partition_id = active
        self.label_panel.set_status("Previewing labels for the selected partition...")

        def work():
            return preview_label_standardization_for_partition(dataset_root, partition_id)

        def on_success(result):
            self.label_panel.set_result(result.operation, result.summary)
            if result.warnings:
                messagebox.showwarning("Unknown labels", "\n".join(result.warnings[:10]))

        def on_error(exc):
            messagebox.showerror("Label preview failed", str(exc))
            self.label_panel.set_status("Label preview failed.")

        run_operation(self, "label_standardization_preview", work, on_success, on_error)

    def _apply_label_standardization(self) -> None:
        active = self._active_partition()
        if active is None or not self._guard_utility("label standardization apply"):
            return
        dataset_root, partition_id = active
        self.label_panel.set_status("Applying unambiguous label standardizations...")

        def work():
            return apply_label_standardization_for_partition(dataset_root, partition_id)

        def on_success(result):
            self.label_panel.set_result(result.operation, result.summary)
            self.load_partition(dataset_root, partition_id)
            if result.warnings:
                messagebox.showwarning("Unknown labels left unchanged", "\n".join(result.warnings[:10]))

        def on_error(exc):
            messagebox.showerror("Label apply failed", str(exc))
            self.label_panel.set_status("Label apply failed.")

        run_operation(self, "label_standardization_apply", work, on_success, on_error)
