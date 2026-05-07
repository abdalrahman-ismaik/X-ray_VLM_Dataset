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

The GUI opens maximized by default. The first tab in the right panel is `Workflow`, which lists the same review sequence inside the app.

1. Choose the dataset root that contains `images/` and `json/`.
2. Click `Index Dataset` to build the manifest and partition list. This does not generate crops.
3. Select one partition, such as `part-0001`.
4. Click `Generate Crops` for the selected partition, or `Resume` if crops already exist.
5. After crops load, the Dataset and Partition controls collapse automatically to give the main review area more space.
6. Browse crops from the left panel using filters, `Previous`, and `Next`.
7. Use the `Preview` tab for selected partition source-image browsing and crop selection source context.
8. In Annotation Editor mode, select boxes directly, cycle overlapping boxes with repeated clicks, use `Draw Box` with an approved PIDRay label, move or resize selected boxes, `Relabel Box`, `Delete Box`, or `Cancel Box Edit`.
9. Review the shared `Pending` tab and click `Save Pending` when crop corrections and annotation edits are correct.
10. Saves are atomic, and saved annotation edits trigger affected-image-only crop refresh when a crop manifest exists.

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

The GUI now includes a crop browser with:

- crop list by selected partition
- class, status, and search filters
- previous/next crop navigation
- source image preview
- selected crop preview
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

Click `Index Dataset`.

This creates a stable dataset manifest and partition list. Indexing runs in the background so the GUI remains responsive.

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
- inspect the source image and crop preview
- open the full source preview

### 7. Use Annotation Editor Mode

Open the `Preview` tab after selecting a partition. The Annotation Editor supports source-image browsing before crops exist, so you can inspect and fix annotations without generating the selected partition crops first.

The editor workflow is:

1. Use `Previous Image` and `Next Image` to browse source images in the selected partition.
2. Select a crop from the crop table when crops exist; crop selection loads the source context and highlights the matching bounding box.
3. Click an existing bounding box to select it. When boxes overlap, repeated clicks at the same canvas point cycle through the overlapping boxes.
4. Use `Draw Box`, drag a rectangle in any direction, and choose an approved PIDRay label for the new annotation.
5. Drag the selected box body to move it, or drag a corner handle to resize it.
6. Use `Relabel Box` to change a selected box label to an approved PIDRay label.
7. Use `Delete Box` to stage deletion of a selected box.
8. Use `Cancel Box Edit` to remove pending edits for the selected box before saving.
9. Review all crop corrections and annotation-editor edits in the same `Pending` tab.
10. Use the one shared `Save Pending` action to write annotation JSON atomically.
11. After saving annotation edits, the GUI performs affected-image-only crop refresh when crops exist for the selected partition.

Original image files are never modified. Unsupported shapes and unrelated JSON fields are preserved when supported rectangular boxes are edited.

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

### 9. Run Utilities From The GUI

Open the `Utilities` tab for:

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
