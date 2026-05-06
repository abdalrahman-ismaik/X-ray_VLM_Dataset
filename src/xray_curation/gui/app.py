from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from xray_curation.config import DEFAULT_PARTITION_SIZE, default_dataset_root
from xray_curation.gui.crop_browser import CropBrowser
from xray_curation.gui.state import CurationState
from xray_curation.services.crop_generator import (
    generate_crops_for_partition,
    refresh_changed_crops_for_partition,
)
from xray_curation.services.dataset_index import (
    build_dataset_manifest,
    summarize_partition_state,
)
from xray_curation.gui.workers import run_tk_worker


class CurationApp(ttk.Frame):
    def __init__(self, master: tk.Tk, dataset_root: Path | None = None) -> None:
        super().__init__(master, padding=12)
        self.master.title("X-ray Dataset Curation")
        self.dataset_var = tk.StringVar(value=str(dataset_root or default_dataset_root()))
        self.partition_size_var = tk.IntVar(value=DEFAULT_PARTITION_SIZE)
        self.partition_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Choose a dataset batch and index partitions.")
        self.partitions: list[dict] = []
        self.state = CurationState(dataset_root=Path(self.dataset_var.get()))
        self._build()

    def _build(self) -> None:
        self.grid(sticky="nsew")
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        ttk.Label(self, text="Dataset batch").grid(row=0, column=0, sticky="w")
        ttk.Entry(self, textvariable=self.dataset_var).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(self, text="Browse", command=self._browse).grid(row=0, column=2)

        ttk.Label(self, text="Partition size").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Spinbox(
            self,
            from_=1,
            to=100000,
            textvariable=self.partition_size_var,
            width=12,
        ).grid(row=1, column=1, sticky="w", padx=8, pady=(8, 0))
        ttk.Button(self, text="Index Dataset", command=self._index_dataset).grid(
            row=1,
            column=2,
            pady=(8, 0),
        )

        ttk.Label(self, text="Partition").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.partition_combo = ttk.Combobox(self, textvariable=self.partition_var, state="readonly")
        self.partition_combo.grid(row=2, column=1, sticky="ew", padx=8, pady=(8, 0))
        ttk.Button(self, text="Generate Crops", command=self._generate_crops).grid(
            row=2,
            column=2,
            pady=(8, 0),
        )

        resume_actions = ttk.Frame(self)
        resume_actions.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        ttk.Button(resume_actions, text="Resume", command=self._resume_partition).grid(row=0, column=0)
        ttk.Button(resume_actions, text="Refresh Changed", command=self._refresh_changed).grid(
            row=0,
            column=1,
            padx=4,
        )
        ttk.Button(resume_actions, text="Rebuild", command=self._rebuild_partition).grid(row=0, column=2)

        ttk.Label(self, textvariable=self.status_var).grid(
            row=4,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(12, 0),
        )

        self.crop_browser = CropBrowser(self, self.state)
        self.crop_browser.grid(row=5, column=0, columnspan=3, sticky="nsew")
        self.rowconfigure(5, weight=1)

    def _browse(self) -> None:
        selected = filedialog.askdirectory(title="Select dataset batch folder")
        if selected:
            self.dataset_var.set(selected)

    def _index_dataset(self) -> None:
        dataset = Path(self.dataset_var.get())
        size = int(self.partition_size_var.get())
        self.status_var.set("Indexing selected dataset batch...")
        try:
            manifest = build_dataset_manifest(dataset, partition_size=size, persist=True)
        except Exception as exc:
            messagebox.showerror("Index failed", str(exc))
            self.status_var.set("Indexing failed.")
            return
        self.partitions = list(manifest["partitions"])
        values = [
            f'{item["partition_id"]} ({item["image_count"]} images)'
            for item in self.partitions
        ]
        self.partition_combo["values"] = values
        if values:
            self.partition_combo.current(0)
            self.partition_var.set(values[0])
            self.crop_browser.load_partition(dataset, self._selected_partition_id() or "part-0001")
        self.status_var.set(
            f'Indexed {manifest["image_count"]} images into {len(values)} partitions.'
        )

    def _selected_partition_id(self) -> str | None:
        value = self.partition_var.get()
        if not value:
            return None
        return value.split(" ", 1)[0]

    def _generate_crops(self) -> None:
        partition_id = self._selected_partition_id()
        if partition_id is None:
            messagebox.showwarning("No partition", "Index and select a partition first.")
            return
        dataset = Path(self.dataset_var.get())
        size = int(self.partition_size_var.get())
        self.status_var.set(f"Generating crops for {partition_id}...")

        def work():
            return generate_crops_for_partition(dataset, partition_id, partition_size=size)

        def on_success(result):
            self.status_var.set(
                f'{partition_id}: {result.summary["crops_total"]} crops in manifest.'
            )
            self.crop_browser.load_partition(dataset, partition_id)
            if result.warnings:
                messagebox.showwarning("Crop generation warnings", "\n".join(result.warnings[:10]))

        def on_error(exc):
            messagebox.showerror("Crop generation failed", str(exc))
            self.status_var.set("Crop generation failed.")

        run_tk_worker(self.master, work, on_success, on_error)

    def _resume_partition(self) -> None:
        partition_id = self._selected_partition_id()
        if partition_id is None:
            messagebox.showwarning("No partition", "Index and select a partition first.")
            return
        dataset = Path(self.dataset_var.get())
        summary = summarize_partition_state(dataset, partition_id)
        self.crop_browser.load_partition(dataset, partition_id)
        self.status_var.set(
            f'{partition_id}: status={summary.get("status")}, changed={summary.get("changed_image_count", 0)}.'
        )

    def _refresh_changed(self) -> None:
        partition_id = self._selected_partition_id()
        if partition_id is None:
            messagebox.showwarning("No partition", "Index and select a partition first.")
            return
        dataset = Path(self.dataset_var.get())
        size = int(self.partition_size_var.get())
        self.status_var.set(f"Refreshing changed crops for {partition_id}...")

        def work():
            return refresh_changed_crops_for_partition(dataset, partition_id, partition_size=size)

        def on_success(result):
            self.status_var.set(
                f'{partition_id}: refreshed {result.summary["changed_image_count"]} changed image(s).'
            )
            self.crop_browser.load_partition(dataset, partition_id)
            if result.warnings:
                messagebox.showwarning("Refresh warnings", "\n".join(result.warnings[:10]))

        def on_error(exc):
            messagebox.showerror("Refresh failed", str(exc))
            self.status_var.set("Refresh changed failed.")

        run_tk_worker(self.master, work, on_success, on_error)

    def _rebuild_partition(self) -> None:
        partition_id = self._selected_partition_id()
        if partition_id is None:
            messagebox.showwarning("No partition", "Index and select a partition first.")
            return
        dataset = Path(self.dataset_var.get())
        size = int(self.partition_size_var.get())
        self.status_var.set(f"Rebuilding crops for {partition_id}...")

        def work():
            return generate_crops_for_partition(
                dataset,
                partition_id,
                partition_size=size,
                overwrite=True,
            )

        def on_success(result):
            self.status_var.set(
                f'{partition_id}: rebuilt {result.summary["crops_total"]} crops.'
            )
            self.crop_browser.load_partition(dataset, partition_id)
            if result.warnings:
                messagebox.showwarning("Rebuild warnings", "\n".join(result.warnings[:10]))

        def on_error(exc):
            messagebox.showerror("Rebuild failed", str(exc))
            self.status_var.set("Rebuild failed.")

        run_tk_worker(self.master, work, on_success, on_error)


def run_app(dataset_root: str | Path | None = None) -> None:
    root = tk.Tk()
    CurationApp(root, Path(dataset_root) if dataset_root else None)
    root.mainloop()


if __name__ == "__main__":
    run_app()
