from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from xray_curation.domain.labels import APPROVED_PIDRAY_LABELS
from xray_curation.gui.annotation_editor import (
    ANNOTATION_EDITOR_GUIDANCE_STEPS,
    AnnotationEditorPanel,
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
from xray_curation.services.crop_generator import refresh_affected_image_crops
from xray_curation.services.crop_manifest import (
    apply_external_moves,
    crop_manifest_path,
    find_crop,
    preview_external_moves,
    query_crops,
    read_crop_manifest,
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


class CropBrowser(ttk.Frame):
    def __init__(self, master, state: CurationState) -> None:
        super().__init__(master, padding=(0, 8, 0, 0))
        self.state = state
        self.label_var = tk.StringVar(value=ALL_CLASSES)
        self.status_var = tk.StringVar(value=ALL_STATUS)
        self.query_var = tk.StringVar(value="")
        self.status_var_message = tk.StringVar(value="No crop manifest loaded.")
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        panes = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        panes.grid(row=0, column=0, sticky="nsew")

        left = ttk.Frame(panes, padding=(0, 0, 8, 0))
        right = ttk.Frame(panes)
        panes.add(left, weight=2)
        panes.add(right, weight=5)

        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=1)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        self._build_filters(left)
        self._build_navigation(left)
        self._build_crop_table(left)
        self._build_actions(left)
        ttk.Label(left, textvariable=self.status_var_message).grid(row=4, column=0, sticky="w", pady=(6, 0))

        self.tabs = ttk.Notebook(right)
        self.tabs.grid(row=0, column=0, sticky="nsew")

        workflow_tab = ttk.Frame(self.tabs, padding=12)
        preview_tab = ttk.Frame(self.tabs)
        tools_tab = ttk.Frame(self.tabs, padding=8)
        pending_tab = ttk.Frame(self.tabs, padding=8)
        workflow_tab.columnconfigure(0, weight=1)
        preview_tab.columnconfigure(0, weight=1)
        preview_tab.rowconfigure(0, weight=1)
        tools_tab.columnconfigure(0, weight=1)
        pending_tab.columnconfigure(0, weight=1)
        pending_tab.rowconfigure(0, weight=1)

        self._build_workflow_tab(workflow_tab)
        self.annotation_editor = AnnotationEditorPanel(
            preview_tab,
            self.state,
            on_stage=self._stage,
            on_pending_changed=self._sync_pending_panel,
        )
        self.annotation_editor.grid(row=0, column=0, sticky="nsew")

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

        self.workflow_tab = workflow_tab
        self.preview_tab = preview_tab
        self.tabs.add(workflow_tab, text="Workflow")
        self.tabs.add(preview_tab, text="Preview")
        self.tabs.add(tools_tab, text="Utilities")
        self.tabs.add(pending_tab, text="Pending")

    def _build_workflow_tab(self, parent: ttk.Frame) -> None:
        guide = ttk.LabelFrame(parent, text="Recommended Workflow", padding=12)
        guide.grid(row=0, column=0, sticky="new")
        guide.columnconfigure(1, weight=1)
        steps = (
            ("1", "Choose Dataset", "Select the dataset root that contains images/ and json/."),
            ("2", "Index Dataset", "Build the manifest and partition list. This does not generate crops."),
            ("3", "Select Partition", "Pick one partition, such as part-0001, and work only on that partition."),
            ("4", "Generate or Resume", "Generate crops once, or Resume if the partition already has crops."),
            ("5", "Browse and Inspect", "Use filters, Previous/Next, and the Preview tab to inspect crops and source images."),
            ("6", "Stage Corrections", "Relabel, rename, move group, soft-delete, or restore selected crops."),
            ("7", "Save Pending", "Commit staged annotation changes after reviewing the pending list."),
            ("8", "Refresh Changed", "After annotation edits, refresh only changed images instead of rebuilding the partition."),
        )
        for row, (number, title, description) in enumerate(steps):
            ttk.Label(guide, text=number, width=3).grid(row=row, column=0, sticky="n", pady=(0, 6))
            ttk.Label(guide, text=title, width=18).grid(row=row, column=1, sticky="nw", pady=(0, 6))
            ttk.Label(guide, text=description, wraplength=720).grid(
                row=row,
                column=2,
                sticky="nw",
                pady=(0, 6),
            )

        editor = ttk.LabelFrame(parent, text="Annotation Editor Mode", padding=12)
        editor.grid(row=1, column=0, sticky="new", pady=(12, 0))
        editor.columnconfigure(1, weight=1)
        for row, instruction in enumerate(ANNOTATION_EDITOR_GUIDANCE_STEPS, start=1):
            ttk.Label(editor, text=f"{row}.", width=3).grid(row=row - 1, column=0, sticky="n", pady=(0, 6))
            ttk.Label(editor, text=instruction, wraplength=820).grid(
                row=row - 1,
                column=1,
                sticky="nw",
                pady=(0, 6),
            )

        notes = ttk.LabelFrame(parent, text="Safety Notes", padding=12)
        notes.grid(row=2, column=0, sticky="new", pady=(12, 0))
        notes.columnconfigure(0, weight=1)
        ttk.Label(
            notes,
            text=(
                "Original images are not modified. Crops, manifests, partition state, and operation logs "
                "are generated under dataset/curation/. Use Rebuild Partition only when you intentionally "
                "want to regenerate the selected partition."
            ),
            wraplength=880,
        ).grid(row=0, column=0, sticky="w")

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
            height=18,
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

    def load_partition(self, dataset_root: Path, partition_id: str) -> None:
        self.state.dataset_root = dataset_root
        self.state.partition_id = partition_id
        self.annotation_editor.load_partition(dataset_root, partition_id)
        manifest_path = crop_manifest_path(dataset_root, partition_id)
        if not manifest_path.exists():
            self.state.crop_manifest = None
            self.state.selected_crop_id = None
            self.tree.delete(*self.tree.get_children())
            self.tabs.select(self.preview_tab)
            self.status_var_message.set(
                f"{partition_id}: no crop manifest yet. Browsing source images from the selected partition."
            )
            return
        try:
            self.state.crop_manifest = read_crop_manifest(dataset_root, partition_id)
        except Exception as exc:
            self.state.crop_manifest = None
            self.tree.delete(*self.tree.get_children())
            self.tabs.select(self.preview_tab)
            self.status_var_message.set(
                f"Could not load crop manifest: {exc}. Source-image browsing is still available."
            )
            return
        self.status_var_message.set(f"Loaded crops for {partition_id}.")
        self.refresh()

    def refresh(self) -> None:
        previous_selection = self.state.selected_crop_id
        self.tree.delete(*self.tree.get_children())
        manifest = self.state.crop_manifest
        if not manifest:
            self.status_var_message.set(
                "No crops to show. Generate crops for the selected partition first."
            )
            return
        label = self.label_var.get()
        status = self.status_var.get()
        crops = query_crops(
            manifest,
            label=None if label == ALL_CLASSES else label,
            status=None if status == ALL_STATUS else status,
            text=self.query_var.get() or None,
        )
        for crop in crops:
            crop_id = str(crop["crop_id"])
            self.tree.insert(
                "",
                tk.END,
                iid=crop_id,
                values=(
                    crop.get("label", ""),
                    crop.get("image_id", ""),
                    crop.get("status", "active"),
                ),
            )
        self.status_var_message.set(f"Showing {len(crops)} crop(s).")
        children = self.tree.get_children()
        if not children:
            self.state.selected_crop_id = None
            return
        selected = previous_selection if previous_selection in children else children[0]
        self.tree.selection_set(selected)
        self.tree.focus(selected)
        self.tree.see(selected)
        self._on_select()

    def select_previous(self) -> None:
        self._move_selection(-1)

    def select_next(self) -> None:
        self._move_selection(1)

    def _move_selection(self, offset: int) -> None:
        children = self.tree.get_children()
        if not children:
            return
        selection = self.tree.selection()
        index = children.index(selection[0]) if selection else 0
        index = max(0, min(len(children) - 1, index + offset))
        self.tree.selection_set(children[index])
        self.tree.focus(children[index])
        self.tree.see(children[index])
        self._on_select()

    def _on_select(self, _event=None) -> None:
        selection = self.tree.selection()
        self.state.selected_crop_id = selection[0] if selection else None
        if self.state.selected_crop_id and self.state.dataset_root and self.state.partition_id:
            context = self.annotation_editor.load_crop(
                self.state.dataset_root,
                self.state.partition_id,
                self.state.selected_crop_id,
            )
            if context:
                self.state.selected_image_id = context.image_id
                self.state.active_source_image_id = context.image_id
                self.state.selected_bbox_id = context.selected_bbox_id
                self.tabs.select(self.preview_tab)

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

    def _ask_label(self, title: str) -> str | None:
        selected: dict[str, str | None] = {"value": None}
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.columnconfigure(0, weight=1)

        label_var = tk.StringVar(value=APPROVED_PIDRAY_LABELS[0])
        ttk.Label(dialog, text="Approved class label").grid(
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
            state="readonly",
            width=32,
        )
        combo.grid(row=1, column=0, sticky="ew", padx=12)

        buttons = ttk.Frame(dialog)
        buttons.grid(row=2, column=0, sticky="e", padx=12, pady=12)

        def choose() -> None:
            selected["value"] = label_var.get()
            dialog.destroy()

        ttk.Button(buttons, text="Cancel", command=dialog.destroy).grid(row=0, column=0)
        ttk.Button(buttons, text="OK", command=choose).grid(row=0, column=1, padx=(4, 0))
        combo.focus_set()
        self.wait_window(dialog)
        return selected["value"]

    def _stage_relabel(self) -> None:
        crop = self._selected_crop()
        if crop is None:
            return
        label = self._ask_label("Relabel Crop")
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
        label = self._ask_label("Move Crop Group")
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
            self.refresh()

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
