import os
import sys
import json
import threading
from queue import Queue, Empty
from pathlib import Path
from collections import defaultdict

# ============================================================
# CONFIG
# ============================================================
IMG_DIR = r"C:\Users\Anigma_PC\CVPR2025\Annotation_generation\pidray\Dataset\images"
JSON_DIR = r"C:\Users\Anigma_PC\CVPR2025\Annotation_generation\pidray\Dataset\json"
CROP_ROOT = r"C:\Users\Anigma_PC\CVPR2025\Annotation_generation\pidray\Dataset\class_crops"

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
STRIP_CONF_ALWAYS = True

LABEL_FONT_FAMILY = "Arial"
LABEL_FONT_SIZE = 15

BOX_COLOR_ALL = "lime"
BOX_COLOR_SELECTED = "cyan"
TEXT_COLOR_ALL = "yellow"
TEXT_COLOR_SELECTED = "red"
TEMP_BOX_COLOR = "orange"

CROP_PADDING = 8
GENERATE_CROPS_IN_BACKGROUND = True


# ============================================================
# HELPERS
# ============================================================
def log(msg):
    print(msg, flush=True)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def strip_conf(label: str) -> str:
    s = (label or "").strip()
    if "__" in s:
        s = s.split("__")[0].strip()
    return s


def get_base_label(label: str) -> str:
    return strip_conf(label) if STRIP_CONF_ALWAYS else (label or "").strip()


def sanitize_name(s: str) -> str:
    s = (s or "").strip()
    bad = '<>:"/\\|?*'
    for ch in bad:
        s = s.replace(ch, "_")
    s = s.replace(" ", "_")
    return s


def get_image_list():
    if not os.path.isdir(IMG_DIR):
        raise RuntimeError(f"IMG_DIR not found: {IMG_DIR}")
    imgs = []
    for f in os.listdir(IMG_DIR):
        p = os.path.join(IMG_DIR, f)
        if os.path.isfile(p) and Path(p).suffix.lower() in SUPPORTED_EXTS:
            imgs.append(f)
    imgs.sort()
    return imgs


def json_for_image(img_name):
    return os.path.join(JSON_DIR, str(Path(img_name).with_suffix(".json")))


def shapes_from_json(data):
    shapes = data.get("shapes", [])
    if not isinstance(shapes, list):
        shapes = []
    data["shapes"] = shapes
    return shapes


def normalize_rect_points(points):
    if not isinstance(points, list) or len(points) != 2:
        return None
    (x1, y1), (x2, y2) = points
    x1, x2 = sorted([float(x1), float(x2)])
    y1, y2 = sorted([float(y1), float(y2)])
    return x1, y1, x2, y2


def match_class_from_crop_name(crop_name):
    stem = Path(crop_name).stem
    parts = stem.split("__")
    if len(parts) >= 3:
        return parts[-2]
    return ""


def match_image_stem_from_crop_name(crop_name):
    stem = Path(crop_name).stem
    parts = stem.split("__")
    if len(parts) >= 3:
        return "__".join(parts[:-2])
    return stem


# ============================================================
# BACKGROUND CROP EXPORT
# ============================================================
def export_class_crops_worker(imgs, progress_queue=None):
    """
    Background worker:
    - creates folders by class
    - saves only crop images
    - names each crop: imageStem__ClassName__XYZ.jpg
    - XYZ is the rectangle order in the JSON (global rectangle order),
      not the per-class count
    """
    from PIL import Image
    from tqdm import tqdm

    os.makedirs(CROP_ROOT, exist_ok=True)

    total_crops = 0
    class_counts = defaultdict(int)
    pbar = tqdm(total=len(imgs), desc="Generating crops", unit="img")

    for idx, img_name in enumerate(imgs, start=1):
        img_path = os.path.join(IMG_DIR, img_name)
        json_path = json_for_image(img_name)

        if not os.path.exists(json_path):
            pbar.update(1)
            if progress_queue:
                progress_queue.put({
                    "type": "progress",
                    "done": idx,
                    "total": len(imgs),
                    "image": img_name,
                    "crops": total_crops
                })
            continue

        try:
            data = load_json(json_path)
            img = Image.open(img_path).convert("RGB")
        except Exception as e:
            log(f"[WARN] skip {img_name}: {e}")
            pbar.update(1)
            if progress_queue:
                progress_queue.put({
                    "type": "progress",
                    "done": idx,
                    "total": len(imgs),
                    "image": img_name,
                    "crops": total_crops
                })
            continue

        W, H = img.size
        shapes = shapes_from_json(data)

        rect_order = 0  # global rectangle order in JSON for this image

        for sh in shapes:
            if sh.get("shape_type") != "rectangle":
                continue

            rect_order += 1

            label = get_base_label(sh.get("label", ""))
            if not label:
                continue

            rect = normalize_rect_points(sh.get("points", []))
            if rect is None:
                continue

            x1, y1, x2, y2 = rect
            x1 = max(0, int(round(x1)) - CROP_PADDING)
            y1 = max(0, int(round(y1)) - CROP_PADDING)
            x2 = min(W, int(round(x2)) + CROP_PADDING)
            y2 = min(H, int(round(y2)) + CROP_PADDING)

            if x2 <= x1 or y2 <= y1:
                continue

            class_dir = os.path.join(CROP_ROOT, sanitize_name(label))
            os.makedirs(class_dir, exist_ok=True)

            # instance id is the JSON rectangle order
            out_name = f"{Path(img_name).stem}__{sanitize_name(label)}__{rect_order:03d}.jpg"
            out_path = os.path.join(class_dir, out_name)

            if not os.path.exists(out_path):
                try:
                    crop = img.crop((x1, y1, x2, y2))
                    crop.save(out_path, quality=95)
                    total_crops += 1
                    class_counts[label] += 1
                except Exception as e:
                    log(f"[WARN] crop save failed for {img_name}: {e}")

        pbar.update(1)

        if progress_queue:
            progress_queue.put({
                "type": "progress",
                "done": idx,
                "total": len(imgs),
                "image": img_name,
                "crops": total_crops
            })

    pbar.close()

    if progress_queue:
        progress_queue.put({
            "type": "done",
            "total_images": len(imgs),
            "total_crops": total_crops,
            "class_counts": dict(class_counts)
        })


# ============================================================
# MAIN GUI
# ============================================================
def main():
    log("Starting GUI...")
    log(f"Python: {sys.executable}")
    log(f"IMG_DIR:  {IMG_DIR}")
    log(f"JSON_DIR: {JSON_DIR}")
    log(f"CROP_ROOT: {CROP_ROOT}")

    if not os.path.isdir(JSON_DIR):
        raise RuntimeError(f"JSON_DIR not found: {JSON_DIR}")

    imgs = get_image_list()
    log(f"Found {len(imgs)} images")
    if not imgs:
        raise RuntimeError("No images found in IMG_DIR.")

    import tkinter as tk
    from tkinter import ttk, messagebox, simpledialog
    from PIL import Image, ImageTk

    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("BBox Review GUI")

            self.update_idletasks()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()

            win_w = max(1200, sw - 40)
            win_h = max(800, sh - 80)
            self.geometry(f"{win_w}x{win_h}+10+10")

            try:
                self.state("zoomed")
            except Exception:
                pass

            self.attributes("-topmost", True)
            self.after(250, lambda: self.attributes("-topmost", False))

            self.img_list_all = imgs
            self.current_img_name = None
            self.current_img_path = None
            self.current_json_path = None

            self.data = None
            self.pil_img = None
            self.tk_img = None
            self.scale = 1.0
            self.offset_x = 0
            self.offset_y = 0

            self.selected_shape_idx = None
            self.box_items = []
            self.shape_to_listbox_row = {}

            self.edit_mode = "select"   # select | add | resize
            self.drag_start = None
            self.temp_rect_id = None
            self.dragging = False

            self.class_var = tk.StringVar(value="(all)")
            self.search_var = tk.StringVar(value="")
            self.crop_name_var = tk.StringVar(value="")
            self.info_var = tk.StringVar(value="Opening GUI...")
            self.crop_status_var = tk.StringVar(value="Crop generation: not started")

            self.progress_queue = Queue()
            self.crop_thread = None
            self.resize_after_id = None

            self._build_ui()
            self._bind_keys()

            self.class_combo["values"] = ["(all)"]
            self.class_var.set("(all)")

            self.bind("<Configure>", self.on_window_configure)

            self.open_image(self.img_list_all[0])

            self.after(300, self.start_background_crop_generation)
            self.after(200, self.poll_progress_queue)

        # ----------------------------------------------------
        # UI
        # ----------------------------------------------------
        def _build_ui(self):
            top = ttk.Frame(self)
            top.pack(fill="x", padx=8, pady=6)

            ttk.Label(top, text="Image name / stem:").pack(side="left", padx=(0, 6))
            self.search_entry = ttk.Entry(top, textvariable=self.search_var, width=28)
            self.search_entry.pack(side="left")
            self.search_entry.bind("<Return>", lambda e: self.search_and_load())

            ttk.Button(top, text="Load Image", command=self.search_and_load).pack(side="left", padx=6)
            ttk.Button(top, text="Copy Current Image Name", command=self.copy_current_image_name).pack(side="left", padx=6)

            ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=8)

            ttk.Label(top, text="Paste crop filename:").pack(side="left", padx=(0, 6))
            self.crop_entry = ttk.Entry(top, textvariable=self.crop_name_var, width=32)
            self.crop_entry.pack(side="left")
            self.crop_entry.bind("<Return>", lambda e: self.load_from_crop_name())

            ttk.Button(top, text="Load From Crop Name", command=self.load_from_crop_name).pack(side="left", padx=6)

            ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=8)

            ttk.Label(top, text="Class focus:").pack(side="left", padx=(0, 6))
            self.class_combo = ttk.Combobox(top, textvariable=self.class_var, width=20, state="readonly")
            self.class_combo.pack(side="left")
            self.class_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_ui())

            ttk.Button(top, text="Refresh Classes", command=self.refresh_class_combo).pack(side="left", padx=6)

            ttk.Button(top, text="Prev Image (A)", command=self.prev_image).pack(side="right", padx=4)
            ttk.Button(top, text="Next Image (D)", command=self.next_image).pack(side="right", padx=4)

            status = ttk.Frame(self)
            status.pack(fill="x", padx=8, pady=(0, 4))
            ttk.Label(status, textvariable=self.info_var).pack(side="left")

            crop_status = ttk.Frame(self)
            crop_status.pack(fill="x", padx=8, pady=(0, 6))
            ttk.Label(crop_status, textvariable=self.crop_status_var).pack(side="left")

            body = ttk.Panedwindow(self, orient="horizontal")
            body.pack(fill="both", expand=True, padx=8, pady=6)

            left = ttk.Frame(body)
            right = ttk.Frame(body)

            body.add(left, weight=5)
            body.add(right, weight=2)

            self.canvas = tk.Canvas(left, bg="black", highlightthickness=0)
            self.canvas.pack(fill="both", expand=True)
            self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
            self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
            self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

            ttk.Label(right, text="Boxes in current image").pack(anchor="w")

            self.listbox = tk.Listbox(right)
            self.listbox.pack(fill="both", expand=False, pady=6)
            self.listbox.bind("<<ListboxSelect>>", self.on_list_select)

            btns = ttk.Frame(right)
            btns.pack(fill="x", pady=4)

            ttk.Button(btns, text="Delete Selected (Del)", command=self.delete_selected).pack(fill="x", pady=2)
            ttk.Button(btns, text="Relabel Selected (R)", command=self.relabel_selected).pack(fill="x", pady=2)
            ttk.Button(btns, text="Save Current JSON (S)", command=self.save_current).pack(fill="x", pady=2)
            ttk.Button(btns, text="Add BBox (N)", command=self.start_add_bbox).pack(fill="x", pady=2)
            ttk.Button(btns, text="Resize Selected (E)", command=self.start_resize_selected).pack(fill="x", pady=2)
            ttk.Button(btns, text="Cancel Edit Mode (Esc)", command=self.cancel_edit_mode).pack(fill="x", pady=2)

            ttk.Separator(right, orient="horizontal").pack(fill="x", pady=8)

            ttk.Label(right, text="Current image info").pack(anchor="w")
            self.meta_text = tk.Text(right, height=12, wrap="word")
            self.meta_text.pack(fill="both", expand=True)
            self.meta_text.configure(state="disabled")

        def _bind_keys(self):
            self.bind("<a>", lambda e: self.prev_image())
            self.bind("<A>", lambda e: self.prev_image())
            self.bind("<d>", lambda e: self.next_image())
            self.bind("<D>", lambda e: self.next_image())
            self.bind("<Delete>", lambda e: self.delete_selected())
            self.bind("<r>", lambda e: self.relabel_selected())
            self.bind("<R>", lambda e: self.relabel_selected())
            self.bind("<s>", lambda e: self.save_current())
            self.bind("<S>", lambda e: self.save_current())
            self.bind("<n>", lambda e: self.start_add_bbox())
            self.bind("<N>", lambda e: self.start_add_bbox())
            self.bind("<e>", lambda e: self.start_resize_selected())
            self.bind("<E>", lambda e: self.start_resize_selected())
            self.bind("<Escape>", lambda e: self.cancel_edit_mode())
            self.bind("<Control-f>", lambda e: self.search_entry.focus_set())

        # ----------------------------------------------------
        # Responsive rendering
        # ----------------------------------------------------
        def on_window_configure(self, event):
            if event.widget is not self:
                return
            if self.resize_after_id is not None:
                self.after_cancel(self.resize_after_id)
            self.resize_after_id = self.after(120, self.handle_resize)

        def handle_resize(self):
            self.resize_after_id = None
            if self.current_img_name and self.pil_img is not None:
                self.render_current_image()
                self.refresh_ui()

        def get_canvas_size(self):
            self.update_idletasks()
            cw = max(200, int(self.canvas.winfo_width()))
            ch = max(200, int(self.canvas.winfo_height()))
            return cw, ch

        def render_current_image(self):
            if self.pil_img is None:
                return

            cw, ch = self.get_canvas_size()
            w, h = self.pil_img.size

            sx = cw / w
            sy = ch / h
            self.scale = min(sx, sy)

            new_w = max(1, int(w * self.scale))
            new_h = max(1, int(h * self.scale))

            from PIL import Image, ImageTk
            resized = self.pil_img.resize((new_w, new_h), Image.BILINEAR)
            self.tk_img = ImageTk.PhotoImage(resized)

            self.offset_x = max(0, (cw - new_w) // 2)
            self.offset_y = max(0, (ch - new_h) // 2)

        # ----------------------------------------------------
        # Coordinate helpers
        # ----------------------------------------------------
        def image_to_canvas(self, x, y):
            return self.offset_x + x * self.scale, self.offset_y + y * self.scale

        def canvas_to_image(self, x, y):
            if self.pil_img is None:
                return None

            img_w, img_h = self.pil_img.size
            ix = (x - self.offset_x) / self.scale
            iy = (y - self.offset_y) / self.scale

            ix = max(0, min(img_w, ix))
            iy = max(0, min(img_h, iy))
            return ix, iy

        # ----------------------------------------------------
        # Background crop generation
        # ----------------------------------------------------
        def start_background_crop_generation(self):
            if not GENERATE_CROPS_IN_BACKGROUND:
                self.crop_status_var.set("Crop generation disabled")
                return

            if self.crop_thread is not None and self.crop_thread.is_alive():
                return

            self.crop_status_var.set("Crop generation started in background...")
            self.crop_thread = threading.Thread(
                target=export_class_crops_worker,
                args=(self.img_list_all, self.progress_queue),
                daemon=True
            )
            self.crop_thread.start()

        def poll_progress_queue(self):
            try:
                while True:
                    item = self.progress_queue.get_nowait()
                    if item["type"] == "progress":
                        done = item["done"]
                        total = item["total"]
                        image = item["image"]
                        crops = item["crops"]
                        self.crop_status_var.set(
                            f"Generating crops: {done}/{total} images | last: {image} | crops saved: {crops}"
                        )
                    elif item["type"] == "done":
                        self.crop_status_var.set(
                            f"Crop generation finished | images: {item['total_images']} | crops: {item['total_crops']}"
                        )
            except Empty:
                pass

            self.after(200, self.poll_progress_queue)

        # ----------------------------------------------------
        # Class list
        # ----------------------------------------------------
        def refresh_class_combo(self):
            self.info_var.set("Scanning classes... please wait")
            self.update_idletasks()

            labels = set()
            for img_name in self.img_list_all:
                json_path = json_for_image(img_name)
                if not os.path.exists(json_path):
                    continue
                try:
                    data = load_json(json_path)
                except Exception:
                    continue
                for sh in shapes_from_json(data):
                    if sh.get("shape_type") != "rectangle":
                        continue
                    lab = get_base_label(sh.get("label", ""))
                    if lab:
                        labels.add(lab)

            values = ["(all)"] + sorted(labels, key=str.lower)
            self.class_combo["values"] = values
            if self.class_var.get() not in values:
                self.class_var.set("(all)")

            self.info_var.set(f"Loaded {len(values) - 1} classes")

        # ----------------------------------------------------
        # Search / load
        # ----------------------------------------------------
        def load_image_by_name(self, query_name):
            query = Path(query_name).stem.lower().strip()
            if not query:
                return False

            hit = None
            for img_name in self.img_list_all:
                stem = Path(img_name).stem.lower()
                full = img_name.lower()
                if query == stem or query == full or query in stem or query in full:
                    hit = img_name
                    break

            if hit is None:
                messagebox.showwarning("Not found", f"No image found for: {query_name}")
                return False

            self.open_image(hit)
            return True

        def search_and_load(self):
            q = self.search_var.get().strip()
            if not q:
                return
            self.load_image_by_name(q)

        def load_from_crop_name(self):
            crop_name = self.crop_name_var.get().strip()
            if not crop_name:
                return

            img_stem = match_image_stem_from_crop_name(crop_name)
            cls = match_class_from_crop_name(crop_name)

            self.search_var.set(img_stem)
            ok = self.load_image_by_name(img_stem)

            if ok and cls:
                current_values = list(self.class_combo["values"])
                for v in current_values:
                    if v.lower() == cls.lower():
                        self.class_var.set(v)
                        break
                self.refresh_ui()

        def open_image(self, img_name):
            self.current_img_name = img_name
            self.current_img_path = os.path.join(IMG_DIR, img_name)
            self.current_json_path = json_for_image(img_name)

            if not os.path.exists(self.current_json_path):
                self.data = {"shapes": []}
            else:
                self.data = load_json(self.current_json_path)

            shapes_from_json(self.data)

            if STRIP_CONF_ALWAYS and os.path.exists(self.current_json_path):
                changed = False
                for sh in self.data["shapes"]:
                    old = sh.get("label", "")
                    new = strip_conf(old)
                    if new != old:
                        sh["label"] = new
                        changed = True
                if changed:
                    save_json(self.data, self.current_json_path)

            from PIL import Image
            try:
                self.pil_img = Image.open(self.current_img_path).convert("RGB")
            except Exception as e:
                messagebox.showerror("Image Error", f"Failed to open image:\n{self.current_img_path}\n\n{e}")
                return

            self.selected_shape_idx = None
            self.cancel_edit_mode(silent=True)
            self.render_current_image()
            self.refresh_ui()

        # ----------------------------------------------------
        # Edit mode helpers
        # ----------------------------------------------------
        def start_add_bbox(self):
            self.edit_mode = "add"
            self.drag_start = None
            self.dragging = False
            if self.temp_rect_id is not None:
                self.canvas.delete(self.temp_rect_id)
                self.temp_rect_id = None
            self.info_var.set("Mode: ADD BBOX | drag on image to create a new box")

        def start_resize_selected(self):
            if self.selected_shape_idx is None or self.data is None:
                messagebox.showwarning("No selection", "Select a bbox first, then click Resize Selected.")
                return

            shapes = self.data.get("shapes", [])
            if not (0 <= self.selected_shape_idx < len(shapes)):
                return

            self.edit_mode = "resize"
            self.drag_start = None
            self.dragging = False
            if self.temp_rect_id is not None:
                self.canvas.delete(self.temp_rect_id)
                self.temp_rect_id = None
            self.info_var.set("Mode: RESIZE BBOX | drag a new rectangle to replace the selected bbox")

        def cancel_edit_mode(self, silent=False):
            self.edit_mode = "select"
            self.drag_start = None
            self.dragging = False
            if self.temp_rect_id is not None:
                self.canvas.delete(self.temp_rect_id)
                self.temp_rect_id = None
            if not silent:
                self.info_var.set("Mode: SELECT")

        def finish_add_bbox(self, x0, y0, x1, y1):
            label = simpledialog.askstring(
                "New BBox Label",
                "Enter label for new bbox:",
                initialvalue=self.class_var.get() if self.class_var.get() != "(all)" else ""
            )

            if not label:
                return

            new_shape = {
                "label": label.strip(),
                "points": [[x0, y0], [x1, y1]],
                "group_id": None,
                "description": "",
                "shape_type": "rectangle",
                "flags": {}
            }

            shapes = self.data.get("shapes", [])
            shapes.append(new_shape)
            self.selected_shape_idx = len(shapes) - 1
            self.save_current(silent=True)
            messagebox.showinfo("Added", f"New bbox added with label: {label.strip()}")

        def finish_resize_bbox(self, x0, y0, x1, y1):
            if self.selected_shape_idx is None:
                return

            shapes = self.data.get("shapes", [])
            if not (0 <= self.selected_shape_idx < len(shapes)):
                return

            sh = shapes[self.selected_shape_idx]
            if sh.get("shape_type") != "rectangle":
                messagebox.showwarning("Unsupported", "Only rectangle shapes can be resized.")
                return

            sh["points"] = [[x0, y0], [x1, y1]]
            self.save_current(silent=True)
            messagebox.showinfo("Updated", "Selected bbox size/position updated.")

        # ----------------------------------------------------
        # Draw
        # ----------------------------------------------------
        def refresh_ui(self):
            self.canvas.delete("all")
            self.listbox.delete(0, tk.END)
            self.box_items = []
            self.shape_to_listbox_row = {}

            if self.tk_img is None or self.data is None:
                self.info_var.set("No image loaded.")
                self.set_meta_text("No image loaded.")
                return

            self.canvas.create_image(self.offset_x, self.offset_y, anchor="nw", image=self.tk_img)

            focus_cls = self.class_var.get().strip().lower()
            shapes = self.data.get("shapes", [])
            row = 0

            for i, sh in enumerate(shapes):
                if sh.get("shape_type") != "rectangle":
                    continue

                rect = normalize_rect_points(sh.get("points", []))
                if rect is None:
                    continue

                x1, y1, x2, y2 = rect
                label = get_base_label(sh.get("label", ""))
                selected = (i == self.selected_shape_idx)

                sx1 = self.offset_x + x1 * self.scale
                sy1 = self.offset_y + y1 * self.scale
                sx2 = self.offset_x + x2 * self.scale
                sy2 = self.offset_y + y2 * self.scale

                outline_color = BOX_COLOR_SELECTED if selected else BOX_COLOR_ALL
                text_color = TEXT_COLOR_SELECTED if selected else TEXT_COLOR_ALL
                width = 3 if selected else 2

                if focus_cls != "(all)" and focus_cls and label.lower() != focus_cls and not selected:
                    width = 1

                rect_id = self.canvas.create_rectangle(
                    sx1, sy1, sx2, sy2,
                    outline=outline_color,
                    width=width
                )

                txt_id = self.canvas.create_text(
                    sx1 + 4, sy1 + 4,
                    anchor="nw",
                    text=f"{i:04d} | {label}",
                    fill=text_color,
                    font=(LABEL_FONT_FAMILY, LABEL_FONT_SIZE, "bold")
                )

                self.box_items.append((rect_id, txt_id, i))
                self.shape_to_listbox_row[i] = row
                self.listbox.insert("end", f"{i:04d} | {label}")
                row += 1

            if self.selected_shape_idx in self.shape_to_listbox_row:
                lb_row = self.shape_to_listbox_row[self.selected_shape_idx]
                self.listbox.selection_clear(0, "end")
                self.listbox.selection_set(lb_row)
                self.listbox.see(lb_row)

            self.set_meta_text(
                json.dumps({
                    "image_name": self.current_img_name,
                    "json_path": self.current_json_path,
                    "selected_shape_idx": self.selected_shape_idx,
                    "class_focus": self.class_var.get(),
                    "crop_name_pasted": self.crop_name_var.get().strip(),
                    "edit_mode": self.edit_mode,
                }, indent=2, ensure_ascii=False)
            )

        def set_meta_text(self, text):
            self.meta_text.configure(state="normal")
            self.meta_text.delete("1.0", "end")
            self.meta_text.insert("1.0", text)
            self.meta_text.configure(state="disabled")

        # ----------------------------------------------------
        # Navigation
        # ----------------------------------------------------
        def prev_image(self):
            if self.current_img_name is None:
                return
            idx = self.img_list_all.index(self.current_img_name)
            if idx > 0:
                self.open_image(self.img_list_all[idx - 1])

        def next_image(self):
            if self.current_img_name is None:
                return
            idx = self.img_list_all.index(self.current_img_name)
            if idx < len(self.img_list_all) - 1:
                self.open_image(self.img_list_all[idx + 1])

        # ----------------------------------------------------
        # Canvas interaction
        # ----------------------------------------------------
        def on_canvas_press(self, event):
            if self.tk_img is None:
                return

            if self.edit_mode == "select":
                x, y = event.x, event.y
                hits = []

                for rect_id, txt_id, shape_idx in self.box_items:
                    x1, y1, x2, y2 = self.canvas.coords(rect_id)
                    if x1 <= x <= x2 and y1 <= y <= y2:
                        area = max(1, (x2 - x1) * (y2 - y1))
                        hits.append((area, shape_idx))

                if hits:
                    hits.sort(key=lambda t: t[0])
                    self.selected_shape_idx = hits[0][1]
                    self.refresh_ui()
                return

            self.drag_start = (event.x, event.y)
            self.dragging = True

            if self.temp_rect_id is not None:
                self.canvas.delete(self.temp_rect_id)
                self.temp_rect_id = None

            self.temp_rect_id = self.canvas.create_rectangle(
                event.x, event.y, event.x, event.y,
                outline=TEMP_BOX_COLOR,
                width=2,
                dash=(4, 2)
            )

        def on_canvas_drag(self, event):
            if not self.dragging or self.temp_rect_id is None:
                return

            x0, y0 = self.drag_start
            self.canvas.coords(self.temp_rect_id, x0, y0, event.x, event.y)

        def on_canvas_release(self, event):
            if self.edit_mode not in ("add", "resize"):
                return
            if not self.dragging or self.drag_start is None:
                return

            x0, y0 = self.drag_start
            x1, y1 = event.x, event.y
            self.dragging = False

            if self.temp_rect_id is not None:
                self.canvas.delete(self.temp_rect_id)
                self.temp_rect_id = None

            p0 = self.canvas_to_image(x0, y0)
            p1 = self.canvas_to_image(x1, y1)

            if p0 is None or p1 is None:
                self.cancel_edit_mode()
                return

            ix0, iy0 = p0
            ix1, iy1 = p1

            ix0, ix1 = sorted([float(ix0), float(ix1)])
            iy0, iy1 = sorted([float(iy0), float(iy1)])

            if abs(ix1 - ix0) < 3 or abs(iy1 - iy0) < 3:
                self.info_var.set("Ignored very small bbox")
                self.cancel_edit_mode()
                return

            if self.edit_mode == "add":
                self.finish_add_bbox(ix0, iy0, ix1, iy1)
            elif self.edit_mode == "resize":
                self.finish_resize_bbox(ix0, iy0, ix1, iy1)

            self.cancel_edit_mode()
            self.refresh_ui()

        # ----------------------------------------------------
        # Select from list
        # ----------------------------------------------------
        def on_list_select(self, event):
            sel = self.listbox.curselection()
            if not sel:
                return
            line = self.listbox.get(int(sel[0]))
            shape_idx = int(line.split("|")[0].strip())
            self.selected_shape_idx = shape_idx
            self.refresh_ui()

        # ----------------------------------------------------
        # Edit existing JSON
        # ----------------------------------------------------
        def delete_selected(self):
            if self.selected_shape_idx is None or self.data is None:
                return

            shapes = self.data.get("shapes", [])
            if not (0 <= self.selected_shape_idx < len(shapes)):
                return

            label = get_base_label(shapes[self.selected_shape_idx].get("label", ""))
            ok = messagebox.askyesno(
                "Confirm Delete",
                f"Delete bbox?\n\nImage: {self.current_img_name}\nShape idx: {self.selected_shape_idx}\nLabel: {label}"
            )
            if not ok:
                return

            del shapes[self.selected_shape_idx]
            self.selected_shape_idx = None
            self.save_current(silent=True)
            self.refresh_ui()

        def relabel_selected(self):
            if self.selected_shape_idx is None or self.data is None:
                return

            shapes = self.data.get("shapes", [])
            if not (0 <= self.selected_shape_idx < len(shapes)):
                return

            old = get_base_label(shapes[self.selected_shape_idx].get("label", ""))
            new = simpledialog.askstring("Relabel", f"Old label: {old}\nNew label:", initialvalue=old)
            if not new:
                return

            shapes[self.selected_shape_idx]["label"] = new.strip()
            self.save_current(silent=True)
            self.refresh_ui()

        def save_current(self, silent=False):
            if self.data is None or not self.current_json_path:
                return

            self.data["imagePath"] = self.current_img_name
            if self.pil_img is not None:
                w, h = self.pil_img.size
                self.data["imageWidth"] = int(w)
                self.data["imageHeight"] = int(h)

            if STRIP_CONF_ALWAYS:
                for sh in self.data.get("shapes", []):
                    sh["label"] = strip_conf(sh.get("label", ""))

            save_json(self.data, self.current_json_path)

            if not silent:
                messagebox.showinfo("Saved", self.current_json_path)

        def copy_current_image_name(self):
            if not self.current_img_name:
                return
            stem = Path(self.current_img_name).stem
            self.clipboard_clear()
            self.clipboard_append(stem)
            self.update()
            messagebox.showinfo("Copied", f"Copied image name:\n{stem}")

    app = App()
    app.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n=== GUI CRASH ===", flush=True)
        print(str(e), flush=True)
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")