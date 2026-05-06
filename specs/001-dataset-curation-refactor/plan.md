# Implementation Plan: Dataset Curation Refactor

**Branch**: `001-dataset-curation-refactor` | **Date**: 2026-05-06 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/001-dataset-curation-refactor/spec.md`

## Summary

Refactor the current VLM/X-ray dataset curation scripts into a small Python application with a reusable service layer, a Tkinter GUI shell, and file-backed curation state. The refactor keeps the current image/JSON dataset as the source of truth, treats crops as derived artifacts, partitions crop generation into deterministic 10,000-image parts, adds in-GUI crop browsing and operations, and standardizes labels to the approved PIDRay class vocabulary.

The migration path is incremental: extract shared helpers from `GUI_Dataset/reviewProposals_gui.py`, `Add_NewClass.py`, `missing_crops_detector.py`, and `Moved_crops_json_updation_utility.py` into tested services first, then replace the GUI internals with calls to those services while preserving the familiar review workflow.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Tkinter/ttk, Pillow, tqdm for legacy CLI progress during migration, pytest for tests  
**Storage**: Existing image files and annotation JSON remain primary; partition manifests, crop manifests, operation logs, and generated crops are derived local files  
**Testing**: pytest unit tests for services, integration tests over small fixture datasets, and manual GUI smoke tests  
**Target Platform**: Windows desktop first, with path handling kept portable through `pathlib`  
**Project Type**: Local desktop curation application plus reusable Python package and optional CLI wrappers  
**Performance Goals**: Partition crop generation handles 10,000 images per run; GUI startup avoids full-dataset crop generation; crop refresh processes only changed images; GUI event handlers return quickly during long operations  
**Constraints**: Offline/local filesystem workflow; original images are immutable; annotation updates require reviewable summaries for destructive operations; Tkinter UI calls stay on the main thread; crop identity must not depend on filename or class folder  
**Scale/Scope**: Current dataset scale is 56,176 image/annotation pairs in `batch_1`; design targets multiple batches with the same images/json/curation pattern

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The project constitution is still the initialized placeholder, so no ratified project-specific gates exist yet. Until the constitution is completed, this plan applies the following interim gates from the feature spec and engineering standards:

- **Source data safety**: Original image files are never modified; destructive annotation changes require a pending/preview state.
- **Derived data reproducibility**: Crops are regenerated from annotations and manifest state, not treated as the source of truth.
- **Stable identity**: Crop operations update the intended bounding box through stable manifest/annotation identity, not folder names or rectangle order alone.
- **GUI responsiveness**: Long-running crop generation and validation work must not block the Tkinter event loop.
- **Testable services**: Dataset, annotation, label, crop, partition, and operation logic must be testable without launching the GUI.

Initial gate status: PASS. No known violations.

## Current Architecture Findings

- `GUI_Dataset/reviewProposals_gui.py` hard-codes dataset paths at lines 18-22 and owns configuration, JSON I/O, label cleanup, crop generation, canvas rendering, editing, and saving in one file.
- `reviewProposals_gui.py` generates crops in `export_class_crops_worker()` at line 141 and starts generation automatically from the GUI at line 519, with a guard that skips generation when the crop folder is not empty.
- `reviewProposals_gui.py` has GUI-bound operations for class refresh, crop-name lookup, delete, relabel, save current, and save all at lines 573, 689, 1280, 1301, 1318, and 1353.
- `GUI_Dataset/Add_NewClass.py` duplicates much of the GUI and crop generation logic, but still uses different hard-coded absolute paths at lines 12-14.
- `GUI_Dataset/missing_crops_detector.py` repeats JSON/label helpers and expects crop filenames from labels and indexes; its index convention uses `bbox_idx + 1` at line 192.
- `GUI_Dataset/Moved_crops_json_updation_utility.py` uses old absolute paths at lines 31-32, treats the current class folder as the target class at line 133, and maps filename index to JSON shape index at line 204.
- Current crop folder names include legacy/derived class folder names and can drift from the approved label vocabulary. The plan must remove folder names as the authoritative correction mechanism.

## Project Structure

### Documentation (this feature)

```text
specs/001-dataset-curation-refactor/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── curation-operations.md
└── tasks.md              # created later by /speckit-tasks
```

### Source Code (repository root)

```text
pyproject.toml
src/
└── xray_curation/
    ├── __init__.py
    ├── __main__.py
    ├── config.py
    ├── domain/
    │   ├── annotations.py
    │   ├── crops.py
    │   ├── labels.py
    │   ├── operations.py
    │   └── partitions.py
    ├── services/
    │   ├── annotation_store.py
    │   ├── crop_generator.py
    │   ├── crop_manifest.py
    │   ├── dataset_index.py
    │   ├── label_standardizer.py
    │   └── validation.py
    ├── gui/
    │   ├── app.py
    │   ├── state.py
    │   ├── crop_browser.py
    │   ├── image_review.py
    │   ├── operation_panels.py
    │   └── workers.py
    ├── cli.py
    └── legacy/
        ├── reviewProposals_gui.py
        ├── missing_crops_detector.py
        └── moved_crops_update.py

tests/
├── fixtures/
│   └── small_dataset/
├── unit/
│   ├── test_labels.py
│   ├── test_partitions.py
│   ├── test_crop_identity.py
│   └── test_annotation_store.py
└── integration/
    ├── test_partition_crop_generation.py
    ├── test_label_standardization.py
    └── test_operation_commit.py

GUI_Dataset/
└── ...                  # legacy scripts kept during migration, then converted to thin wrappers

batch_1/
├── images/
├── json/
└── curation/
    ├── dataset_manifest.json
    ├── operation_log.jsonl
    └── partitions/
        ├── part-0001/
        │   ├── partition.json
        │   ├── crop_manifest.json
        │   └── crops/
        └── part-0002/
            └── ...
```

**Structure Decision**: Use a `src/` package layout for importable code and tests, keep existing `GUI_Dataset/` scripts as legacy entry points during migration, and write derived curation artifacts under each dataset batch instead of mixing generated state into source code folders.

## Phase 0: Research Decisions

See [research.md](research.md). Key decisions:

- Package core logic under `src/xray_curation` to separate importable application code from dataset assets and legacy scripts.
- Keep Tkinter, but move long-running operations into worker services with main-thread UI updates.
- Use a file-backed partition/crop manifest, not crop filenames or class folders, as the identity and state source for crops.
- Treat crop generation as a reproducible data-processing stage over selected partitions.
- Standardize labels through a shared vocabulary module and reviewable migration workflow.

## Phase 1: Design Decisions

See [data-model.md](data-model.md) and [contracts/curation-operations.md](contracts/curation-operations.md).

- Add or mirror stable bounding-box identities so crop records survive label changes, class moves, filename changes, and soft deletion.
- Introduce pending changes and operation summaries as first-class concepts.
- Make the GUI call services for crop generation, crop browsing, label changes, missing-crop detection, moved-crop import, and commit/revert.
- Keep crop folders as derived/cache outputs. Class grouping in the GUI comes from the manifest and label vocabulary.

## Post-Design Constitution Check

Interim gates rechecked after Phase 1 design:

- **Source data safety**: PASS. Original images remain immutable, annotation changes use pending changes and summaries.
- **Derived data reproducibility**: PASS. Crops are generated from annotations and partition manifests.
- **Stable identity**: PASS. Crop records are keyed by stable IDs independent of folder/name.
- **GUI responsiveness**: PASS. Long operations are modeled as worker-backed operations with progress events.
- **Testable services**: PASS. Core logic lives outside Tkinter views and is testable through service contracts.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Manifest-backed crop identity | Required to safely rename, relabel, move, soft-delete, and refresh crops without losing bbox links | Filename/order-only identity is already fragile and conflicts with the clarified requirements |
| Service layer between GUI and files | Required to run utilities inside the GUI and test workflows without launching Tkinter | Keeping all behavior in the GUI script preserves the current duplication and stale-state problems |
| Per-partition curation state | Required to resume 10,000-image chunks and avoid full-dataset regeneration | A single global crop folder forces manual deletion/regeneration and hides which images are current |
