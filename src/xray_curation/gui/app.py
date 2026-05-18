from __future__ import annotations

import argparse
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from xray_curation.config import DEFAULT_PARTITION_SIZE, default_dataset_root
from xray_curation.gui.annotation_editor import (
    ANNOTATION_EDITOR_GUIDANCE_TEXT as ANNOTATION_EDITOR_WORKFLOW_TEXT,
)
from xray_curation.gui.crop_browser import CropBrowser
from xray_curation.gui.state import CurationState
from xray_curation.gui.workers import run_tk_worker
from xray_curation.services.crop_generator import (
    generate_crops_for_partition,
    refresh_changed_crops_for_partition,
)
from xray_curation.services.crop_manifest import crop_manifest_path
from xray_curation.services.dataset_index import (
    build_dataset_manifest,
    dataset_manifest_path,
    read_dataset_manifest,
    summarize_partition_state,
)


def partition_values_from_manifest(manifest: dict) -> list[str]:
    return [
        f'{item["partition_id"]} ({item["image_count"]} images)'
        for item in manifest.get("partitions", [])
        if isinstance(item, dict)
        and "partition_id" in item
        and "image_count" in item
    ]


def partition_size_from_manifest(manifest: dict, fallback: int = DEFAULT_PARTITION_SIZE) -> int:
    try:
        size = int(manifest.get("partition_size", fallback))
    except (TypeError, ValueError):
        return fallback
    return size if size > 0 else fallback


def partition_id_from_dropdown_value(value: str) -> str | None:
    return value.split(" ", 1)[0] if value else None


def startup_partition_index(
    partition_values: list[str],
    current_partition_id: str | None,
    generated_partition_ids: set[str],
) -> int:
    if not partition_values:
        return 0
    if current_partition_id:
        for index, value in enumerate(partition_values):
            if partition_id_from_dropdown_value(value) == current_partition_id:
                return index
    for index, value in enumerate(partition_values):
        partition_id = partition_id_from_dropdown_value(value)
        if partition_id in generated_partition_ids:
            return index
    return 0


def should_handle_save_shortcut(modal_dialog_active: bool) -> bool:
    return not modal_dialog_active


class CurationApp(ttk.Frame):
    def __init__(self, master: tk.Tk, dataset_root: Path | None = None) -> None:
        super().__init__(master, padding=10)
        self.master.title("X-ray Dataset Curation")
        self.master.minsize(1100, 720)
        self.dataset_var = tk.StringVar(value=str(dataset_root or default_dataset_root()))
        self.partition_size_var = tk.IntVar(value=DEFAULT_PARTITION_SIZE)
        self.partition_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Choose a dataset root. Existing indexes load automatically.")
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_text_var = tk.StringVar(value="Idle")
        self.setup_summary_var = tk.StringVar(value="No partition selected.")
        self.setup_collapsed = False
        self.partitions: list[dict] = []
        self.action_buttons: list[ttk.Button] = []
        self.state = CurationState(dataset_root=Path(self.dataset_var.get()))
        self._build()
        self.after_idle(self._try_load_existing_manifest)

    def _build(self) -> None:
        self.grid(sticky="nsew")
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_topbar()
        self.crop_browser = CropBrowser(self, self.state)
        self.crop_browser.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.master.bind_all("<Control-s>", self._save_pending_shortcut, add="+")
        self.master.bind_all("<Control-S>", self._save_pending_shortcut, add="+")
        self._build_statusbar()

    def _has_modal_dialog_active(self) -> bool:
        grabbed = self.master.grab_current()
        return grabbed is not None and grabbed.winfo_toplevel() is not self.master

    def _save_pending_shortcut(self, _event=None) -> str:
        if should_handle_save_shortcut(self._has_modal_dialog_active()):
            self.crop_browser.save_pending()
        return "break"

    def _build_topbar(self) -> None:
        self.setup_container = ttk.Frame(self)
        self.setup_container.grid(row=0, column=0, sticky="ew")
        self.setup_container.columnconfigure(0, weight=1)

        header = ttk.Frame(self.setup_container)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        ttk.Label(header, text="Dataset and Partition").grid(row=0, column=0, sticky="w")
        ttk.Label(header, textvariable=self.setup_summary_var).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(12, 8),
        )
        self.setup_toggle_button = ttk.Button(header, text="Hide Setup", command=self._toggle_setup)
        self.setup_toggle_button.grid(row=0, column=2, sticky="e")

        top = ttk.LabelFrame(self.setup_container, text="Setup Controls", padding=8)
        top.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        top.columnconfigure(1, weight=1)
        top.columnconfigure(5, weight=1)
        self.setup_details = top

        ttk.Label(top, text="Dataset root").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.dataset_var).grid(
            row=0,
            column=1,
            columnspan=5,
            sticky="ew",
            padx=(8, 8),
        )
        self._add_button(top, "Browse", self._browse).grid(row=0, column=6, sticky="ew")

        ttk.Label(top, text="Partition size").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Spinbox(
            top,
            from_=1,
            to=100000,
            textvariable=self.partition_size_var,
            width=10,
        ).grid(row=1, column=1, sticky="w", padx=(8, 16), pady=(8, 0))
        self._add_button(top, "Index Dataset", self._index_dataset).grid(
            row=1,
            column=2,
            sticky="ew",
            pady=(8, 0),
        )

        ttk.Label(top, text="Partition").grid(row=1, column=3, sticky="w", padx=(16, 0), pady=(8, 0))
        self.partition_combo = ttk.Combobox(top, textvariable=self.partition_var, state="readonly")
        self.partition_combo.grid(row=1, column=4, columnspan=2, sticky="ew", padx=(8, 8), pady=(8, 0))
        self.partition_combo.bind("<<ComboboxSelected>>", lambda _event: self._load_selected_partition())
        self._add_button(top, "Generate Crops", self._generate_crops).grid(
            row=1,
            column=6,
            sticky="ew",
            pady=(8, 0),
        )

        actions = ttk.Frame(top)
        actions.grid(row=2, column=0, columnspan=7, sticky="ew", pady=(8, 0))
        self._add_button(actions, "Resume", self._resume_partition).grid(row=0, column=0)
        self._add_button(actions, "Refresh Changed", self._refresh_changed).grid(row=0, column=1, padx=(4, 0))
        self._add_button(actions, "Rebuild Partition", self._rebuild_partition).grid(row=0, column=2, padx=(4, 0))
        self._update_setup_summary()

    def _toggle_setup(self) -> None:
        self._set_setup_collapsed(not self.setup_collapsed)

    def _set_setup_collapsed(self, collapsed: bool) -> None:
        if collapsed == self.setup_collapsed:
            return
        self.setup_collapsed = collapsed
        if collapsed:
            self.setup_details.grid_remove()
            self.setup_toggle_button.configure(text="Show Setup")
        else:
            self.setup_details.grid()
            self.setup_toggle_button.configure(text="Hide Setup")

    def _update_setup_summary(self) -> None:
        dataset = Path(self.dataset_var.get())
        partition_id = self._selected_partition_id()
        dataset_name = dataset.name or str(dataset)
        if partition_id:
            self.setup_summary_var.set(
                f"{dataset_name} | {partition_id} | partition size {self.partition_size_var.get()}"
            )
        elif self.partitions:
            self.setup_summary_var.set(
                f"{dataset_name} | partition size {self.partition_size_var.get()} | select a partition"
            )
        else:
            self.setup_summary_var.set(
                f"{dataset_name} | partition size {self.partition_size_var.get()} | index once if no saved index exists"
            )

    def _build_statusbar(self) -> None:
        status = ttk.Frame(self)
        status.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        status.columnconfigure(0, weight=1)
        ttk.Label(status, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Label(status, textvariable=self.progress_text_var).grid(row=0, column=1, sticky="e", padx=(8, 0))
        self.progress = ttk.Progressbar(
            status,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
            length=260,
        )
        self.progress.grid(row=0, column=2, sticky="e", padx=(8, 0))

    def _add_button(self, parent, text: str, command) -> ttk.Button:
        button = ttk.Button(parent, text=text, command=command)
        self.action_buttons.append(button)
        return button

    def _browse(self) -> None:
        selected = filedialog.askdirectory(title="Select dataset root folder")
        if selected:
            self.dataset_var.set(selected)
            self.state.dataset_root = Path(selected)
            self._set_setup_collapsed(False)
            self._update_setup_summary()
            self._try_load_existing_manifest()

    def _clear_loaded_manifest(self, message: str) -> None:
        self.partitions = []
        self.partition_combo["values"] = ()
        self.partition_var.set("")
        self.state.partition_id = None
        self.state.selected_crop_id = None
        self.state.selected_image_id = None
        self.state.active_source_image_id = None
        self.state.selected_bbox_id = None
        self.state.crop_manifest = None
        self.state.pending_changes.clear()
        if hasattr(self, "crop_browser"):
            self.crop_browser.clear(message)
        self.status_var.set(message)
        self.progress_text_var.set("Ready")
        self.progress_var.set(0)
        self._set_setup_collapsed(False)
        self._update_setup_summary()

    def _apply_dataset_manifest(self, manifest: dict, message: str) -> None:
        self.partitions = list(manifest.get("partitions", []))
        self.partition_size_var.set(partition_size_from_manifest(manifest, self.partition_size_var.get()))
        values = partition_values_from_manifest(manifest)
        self.partition_combo["values"] = values
        if not values:
            self.partition_var.set("")
            self._clear_loaded_manifest("Saved dataset index has no partitions. Click Index Dataset to rebuild it.")
            return

        current_partition_id = self._selected_partition_id()
        generated_partition_ids = {
            str(partition.get("partition_id"))
            for partition in self.partitions
            if partition.get("partition_id")
            and crop_manifest_path(Path(self.dataset_var.get()), str(partition.get("partition_id"))).exists()
        }
        selected_index = startup_partition_index(
            values,
            current_partition_id,
            generated_partition_ids,
        )
        self.partition_combo.current(selected_index)
        self.partition_var.set(values[selected_index])
        self._load_selected_partition()
        self.status_var.set(message)
        self.progress_text_var.set("Ready")
        self.progress_var.set(100)
        selected_partition_id = self._selected_partition_id()
        self._set_setup_collapsed(
            bool(self.partitions and selected_partition_id in generated_partition_ids)
        )
        self._update_setup_summary()

    def _try_load_existing_manifest(self) -> None:
        dataset = Path(self.dataset_var.get())
        self.state.dataset_root = dataset
        path = dataset_manifest_path(dataset)
        if not path.exists():
            self._clear_loaded_manifest(
                "No saved dataset index found. Click Index Dataset once for this dataset root."
            )
            return
        try:
            manifest = read_dataset_manifest(dataset)
        except Exception as exc:
            self._clear_loaded_manifest(
                f"Could not load saved dataset index: {exc}. Click Index Dataset to rebuild it."
            )
            return
        self._apply_dataset_manifest(
            manifest,
            f"Loaded saved dataset index from {path}.",
        )

    def _set_busy(self, message: str, indeterminate: bool = False) -> None:
        self.status_var.set(message)
        self.progress_text_var.set(message)
        self.progress_var.set(0)
        if indeterminate:
            self.progress.configure(mode="indeterminate")
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate", maximum=100)
        for button in self.action_buttons:
            button.state(["disabled"])

    def _clear_busy(self, message: str) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate", maximum=100)
        self.progress_var.set(100)
        self.status_var.set(message)
        self.progress_text_var.set("Ready")
        for button in self.action_buttons:
            button.state(["!disabled"])

    def _update_progress(self, current: int, total: int, image_id: str, label: str) -> None:
        if total <= 0:
            percent = 0
            text = label
        else:
            percent = min(100, max(0, (current / total) * 100))
            text = f"{label}: {current}/{total} images ({image_id})"
        self.progress_var.set(percent)
        self.progress_text_var.set(text)

    def _progress_callback(self, label: str):
        last_update = {"current": 0}

        def callback(current: int, total: int, image_id: str) -> None:
            step = max(1, total // 100) if total > 0 else 1
            if current < total and current - last_update["current"] < step:
                return
            last_update["current"] = current
            self.master.after(
                0,
                lambda: self._update_progress(current, total, image_id, label),
            )

        return callback

    def _index_dataset(self) -> None:
        dataset = Path(self.dataset_var.get())
        size = int(self.partition_size_var.get())
        self._update_setup_summary()
        self._set_busy("Indexing selected dataset root...", indeterminate=True)

        def work():
            return build_dataset_manifest(dataset, partition_size=size, persist=True)

        def on_success(manifest):
            partition_count = len(manifest.get("partitions", []))
            self._apply_dataset_manifest(
                manifest,
                f'Indexed {manifest["image_count"]} images into {partition_count} partitions.',
            )
            self._clear_busy(
                f'Indexed {manifest["image_count"]} images into {partition_count} partitions.'
            )

        def on_error(exc):
            self._clear_busy("Indexing failed.")
            messagebox.showerror("Index failed", str(exc))

        run_tk_worker(self.master, work, on_success, on_error)

    def _selected_partition_id(self) -> str | None:
        return partition_id_from_dropdown_value(self.partition_var.get())

    def _load_selected_partition(self) -> None:
        partition_id = self._selected_partition_id()
        if partition_id is None:
            return
        dataset = Path(self.dataset_var.get())
        self.crop_browser.load_partition(dataset, partition_id)
        self._update_setup_summary()

    def _generate_crops(self) -> None:
        partition_id = self._selected_partition_id()
        if partition_id is None:
            messagebox.showwarning("No partition", "Index and select a partition first.")
            return
        dataset = Path(self.dataset_var.get())
        size = int(self.partition_size_var.get())
        self._set_busy(f"Generating crops for {partition_id}...")

        def work():
            return generate_crops_for_partition(
                dataset,
                partition_id,
                partition_size=size,
                progress_callback=self._progress_callback(f"Generating {partition_id}"),
            )

        def on_success(result):
            self._clear_busy(f'{partition_id}: {result.summary["crops_total"]} crops in manifest.')
            self.crop_browser.load_partition(dataset, partition_id)
            self._update_setup_summary()
            self._set_setup_collapsed(True)
            if result.warnings:
                messagebox.showwarning("Crop generation warnings", "\n".join(result.warnings[:10]))

        def on_error(exc):
            self._clear_busy("Crop generation failed.")
            messagebox.showerror("Crop generation failed", str(exc))

        run_tk_worker(self.master, work, on_success, on_error)

    def _resume_partition(self) -> None:
        partition_id = self._selected_partition_id()
        if partition_id is None:
            messagebox.showwarning("No partition", "Index and select a partition first.")
            return
        dataset = Path(self.dataset_var.get())
        summary = summarize_partition_state(dataset, partition_id)
        self.crop_browser.load_partition(dataset, partition_id)
        self._update_setup_summary()
        self._set_setup_collapsed(True)
        self.status_var.set(
            f'{partition_id}: status={summary.get("status")}, changed={summary.get("changed_image_count", 0)}.'
        )
        self.progress_text_var.set("Ready")

    def _refresh_changed(self) -> None:
        partition_id = self._selected_partition_id()
        if partition_id is None:
            messagebox.showwarning("No partition", "Index and select a partition first.")
            return
        dataset = Path(self.dataset_var.get())
        size = int(self.partition_size_var.get())
        self._set_busy(f"Refreshing changed crops for {partition_id}...")

        def work():
            return refresh_changed_crops_for_partition(
                dataset,
                partition_id,
                partition_size=size,
                progress_callback=self._progress_callback(f"Refreshing {partition_id}"),
            )

        def on_success(result):
            self._clear_busy(
                f'{partition_id}: refreshed {result.summary["changed_image_count"]} changed image(s).'
            )
            self.crop_browser.load_partition(dataset, partition_id)
            if result.warnings:
                messagebox.showwarning("Refresh warnings", "\n".join(result.warnings[:10]))

        def on_error(exc):
            self._clear_busy("Refresh changed failed.")
            messagebox.showerror("Refresh failed", str(exc))

        run_tk_worker(self.master, work, on_success, on_error)

    def _rebuild_partition(self) -> None:
        partition_id = self._selected_partition_id()
        if partition_id is None:
            messagebox.showwarning("No partition", "Index and select a partition first.")
            return
        dataset = Path(self.dataset_var.get())
        size = int(self.partition_size_var.get())
        self._set_busy(f"Rebuilding crops for {partition_id}...")

        def work():
            return generate_crops_for_partition(
                dataset,
                partition_id,
                partition_size=size,
                overwrite=True,
                progress_callback=self._progress_callback(f"Rebuilding {partition_id}"),
            )

        def on_success(result):
            self._clear_busy(f'{partition_id}: rebuilt {result.summary["crops_total"]} crops.')
            self.crop_browser.load_partition(dataset, partition_id)
            if result.warnings:
                messagebox.showwarning("Rebuild warnings", "\n".join(result.warnings[:10]))

        def on_error(exc):
            self._clear_busy("Rebuild failed.")
            messagebox.showerror("Rebuild failed", str(exc))

        run_tk_worker(self.master, work, on_success, on_error)


def run_app(dataset_root: str | Path | None = None) -> None:
    root = tk.Tk()
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    root.geometry("1280x820")
    try:
        root.state("zoomed")
    except tk.TclError:
        root.attributes("-zoomed", True)
    CurationApp(root, Path(dataset_root) if dataset_root else None)
    root.mainloop()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="xray-curation-gui")
    parser.add_argument(
        "--dataset",
        default=None,
        help="Dataset root containing images/ and json/. Default: ./dataset",
    )
    args = parser.parse_args(argv)
    run_app(args.dataset)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
