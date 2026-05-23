from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk

from xray_curation.domain.labels import APPROVED_PIDRAY_LABELS


NAVIGATION_KEYS = {
    "Down",
    "Up",
    "Left",
    "Right",
    "Home",
    "End",
    "Prior",
    "Next",
    "Return",
    "Escape",
    "Tab",
}


def _fold_label(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("_", " ")).strip().casefold()


def matching_approved_labels(
    query: str,
    labels: tuple[str, ...] = APPROVED_PIDRAY_LABELS,
) -> tuple[str, ...]:
    folded_query = _fold_label(query)
    if not folded_query:
        return labels
    prefix_matches = [label for label in labels if _fold_label(label).startswith(folded_query)]
    contains_matches = [
        label
        for label in labels
        if folded_query in _fold_label(label) and label not in prefix_matches
    ]
    return tuple(prefix_matches + contains_matches)


def selected_approved_label(
    value: str,
    labels: tuple[str, ...] = APPROVED_PIDRAY_LABELS,
) -> str | None:
    folded_value = _fold_label(value)
    if not folded_value:
        return None
    for label in labels:
        if _fold_label(label) == folded_value:
            return label
    matches = matching_approved_labels(value, labels)
    return matches[0] if len(matches) == 1 else None


def should_post_label_dropdown(query: str, matches: tuple[str, ...]) -> bool:
    return bool(_fold_label(query) and matches)


def label_dropdown_values(
    query: str,
    labels: tuple[str, ...] = APPROVED_PIDRAY_LABELS,
    show_all: bool = False,
) -> tuple[str, ...]:
    if show_all or not _fold_label(query):
        return labels
    return matching_approved_labels(query, labels)


def _restore_combobox_typing_focus(combo: ttk.Combobox, cursor_index: int | None = None) -> None:
    if not combo.winfo_exists():
        return
    combo.focus_set()
    try:
        combo.selection_clear()
    except tk.TclError:
        pass
    if cursor_index is not None:
        try:
            combo.icursor(cursor_index)
        except tk.TclError:
            pass


def post_combobox_dropdown(combo: ttk.Combobox, cursor_index: int | None = None) -> None:
    if not combo.winfo_exists():
        return
    try:
        combo.tk.call("ttk::combobox::Post", combo)
    except tk.TclError:
        combo.event_generate("<Alt-Down>")
    combo.after(1, lambda: _restore_combobox_typing_focus(combo, cursor_index))


def unpost_combobox_dropdown(combo: ttk.Combobox) -> None:
    if not combo.winfo_exists():
        return
    try:
        combo.tk.call("ttk::combobox::Unpost", combo)
    except tk.TclError:
        pass


def attach_label_autocomplete(
    combo: ttk.Combobox,
    variable: tk.StringVar,
    labels: tuple[str, ...] = APPROVED_PIDRAY_LABELS,
    auto_post: bool = True,
) -> None:
    def refresh_values(_event=None) -> None:
        if _event is not None and getattr(_event, "keysym", "") in NAVIGATION_KEYS:
            return
        query = variable.get()
        matches = matching_approved_labels(query, labels)
        combo.configure(values=matches)
        if auto_post and _event is not None and should_post_label_dropdown(query, matches):
            cursor_index = combo.index(tk.INSERT)
            combo.after_idle(lambda: post_combobox_dropdown(combo, cursor_index))
        elif auto_post and _event is not None:
            unpost_combobox_dropdown(combo)

    combo.configure(values=labels, state="normal")
    combo.configure(postcommand=refresh_values)
    combo.bind("<KeyRelease>", refresh_values, add="+")
    combo.bind("<<ComboboxSelected>>", lambda _event: combo.configure(values=labels), add="+")


class LabelAutocompleteEntry(ttk.Frame):
    """Searchable label entry with a popup that does not steal typing focus."""

    def __init__(
        self,
        master,
        variable: tk.StringVar,
        labels: tuple[str, ...] = APPROVED_PIDRAY_LABELS,
        width: int = 22,
        max_visible: int = 8,
    ) -> None:
        super().__init__(master)
        self.variable = variable
        self.labels = labels
        self.max_visible = max_visible
        self.entry = ttk.Entry(self, textvariable=self.variable, width=width)
        self.entry.grid(row=0, column=0, sticky="ew")
        self.dropdown_button = ttk.Button(
            self,
            text="v",
            width=2,
            command=self.toggle_dropdown,
        )
        self.dropdown_button.grid(row=0, column=1, sticky="e", padx=(2, 0))
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)

        self._popup: tk.Toplevel | None = None
        self._listbox: tk.Listbox | None = None

        self.entry.bind("<KeyRelease>", self._on_key_release, add="+")
        self.entry.bind("<Down>", self._focus_listbox, add="+")
        self.entry.bind("<Return>", self._accept_current, add="+")
        self.entry.bind("<Escape>", self._hide_popup_event, add="+")
        self.entry.bind("<FocusOut>", self._hide_after_focus_change, add="+")
        self.entry.bind("<Destroy>", self._destroy_popup, add="+")
        self.dropdown_button.bind("<FocusOut>", self._hide_after_focus_change, add="+")

    def focus_entry(self, select_text: bool = False) -> None:
        try:
            self.entry.configure(state="normal")
        except tk.TclError:
            pass
        try:
            self.entry.focus_force()
        except tk.TclError:
            self.entry.focus_set()
        if select_text:
            self.entry.selection_range(0, tk.END)
        else:
            try:
                self.entry.selection_clear()
            except tk.TclError:
                pass
        self.entry.icursor(tk.END)

    def _on_key_release(self, event) -> None:
        if getattr(event, "keysym", "") in NAVIGATION_KEYS:
            return
        self._refresh_popup()

    def toggle_dropdown(self) -> None:
        if self._popup is not None and self._popup.winfo_exists() and self._popup.state() != "withdrawn":
            self.hide_popup()
            self.focus_entry()
            return
        self._refresh_popup(force=True, focus_listbox=True)

    def _refresh_popup(self, force: bool = False, focus_listbox: bool = False) -> None:
        query = self.variable.get()
        show_all = force and selected_approved_label(query, self.labels) is not None
        matches = label_dropdown_values(query, self.labels, show_all=show_all)
        if not force and not should_post_label_dropdown(query, matches):
            self.hide_popup()
            return
        if not matches:
            self.hide_popup()
            return

        self._ensure_popup()
        if self._popup is None or self._listbox is None:
            return

        visible_matches = matches[: self.max_visible]
        self._listbox.configure(height=max(1, len(visible_matches)))
        self._listbox.delete(0, tk.END)
        for label in visible_matches:
            self._listbox.insert(tk.END, label)
        self._position_popup()
        self._popup.deiconify()
        self._popup.lift()
        if focus_listbox and self._listbox.size():
            self._listbox.focus_set()
            self._listbox.selection_clear(0, tk.END)
            self._listbox.selection_set(0)
            self._listbox.activate(0)

    def _ensure_popup(self) -> None:
        if self._popup is not None and self._popup.winfo_exists():
            return
        self._popup = tk.Toplevel(self)
        self._popup.withdraw()
        self._popup.overrideredirect(True)
        try:
            self._popup.attributes("-topmost", True)
        except tk.TclError:
            pass
        self._listbox = tk.Listbox(
            self._popup,
            activestyle="dotbox",
            exportselection=False,
            relief=tk.SOLID,
            borderwidth=1,
        )
        self._listbox.pack(fill="both", expand=True)
        self._listbox.bind("<ButtonRelease-1>", self._choose_from_click, add="+")
        self._listbox.bind("<Return>", self._choose_from_keyboard, add="+")
        self._listbox.bind("<Escape>", self._hide_popup_event, add="+")
        self._listbox.bind("<FocusOut>", self._hide_after_focus_change, add="+")

    def _position_popup(self) -> None:
        if self._popup is None or self._listbox is None:
            return
        self.update_idletasks()
        row_height = max(18, self._listbox.winfo_reqheight() // max(1, self._listbox.size()))
        width = max(self.winfo_width(), self.entry.winfo_width(), 240)
        height = max(24, row_height * max(1, self._listbox.size()) + 4)
        x = self.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()
        self._popup.geometry(f"{width}x{height}+{x}+{y}")

    def _focus_listbox(self, _event=None) -> str:
        self._refresh_popup(force=True, focus_listbox=True)
        return "break"

    def _accept_current(self, _event=None) -> str | None:
        matches = matching_approved_labels(self.variable.get(), self.labels)
        exact_or_unique = selected_approved_label(self.variable.get(), self.labels)
        if exact_or_unique is not None:
            self._choose_label(exact_or_unique)
            return "break"
        if len(matches) == 1:
            self._choose_label(matches[0])
            return "break"
        return None

    def _choose_from_click(self, _event=None) -> str:
        self._choose_selected_listbox_label()
        return "break"

    def _choose_from_keyboard(self, _event=None) -> str:
        self._choose_selected_listbox_label()
        return "break"

    def _choose_selected_listbox_label(self) -> None:
        if self._listbox is None:
            return
        selection = self._listbox.curselection()
        if not selection:
            return
        self._choose_label(self._listbox.get(selection[0]))

    def _choose_label(self, label: str) -> None:
        self.variable.set(label)
        self._destroy_popup()
        self.focus_entry(select_text=True)
        self.after_idle(lambda: self.focus_entry(select_text=True))

    def _hide_popup_event(self, _event=None) -> str:
        self.hide_popup()
        self.focus_entry()
        return "break"

    def _hide_after_focus_change(self, _event=None) -> None:
        self.after(150, self._hide_if_focus_left_widget)

    def _hide_if_focus_left_widget(self) -> None:
        focused = self.focus_get()
        if focused in {self.entry, self.dropdown_button, self._listbox}:
            return
        self.hide_popup()

    def hide_popup(self) -> None:
        if self._popup is not None and self._popup.winfo_exists():
            self._popup.withdraw()

    def _destroy_popup(self, _event=None) -> None:
        if self._popup is not None and self._popup.winfo_exists():
            self._popup.destroy()
        self._popup = None
        self._listbox = None
