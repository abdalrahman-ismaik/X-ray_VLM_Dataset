from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from xray_curation.domain.operations import PendingChange


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
            self.listbox.insert(
                tk.END,
                f"{change.operation}: {change.target_id}",
            )
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
        self.status_var = tk.StringVar(value="Approved PIDRay labels are available.")
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
