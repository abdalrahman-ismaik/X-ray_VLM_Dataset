# X-ray VLM Dataset Curation

This project provides a local desktop workflow for cleaning and organizing X-ray image annotations for VLM and object-detection research. It refactors the original `GUI_Dataset` scripts into a structured Python package with a Tkinter GUI, reusable services, partitioned crop generation, stable crop identity, and approved PIDRay label standardization.

The refactor is based on the requirements in [spec.md](specs/001-dataset-curation-refactor/spec.md).

The project constitution is in [.specify/memory/constitution.md](.specify/memory/constitution.md).
It requires future refactors to preserve core legacy GUI workflows, including
source-image browsing, drawing new bounding boxes, assigning labels, selecting
and editing boxes, deleting boxes through a reviewable path, saving annotation
edits, and refreshing affected crops.

## Start Here: GUI Workflow

The recommended entry point is the new root runner:

```powershell
python run_gui.py --dataset dataset
```

The GUI opens maximized by default. The main review area is split into two workspace tabs: `Image Browser` and `Image Viewer`.

1. Choose the dataset root that contains `images/` and `json/`.
2. If `dataset/curation/dataset_manifest.json` already exists, the GUI loads the partition list automatically.
3. Click `Index Dataset` only the first time for a dataset, after adding/removing images, after changing partition size, or when you intentionally want to rebuild the index.
4. Select one partition, such as `part-0001`.
5. Click `Generate Crops` for the selected partition, or `Resume` if crops already exist.
6. After crops load, the Dataset and Partition controls collapse automatically to give the main review area more space.
7. Use `Image Browser` to browse crop thumbnails, or source-image thumbnails before crops exist. Ctrl/Shift-click selects multiple browser items for bulk class moves, soft-delete, or restore.
8. Use the `Image Browser` zoom slider to enlarge thumbnails and reduce the number of images per row.
9. Double-click an image in `Image Browser`, or select a crop from the table, to open `Image Viewer`.
10. `Image Viewer` contains only the source image preview with Annotation Editor tools and the selected crop preview.
11. Scroll over the source image to zoom; drag the zoomed background, middle mouse, or right mouse to pan around the image.
12. In Annotation Editor mode, select boxes directly; when a selected bounding box has a generated crop, the crop preview updates to that linked crop. Cycle overlapping boxes with repeated clicks, use `Draw Box` with an approved PIDRay label, move or resize selected boxes, `Relabel Box`, `Delete Box`, or `Cancel Box Edit`.
13. Review the shared `Pending` tab and click `Save Pending` when crop corrections and annotation edits are correct.
14. Saves are atomic, and saved annotation edits trigger affected-image-only crop refresh when a crop manifest exists.

For a safe test run without touching the main dataset:

```powershell
python run_gui.py --dataset tests\fixtures\small_dataset
```

## Why This Refactor Was Needed

The original workflow was useful, but it became difficult to maintain at the current dataset scale of 56,176 image/annotation pairs.

Main issues in the old code:

- Crop generation tried to operate on the full dataset at once, which was too heavy for practical review sessions.
- The GUI focused on one image at a time and did not provide a comfortable in-GUI crop browsing workflow.
- Important utilities required closing the GUI, saving JSON manually, and running separate scripts.
- Regenerating crops often required deleting existing crop folders and starting again.
- Class labels were inconsistent, including underscore variants such as `Electrical_Device` instead of `Electrical Device`.
- Several scripts duplicated JSON loading, crop generation, label cleanup, and path logic.
- Crop identity depended too much on filenames, class folders, or shape order, which made relabeling, moving, and deleting crops fragile.

## What Changed

The project now uses a `src/` package architecture. This is the real application code:

```text
src/xray_curation/
  domain/      Pure models and identity helpers
  services/    Dataset indexing, crop generation, manifests, validation, labels
  gui/         Tkinter application, crop browser, previews, worker UI
  cli.py       Optional command-line entry points
```

Legacy scripts in `GUI_Dataset/` are now thin launchers or wrappers around the new package. They are kept for backwards compatibility only:

- `reviewProposals_gui.py` launches the refactored GUI.
- `Add_NewClass.py` launches the refactored GUI.
- `missing_crops_detector.py` calls the selected-partition missing-crop service.
- `Moved_crops_json_updation_utility.py` calls the selected-partition external-move service.

This reduces duplicated logic and makes the behavior testable without launching the GUI.

## Key Improvements

### Partitioned Crop Generation

Instead of generating crops for all 56,176 images, the app builds deterministic partitions, normally 10,000 images each.

The reviewer selects a partition such as `part-0001`, then the GUI generates crops only for that partition. The final partition can contain fewer than 10,000 images and is handled normally.

This improves performance, recovery, and day-to-day review because work is split into manageable sessions.

### In-GUI Crop Browsing

The GUI now includes a crop browser and viewer workspace with:

- crop list by selected partition
- class, status, and search filters
- previous/next crop navigation
- `Image Browser` grid with vertical scrolling
- browser thumbnail zoom to enlarge previews and reduce images per row
- multi-select crop thumbnails for bulk class move, soft-delete, and restore
- `Image Viewer` with a large source image and Annotation Editor tools
- image viewer scroll zoom and drag panning for zoomed images
- bbox selection that updates the linked crop preview when crops exist
- selected crop preview beside the source image
- bounding-box overlay on the source image
- full preview window

This brings the crop-review workflow into the GUI instead of requiring manual folder browsing.

### Stable Crop and Bounding-Box Identity

Crops are linked to annotations through stable manifest and bounding-box IDs, not through folder names or crop filenames.

This allows a crop to be:

- relabeled
- renamed
- moved between class groups
- soft-deleted
- restored
- refreshed

without losing the link to the intended source image and bounding box.

### Safer Annotation Editing

Annotation JSON files remain the source of truth. Original image files are never modified.

Destructive changes use safer workflows:

- crop deletion starts as a pending soft-delete
- pending changes can be cancelled before saving
- save operations write annotation JSON atomically
- utilities guard against stale unsaved edits

### Integrated Utilities

The GUI now exposes utility workflows that previously required separate scripts:

- missing-crop detection
- external moved-crop import/apply
- label standardization
- refresh changed crops
- save pending changes

These operations run against the selected partition and produce reviewable summaries.

### Efficient Resume and Refresh

Each dataset root stores derived curation state under:

```text
dataset/curation/
  dataset_manifest.json
  operation_log.jsonl
  partitions/
    part-0001/
      partition.json
      state.json
      crop_manifest.json
      crops/
```

When annotations change after crops were generated, the app can refresh only affected images instead of rebuilding the whole partition.

### Approved PIDRay Labels

The approved class labels are centralized in `src/xray_curation/domain/labels.py`.

Labels use spaces, not underscores. For example:

- Correct: `Electrical Device`
- Incorrect: `Electrical_Device`

Unambiguous legacy labels can be mapped automatically. Unknown or ambiguous labels are reported for reviewer decision instead of being silently changed.

## Recommended Repository Layout

Use this layout for the refactored workflow:

```text
X-ray_VLM_Dataset/
  README.md
  run_gui.py
  pyproject.toml
  src/xray_curation/
  tests/
  docs/
  specs/
  dataset/
    images/
    json/
    curation/        # generated automatically
```

The old local folder name `batch_1` still works if you pass it explicitly:

```powershell
python run_gui.py --dataset batch_1
```

The refactored default is now `dataset`, so the cleanest long-term setup is:

```text
dataset/
  images/
  json/
```

The repository does not physically rename or move your existing `batch_1` folder automatically because it contains large research data. Rename it manually only when you are ready and have confirmed no other scripts depend on the old name.

## How To Use The GUI

### Practical Click-By-Click Workflow

Use this sequence for normal review work:

1. Start the app with `python run_gui.py --dataset dataset`.
2. Confirm the dataset root points to the folder that contains `images/` and `json/`.
3. Let the saved index load automatically, or click `Index Dataset` only if this dataset has not been indexed before or the image/JSON set changed.
4. Select one partition from the partition dropdown.
5. Click `Resume` if crops already exist for that partition. Click `Generate Crops` only when that selected partition has no crops yet.
6. Use `Image Browser` to visually browse thumbnails. Double-click an item to open it in `Image Viewer`.
7. Use the right-side `Crops` filters to choose the class/status/search sequence for thumbnails and Previous/Next crop navigation.
8. The right-side crop table shows the generated items inside the image currently open in `Image Viewer`, so you can select and edit different boxes from that same source image.
9. Use the `Image Viewer` tab to inspect the full source image, select bounding boxes, draw boxes, move/resize boxes, relabel, or delete boxes.
10. Every correction is staged first. Nothing important is written until you use `Save Pending`.
11. Open the right-side `Pending` tab before saving. If the list looks wrong, cancel the selected crop edit, cancel the selected box edit, restore, or restart that edit before saving.
12. Click `Save Pending` when the pending list is correct.

### What Happens When You Use Soft Delete

`Soft Delete` is a review-safe crop action. It is not the same as deleting an image file.

When you click `Soft Delete`:

- The original X-ray image is not changed.
- The source annotation JSON is not changed immediately.
- The crop image file is not immediately removed from disk.
- A pending `soft_delete` change is added to the shared `Pending` tab.

Before saving, you can still undo the staged change with `Cancel Selected` or stage `Restore`.

When you click `Save Pending`:

- The annotation JSON is written atomically.
- The selected bounding box remains in the JSON, but its `flags.curation_status` becomes `soft_deleted`.
- The selected crop record in `crop_manifest.json` is marked as `soft_deleted`.
- The selected crop file is moved out of the active class folder and into `crops/_soft_deleted/<Class Label>/`.
- The GUI reloads the manifest, crop table, thumbnail browser, source preview, and crop preview.

After saving:

- If the crop `Status` filter is `active`, the soft-deleted crop is hidden.
- If the crop `Status` filter is `All` or `soft_deleted`, the crop can still be reviewed.
- `Restore` can mark it active again.
- `Restore` moves the crop file back into the active `crops/<Class Label>/` folder.

Use `Delete Box` in the Annotation Editor only when the bounding box should be removed from the annotation JSON. `Delete Box` is stronger than `Soft Delete`: after `Save Pending`, the rectangular shape is removed from the source JSON and affected-image crops are refreshed when a crop manifest exists.

### What Save Pending Applies

`Save Pending` applies all staged changes together:

- Crop `Relabel` / `Move Group`: updates the source box label and the crop manifest label.
- Relabeled crop files move to the matching `crops/<New Class Label>/` folder after saving.
- `Rename`: stores a review display name in annotation flags and the crop manifest.
- `Soft Delete`: marks the box and crop manifest record as `soft_deleted`.
- `Restore`: marks the box and crop manifest record as `active`.
- `Draw Box`: adds a new rectangular shape with a stable bbox ID.
- Move/resize/relabel box: updates the selected rectangular shape.
- `Delete Box`: removes the selected rectangular shape from the JSON.

For annotation-editor edits, the GUI refreshes only the affected image crops after saving. It does not rebuild the full partition and never modifies original image files.

### 1. Start The GUI

From the repository root:

```powershell
python run_gui.py
```

To open a specific dataset root:

```powershell
python run_gui.py --dataset dataset
```

For a safe fixture test:

```powershell
python run_gui.py --dataset tests\fixtures\small_dataset
```

After installing the package in editable mode, you can also launch through the package CLI:

```powershell
python -m pip install -e .
```

```powershell
python -m xray_curation gui --dataset dataset
```

The old command still works as a compatibility wrapper, but it is no longer the recommended entry point:

```powershell
python GUI_Dataset\reviewProposals_gui.py --dataset dataset
```

### 2. Select The Dataset Root

Use the `Dataset root` field or `Browse` button.

The expected dataset layout is:

```text
dataset/
  images/
  json/
```

The GUI writes generated curation state to:

```text
dataset/curation/
```

### 3. Index The Dataset

If a saved manifest already exists, the GUI loads it automatically when the app opens or after you use `Browse`.

Click `Index Dataset` only when the dataset has no saved manifest, images or JSON files were added or removed, partition size changed, or you intentionally want to rebuild the index.

Indexing creates a stable dataset manifest and partition list. It runs in the background so the GUI remains responsive.

### 4. Select A Partition

Choose a partition from the partition dropdown, for example:

```text
part-0001 (10000 images)
```

Do not generate crops for all partitions at once. Work one selected partition at a time.

### 5. Generate Crops

Click `Generate Crops`.

The progress bar shows generation progress by image count. Crops are created only for the selected partition.

### 6. Browse And Review Crops

Use the crop browser to:

- filter by class
- filter by status
- search by crop/image identity
- move with `Previous` and `Next`
- inspect the source image and selected crop preview in `Image Viewer`
- browse crop/source thumbnails in the vertical `Image Browser` grid
- use the browser zoom slider to enlarge thumbnails and reduce the number of images per row
- Ctrl/Shift-click browser thumbnails to select multiple generated crops for bulk move, soft-delete, or restore
- double-click a browser image to open it in `Image Viewer`
- open the full source preview

### 7. Use Annotation Editor Mode

Open `Image Viewer` after selecting a partition. You can double-click a source image from `Image Browser`, use `Previous Image` and `Next Image`, or select a crop from the crop table. The Annotation Editor supports source-image browsing before crops exist, so you can inspect and fix annotations without generating the selected partition crops first.

Scroll over the image preview to zoom in or back out to the fitted view. When zoomed in, drag the image background, middle mouse, or right mouse to pan around the image without changing the original image file.

The editor workflow is:

1. Use `Previous Crop` and `Next Crop` to move through the current filtered crop list when crops are loaded. Before crops exist, these controls fall back to source-image browsing.
2. Select a crop from the crop table when crops exist; crop selection loads the source context and highlights the matching bounding box.
3. Click an existing bounding box to select it. If the selected bounding box has a generated crop, the crop preview switches to that crop automatically. When boxes overlap, repeated clicks at the same canvas point cycle through the overlapping boxes.
4. Use `Draw Box`, drag a rectangle in any direction, and choose an approved PIDRay label for the new annotation.
5. Drag the selected box body to move it, or drag a corner handle to resize it.
6. Use `Relabel Box` to change a selected box label to an approved PIDRay label.
7. Use `Delete Box` to stage deletion of a selected box.
8. Use `Cancel Box Edit` to remove pending edits for the selected box before saving.
9. Review all crop corrections and annotation-editor edits in the same `Pending` tab.
10. Use the one shared `Save Pending` action to write annotation JSON atomically.
11. After saving annotation edits, the GUI performs affected-image-only crop refresh when crops exist for the selected partition.

Original image files are never modified. Unsupported shapes and unrelated JSON fields are preserved when supported rectangular boxes are edited.

When generated crops are loaded, the viewer navigation buttons step through the current filtered crop list. For example, if the right-side `Crops` tab is filtered to `Box`, `Next Crop` opens the next `Box` crop instead of the next source image. Before crops exist, navigation falls back to source-image browsing.

### 8. Correct Labels Or Crop State

Select a crop, then use:

- `Relabel`
- `Rename`
- `Move Group`
- `Soft Delete`
- `Restore`
- `Cancel Selected`
- `Save Pending`

Changes are staged first. They are written to annotation JSON only when you save pending changes.

### 9. Run Tools From The GUI

Open the right-side `Tools` tab for:

- missing-crop detection
- external moved-crop import
- refresh

Open the label standardization area to:

- preview label standardization
- apply unambiguous approved-label mappings

Unknown labels are reported and left for review.

### 10. Resume Or Refresh Work

Use the top controls:

- `Resume`: load existing partition state and crop manifest
- `Refresh Changed`: regenerate crops only for images whose annotations changed
- `Rebuild Partition`: regenerate the selected partition intentionally

Use `Rebuild Partition` only when you really want to recreate the selected partition crops.

## Command-Line Utilities

The legacy utility script names still work, but they now call the new services.

Preview missing crops:

```powershell
python GUI_Dataset\missing_crops_detector.py --dataset dataset --partition-id part-0001
```

Stage missing-crop soft-deletes:

```powershell
python GUI_Dataset\missing_crops_detector.py --dataset dataset --partition-id part-0001 --stage
```

Preview external moved crops:

```powershell
python GUI_Dataset\Moved_crops_json_updation_utility.py --dataset dataset --partition-id part-0001 --external-root path\to\moved_crops
```

Apply external moved crops:

```powershell
python GUI_Dataset\Moved_crops_json_updation_utility.py --dataset dataset --partition-id part-0001 --external-root path\to\moved_crops --apply
```

## Safety Rules

- Original images are immutable and should not be edited by the app.
- Crops are derived artifacts and can be regenerated.
- Annotation JSON files are the source of truth.
- Work on one partition at a time.
- Use `Refresh Changed` for ordinary updates.
- Use `Rebuild Partition` only when a full selected-partition rebuild is intended.
- Do not commit raw dataset images, raw dataset JSON folders, generated crops, or `dataset/curation/` artifacts.

The `.gitignore` is configured to keep large local dataset files and generated curation artifacts out of Git.

## Tests

Run the automated tests:

```powershell
python -m pytest tests\unit tests\integration
```

Compile-check source and wrappers:

```powershell
python -m compileall -q src GUI_Dataset
```

The tests use small fixtures and synthetic manifests. They do not scan the full dataset or generate crops for all 56,176 images.

## Current Status

Implemented features include:

- deterministic partitioning
- selected-partition crop generation
- crop manifest creation
- in-GUI crop browsing
- source image and crop previews
- stable crop/bounding-box identity
- pending relabel, rename, move group, soft-delete, restore, and save
- missing-crop detection
- external moved-crop preview/apply
- label standardization preview/apply
- resume and refresh-changed workflow
- append-only operation log
- legacy script wrappers

The recommended next step is to use the GUI on a single real partition and verify the full review workflow before scaling partition-by-partition through the dataset.
