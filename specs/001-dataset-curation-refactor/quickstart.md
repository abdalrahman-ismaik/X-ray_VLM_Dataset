# Quickstart: Dataset Curation Refactor

This quickstart describes the target workflow after the refactor is implemented.

## 1. Prepare the Project

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## 2. Validate the Dataset Layout

Expected current layout:

```text
batch_1/
├── images/
├── json/
└── curation/       # created by the app
```

Run the dataset index preview:

```powershell
.\.venv\Scripts\python.exe -m xray_curation.cli index --dataset batch_1 --preview
```

Expected result:

- Reports image and annotation counts.
- Reports missing/corrupt pairs as warnings.
- Creates no crops in preview mode.

## 3. Launch the GUI

```powershell
.\.venv\Scripts\python.exe -m xray_curation
```

Expected first screen:

- Dataset selector.
- Partition selector showing 10,000-image partitions.
- Crop status for the selected partition.
- Actions for generate/resume/refresh/rebuild.

## 4. Generate Crops for One Partition

1. Select `batch_1`.
2. Select a partition, for example `part-0001`.
3. Choose `Generate/Resume Crops`.
4. Keep working while progress updates appear.

Expected result:

- Only the selected partition is processed.
- Crops and `crop_manifest.json` are created under `batch_1/curation/partitions/part-0001/`.
- The GUI does not require deleting existing crop folders to resume.

## 5. Browse and Correct Crops

1. Open the crop browser tab.
2. Filter by class label, source image, status, or text query.
3. Select a crop to open its source image and bounding box.
4. Relabel, rename, move group, or soft-delete from the GUI.
5. Review pending changes.
6. Save/commit approved changes.

Expected result:

- The crop remains linked to the correct bounding box through stable identity.
- Deletions are pending until confirmed.
- Annotation JSON changes are summarized before apply.

## 6. Run Integrated Utilities

From the GUI:

- `Standardize Labels`
- `Detect Missing Crops`
- `Import External Moved Crops`
- `Refresh Changed Crops`
- `Save Pending Changes`

Expected result:

- Each utility shows a preview or summary.
- Unknown labels are flagged for review.
- External/manual crop-folder moves are applied only through explicit import/apply.

## 7. Run Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit
.\.venv\Scripts\python.exe -m pytest tests\integration
```

Minimum test coverage for the first implementation pass:

- Label normalization and approved vocabulary.
- Stable partition assignment.
- Crop identity independent of filename/folder.
- Soft-delete and restore behavior.
- Annotation save preserves unrelated JSON fields.
- Partition crop generation processes only selected images.

## 8. Legacy Script Compatibility

During migration, existing scripts under `GUI_Dataset/` should become thin wrappers or launchers that call the new package services. They should stop containing hard-coded dataset paths and duplicated JSON/crop logic.

## 9. Current Implementation Commands

The completed refactor can be validated without scanning the full dataset:

```powershell
python -m pytest tests\unit
python -m pytest tests\integration
python -m compileall -q src GUI_Dataset
python GUI_Dataset\reviewProposals_gui.py --help
python GUI_Dataset\Add_NewClass.py --help
python GUI_Dataset\missing_crops_detector.py --help
python GUI_Dataset\Moved_crops_json_updation_utility.py --help
```

Expected results from the implementation pass:

- Unit tests: `22 passed`.
- Integration tests: `9 passed`.
- Compile check: no output and exit code 0.
- Legacy wrappers: help text is shown and no hard-coded dataset path is required.

The real dataset should only be used through an explicit selected partition, for example `part-0001`. Do not run crop generation across all partitions at once.
