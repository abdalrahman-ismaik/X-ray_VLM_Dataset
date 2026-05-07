# Quickstart: Annotation Editor Restoration

This quickstart describes the intended reviewer workflow after the feature is implemented.

## Launch The Refactored GUI

From the repository root:

```powershell
python run_gui.py --dataset tests\fixtures\small_dataset
```

For production use, choose the real dataset folder from the GUI. During implementation and tests, use fixtures or selected partitions only.

## Prepare A Partition

1. Choose the dataset root.
2. Keep the partition size at `10000` unless you are using a smaller fixture.
3. Click `Index Dataset`.
4. Select the partition you want to work on.

The Annotation Editor must be able to browse source images after this step, even before crops are generated.

## Browse And Edit Source Annotations

1. Open the Preview area and choose Annotation Editor mode.
2. Use source-image navigation to open an image from the selected partition.
3. Inspect all visible rectangular boxes on the image.
4. Click a box to select it.
5. If boxes overlap, click the same point repeatedly to cycle through them.
6. Use draw mode to drag a new rectangle.
7. Choose an approved PIDRay label before staging the new box.
8. Move or resize an existing selected box with the canvas controls.
9. Relabel or delete the selected box when needed.

All edits are staged first. The annotation JSON is not changed until Save Pending is used.

## Save Pending Changes

Use the shared `Save Pending` action after reviewing the pending list.

Expected save behavior:

- Crop corrections and annotation-editor edits are saved from one queue.
- Annotation JSON is written atomically.
- Original image files are never modified.
- Unsupported shapes and unrelated JSON fields are preserved.
- Stable bounding-box IDs are preserved or assigned.
- If crops exist for the selected partition, only affected image crops are refreshed.
- If crops do not exist yet, the annotation save completes and crops can be generated later.

## Generate Or Refresh Crops

Use `Generate Crops` only for the selected partition. Do not generate crops for the full production dataset in one run.

After annotation edits are saved:

- Existing selected-partition crop state should refresh only affected images.
- `Refresh Changed` remains available for broader selected-partition recovery.
- `Rebuild Partition` is for explicit selected-partition rebuilds, not default annotation editing.

## Validation Commands For Implementation

Run focused tests for the annotation editor feature:

```powershell
python -m pytest tests\unit\test_annotation_editor_service.py tests\unit\test_annotation_editor_geometry.py tests\unit\test_annotation_editor_pending.py tests\integration\test_annotation_editor_workflow.py tests\integration\test_annotation_editor_pre_crop_browsing.py
```

Run the broader existing suite when the feature is integrated:

```powershell
python -m pytest tests\unit tests\integration
```

Compile check:

```powershell
python -m compileall -q src GUI_Dataset run_gui.py
```

## Phase 7 Validation Results

Recorded on 2026-05-07 using fixture annotations, fixture crops, synthetic manifests, and selected-partition state only. No full-dataset scan was performed and no crops were generated for all 56,176 images.

- Focused annotation-editor unit validation:

  ```powershell
  python -m pytest tests\unit\test_annotation_editor_service.py tests\unit\test_annotation_editor_geometry.py tests\unit\test_annotation_editor_pending.py tests\unit\test_affected_crop_refresh.py tests\unit\test_annotation_editor_guidance.py
  ```

  Result: passed, 30 tests.

- Focused annotation-editor integration validation:

  ```powershell
  python -m pytest tests\integration\test_annotation_editor_workflow.py tests\integration\test_annotation_editor_pre_crop_browsing.py
  ```

  Result: passed, 6 tests.

- Final focused annotation-editor validation after wrapper review:

  ```powershell
  python -m pytest tests\unit\test_annotation_editor_service.py tests\unit\test_annotation_editor_geometry.py tests\unit\test_annotation_editor_pending.py tests\unit\test_affected_crop_refresh.py tests\unit\test_annotation_editor_guidance.py tests\integration\test_annotation_editor_workflow.py tests\integration\test_annotation_editor_pre_crop_browsing.py
  ```

  Result: passed, 36 tests.

- Broader fixture-based regression suite:

  ```powershell
  python -m pytest tests
  ```

  Result: passed, 67 tests.

- Compile check:

  ```powershell
  python -m compileall -q src GUI_Dataset run_gui.py
  ```

  Result: passed.

## Phase 7 Boundary Review

- Legacy compatibility: `src/xray_curation/legacy/reviewProposals_gui.py` is a thin compatibility launcher for the refactored GUI and no longer contains the old monolithic GUI implementation.
- GUI boundary: `src/xray_curation/gui/annotation_editor.py` owns Tkinter canvas state, Pillow rendering, and user interaction. It calls service functions for source context, geometry, hit testing, and pending-change staging. It does not write annotation JSON directly.
- Service boundary: `src/xray_curation/services/annotation_editor.py` has no Tkinter or GUI imports. It owns source-image context loading, coordinate transforms, hit testing, rectangle validation, and annotation edit staging.
- Cross-artifact consistency: `spec.md`, `plan.md`, `contracts/annotation-editor.md`, `tasks.md`, and this quickstart all preserve selected-partition scope, shared pending save, atomic annotation JSON writes, stable bbox/crop identity, approved PIDRay labels, and affected-image-only crop refresh.
- Implementation caveat: automated validation covers service behavior, geometry, pending save, fixture integration, and import boundaries. A human visual click-through on one selected fixture or production partition is still recommended before high-volume production curation.

## Safety Rules

- Do not scan the full 56,176-image dataset during implementation or tests.
- Do not generate all production crops during implementation or tests.
- Use fixture annotations, fixture crops, synthetic manifests, and selected-partition state.
- Treat crops as derived artifacts and annotation JSON as the source of truth.
