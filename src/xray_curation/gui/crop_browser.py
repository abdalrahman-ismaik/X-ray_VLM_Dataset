from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from pathlib import Path

from xray_curation.domain.labels import APPROVED_PIDRAY_LABELS
from xray_curation.gui.image_review import ImageReviewPanel
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
    commit_pending_changes,
    stage_move_group_change,
    stage_relabel_change,
    stage_rename_change,
    stage_restore_change,
    stage_soft_delete_change,
)
from xray_curation.services.crop_manifest import (
    apply_external_moves,
    find_crop,
    preview_external_moves,
    query_crops,
    read_crop_manifest,
)
from xray_curation.services.label_standardizer import (
    apply_label_standardization_for_partition,
    preview_label_standardization_for_partition,
)
from xray_curation.services.validation import (
    ensure_no_unsaved_changes,
    stage_missing_crop_deletions,
)


class CropBrowser(ttk.Frame):
    def __init__(self, master, state: CurationState) -> None:
        super().__init__(master, padding=(0, 8, 0, 0))
        self.state = state
        self.label_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="")
        self.query_var = tk.StringVar(value="")
        self.status_var_message = tk.StringVar(value="No crop manifest loaded.")
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        filters = ttk.Frame(self)
        filters.grid(row=0, column=0, sticky="ew")
        filters.columnconfigure(5, weight=1)
        ttk.Label(filters, text="Class").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            filters,
            textvariable=self.label_var,
            values=("", *APPROVED_PIDRAY_LABELS),
            width=22,
            state="readonly",
        ).grid(row=0, column=1, padx=(4, 10))
        ttk.Label(filters, text="Status").grid(row=0, column=2, sticky="w")
        ttk.Combobox(
            filters,
            textvariable=self.status_var,
            values=("", "active", "soft_deleted"),
            width=14,
            state="readonly",
        ).grid(row=0, column=3, padx=(4, 10))
        ttk.Label(filters, text="Search").grid(row=0, column=4, sticky="w")
        ttk.Entry(filters, textvariable=self.query_var).grid(row=0, column=5, sticky="ew", padx=4)
        ttk.Button(filters, text="Apply", command=self.refresh).grid(row=0, column=6)

        self.tree = ttk.Treeview(
            self,
            columns=("label", "image", "status", "crop"),
            show="headings",
            height=9,
        )
        self.tree.heading("label", text="Class")
        self.tree.heading("image", text="Image")
        self.tree.heading("status", text="Status")
        self.tree.heading("crop", text="Crop ID")
        self.tree.column("label", width=160)
        self.tree.column("image", width=120)
        self.tree.column("status", width=100)
        self.tree.column("crop", width=180)
        self.tree.grid(row=1, column=0, sticky="nsew", pady=6)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        actions = ttk.Frame(self)
        actions.grid(row=2, column=0, sticky="ew")
        ttk.Button(actions, text="Relabel", command=self._stage_relabel).grid(row=0, column=0)
        ttk.Button(actions, text="Rename", command=self._stage_rename).grid(row=0, column=1, padx=4)
        ttk.Button(actions, text="Move Group", command=self._stage_move_group).grid(row=0, column=2)
        ttk.Button(actions, text="Soft Delete", command=self._stage_soft_delete).grid(row=0, column=3, padx=4)
        ttk.Button(actions, text="Restore", command=self._stage_restore).grid(row=0, column=4)
        ttk.Button(actions, text="Cancel Selected", command=self._cancel_selected).grid(row=0, column=5, padx=4)
        ttk.Button(actions, text="Save Pending", command=self._save_pending).grid(row=0, column=6)

        ttk.Label(self, textvariable=self.status_var_message).grid(row=3, column=0, sticky="w")
        self.image_review = ImageReviewPanel(self)
        self.image_review.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        self.utility_panel = UtilityActionsPanel(
            self,
            on_missing_crops=self._detect_missing_crops,
            on_external_moves=self._preview_external_moves,
            on_refresh=self._reload_current_partition,
            on_save_pending=self._save_pending,
        )
        self.utility_panel.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        self.label_panel = LabelStandardizationPanel(
            self,
            on_preview=self._preview_label_standardization,
            on_apply=self._apply_label_standardization,
        )
        self.label_panel.grid(row=6, column=0, sticky="ew", pady=(8, 0))
        self.pending_panel = PendingChangesPanel(self)
        self.pending_panel.grid(row=7, column=0, sticky="ew", pady=(8, 0))

    def load_partition(self, dataset_root: Path, partition_id: str) -> None:
        self.state.dataset_root = dataset_root
        self.state.partition_id = partition_id
        try:
            self.state.crop_manifest = read_crop_manifest(dataset_root, partition_id)
        except Exception as exc:
            self.state.crop_manifest = None
            self.status_var_message.set(f"No crop manifest loaded: {exc}")
            self.refresh()
            return
        self.status_var_message.set(f"Loaded crops for {partition_id}.")
        self.refresh()

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        manifest = self.state.crop_manifest
        if not manifest:
            return
        crops = query_crops(
            manifest,
            label=self.label_var.get() or None,
            status=self.status_var.get() or None,
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
                    crop_id,
                ),
            )
        self.status_var_message.set(f"Showing {len(crops)} crops.")

    def _on_select(self, _event=None) -> None:
        selection = self.tree.selection()
        self.state.selected_crop_id = selection[0] if selection else None
        if self.state.selected_crop_id and self.state.dataset_root and self.state.partition_id:
            context = self.image_review.load_crop(
                self.state.dataset_root,
                self.state.partition_id,
                self.state.selected_crop_id,
            )
            if context:
                self.state.selected_image_id = context["image_id"]

    def _selected_crop(self) -> dict | None:
        if not self.state.crop_manifest or not self.state.selected_crop_id:
            messagebox.showwarning("No crop selected", "Select a crop first.")
            return None
        return find_crop(self.state.crop_manifest, self.state.selected_crop_id)

    def _stage(self, change) -> None:
        self.state.pending_changes = add_pending_change(self.state.pending_changes, change)
        self.pending_panel.set_changes(self.state.pending_changes)
        self.status_var_message.set(f"Staged {change.operation} for {change.target_id}.")

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
        result = commit_pending_changes(self.state.pending_changes)
        if result.success:
            self.state.pending_changes.clear()
            self.pending_panel.set_changes(self.state.pending_changes)
            self.status_var_message.set(
                f'Saved {result.summary["changes_applied"]} pending changes.'
            )
        else:
            messagebox.showerror("Save failed", "\n".join(result.errors))

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
