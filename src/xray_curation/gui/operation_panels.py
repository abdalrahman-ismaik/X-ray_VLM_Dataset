from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from xray_curation.domain.operations import (
    ANNOTATION_ADD,
    ANNOTATION_DELETE,
    ANNOTATION_RELABEL,
    ANNOTATION_UPDATE_BOX,
    PendingChange,
)


def _describe_change(change: PendingChange) -> str:
    if change.operation == ANNOTATION_ADD:
        return (
            f"Add box: {change.payload.get('image_id', '')} | "
            f"{change.payload.get('label', '')} | {change.target_id}"
        )
    if change.operation == ANNOTATION_UPDATE_BOX:
        return f"Edit box: {change.payload.get('image_id', '')} | {change.target_id}"
    if change.operation == ANNOTATION_RELABEL:
        return (
            f"Relabel box: {change.payload.get('image_id', '')} | "
            f"{change.payload.get('label', '')} | {change.target_id}"
        )
    if change.operation == ANNOTATION_DELETE:
        return f"Delete box: {change.payload.get('image_id', '')} | {change.target_id}"
    return f"{change.operation}: {change.target_id}"


class PendingChangesPanel(ttk.LabelFrame):
    def __init__(self, master) -> None:
        super().__init__(master, text="Pending Changes", padding=8)
        self.summary_var = tk.StringVar(value="No pending changes.")
        ttk.Label(self, textvariable=self.summary_var).grid(row=0, column=0, sticky="w")
        self.listbox = tk.Listbox(self, height=4, exportselection=False)
        self.listbox.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

    def set_changes(self, changes: list[PendingChange]) -> None:
        self.listbox.delete(0, tk.END)
        for change in changes:
            self.listbox.insert(tk.END, _describe_change(change))
        if not changes:
            self.summary_var.set("No pending changes.")
            return
        counts: dict[str, int] = {}
        for change in changes:
            counts[change.operation] = counts.get(change.operation, 0) + 1
        self.summary_var.set(
            ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))
        )


class UtilityActionsPanel(ttk.LabelFrame):
    def __init__(
        self,
        master,
        on_missing_crops,
        on_external_moves,
        on_refresh,
        on_save_pending,
    ) -> None:
        super().__init__(master, text="Utilities", padding=8)
        self.status_var = tk.StringVar(value="Utilities are ready.")
        ttk.Button(self, text="Missing Crops", command=on_missing_crops).grid(row=0, column=0)
        ttk.Button(self, text="External Moves", command=on_external_moves).grid(
            row=0,
            column=1,
            padx=4,
        )
        ttk.Button(self, text="Refresh", command=on_refresh).grid(row=0, column=2)
        ttk.Button(self, text="Save Pending", command=on_save_pending).grid(
            row=0,
            column=3,
            padx=4,
        )
        ttk.Label(self, textvariable=self.status_var).grid(
            row=1,
            column=0,
            columnspan=4,
            sticky="w",
            pady=(6, 0),
        )
        self.columnconfigure(3, weight=1)

    def set_status(self, message: str) -> None:
        self.status_var.set(message)

    def set_result(self, operation: str, summary: dict) -> None:
        parts = [f"{key}={value}" for key, value in summary.items() if not isinstance(value, list)]
        self.status_var.set(f"{operation}: " + ", ".join(parts))


class LabelStandardizationPanel(ttk.LabelFrame):
    def __init__(self, master, on_preview, on_apply) -> None:
        super().__init__(master, text="Label Standardization", padding=8)
        self.status_var = tk.StringVar(value="Approved formal labels are available.")
        ttk.Button(self, text="Preview Labels", command=on_preview).grid(row=0, column=0)
        ttk.Button(self, text="Apply Labels", command=on_apply).grid(row=0, column=1, padx=4)
        ttk.Label(self, textvariable=self.status_var).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(6, 0),
        )
        self.columnconfigure(1, weight=1)

    def set_status(self, message: str) -> None:
        self.status_var.set(message)

    def set_result(self, operation: str, summary: dict) -> None:
        keys = ("checked_count", "proposed_count", "unknown_count", "labels_updated", "files_written")
        parts = [f"{key}={summary[key]}" for key in keys if key in summary]
        self.status_var.set(f"{operation}: " + ", ".join(parts))


class ClassesPanel(ttk.LabelFrame):
    def __init__(self, master, on_add_class) -> None:
        super().__init__(master, text="Classes", padding=8)
        self.on_add_class = on_add_class
        self.new_label_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Built-in formal classes are loaded.")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        add_row = ttk.Frame(self)
        add_row.grid(row=0, column=0, sticky="ew")
        add_row.columnconfigure(0, weight=1)
        self.entry = ttk.Entry(add_row, textvariable=self.new_label_var)
        self.entry.grid(row=0, column=0, sticky="ew")
        ttk.Button(add_row, text="Add Class", command=self._add_class).grid(
            row=0,
            column=1,
            padx=(6, 0),
        )
        self.entry.bind("<Return>", lambda _event: self._add_class(), add="+")

        list_frame = ttk.Frame(self)
        list_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self.listbox = tk.Listbox(list_frame, height=12, exportselection=False)
        self.listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=scrollbar.set)

        ttk.Label(self, textvariable=self.status_var, wraplength=260).grid(
            row=2,
            column=0,
            sticky="ew",
            pady=(8, 0),
        )

    def _add_class(self) -> None:
        label = self.new_label_var.get()
        self.on_add_class(label)

    def clear_entry(self) -> None:
        self.new_label_var.set("")

    def set_status(self, message: str) -> None:
        self.status_var.set(message)

    def set_labels(
        self,
        approved_labels: tuple[str, ...],
        custom_labels: tuple[str, ...],
        label_counts: dict[str, int] | None = None,
    ) -> None:
        label_counts = label_counts or {}
        self.listbox.delete(0, tk.END)
        for label in approved_labels:
            count = label_counts.get(label, 0)
            suffix = f" ({count})" if count else ""
            self.listbox.insert(tk.END, f"{label}{suffix}    [Built-in]")
        for label in custom_labels:
            count = label_counts.get(label, 0)
            suffix = f" ({count})" if count else ""
            self.listbox.insert(tk.END, f"{label}{suffix}    [Custom]")
        known = set(approved_labels) | set(custom_labels)
        unknown_labels = sorted(
            label for label, count in label_counts.items() if count and label not in known
        )
        for label in unknown_labels:
            self.listbox.insert(tk.END, f"{label} ({label_counts[label]})    [In Dataset]")
        self.status_var.set(
            f"{len(approved_labels)} built-in class(es), {len(custom_labels)} custom class(es)."
        )
