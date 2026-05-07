# Implementation Plan: Annotation Editor Restoration

**Branch**: `002-annotation-editor` | **Date**: 2026-05-07 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/002-annotation-editor/spec.md`

## Summary

Restore the legacy source-image annotation editor inside the refactored
X-ray/VLM curation GUI while preserving the new service-based architecture.
The implementation adds selected-partition source-image browsing, a canvas-based
Annotation Editor mode, all-box rendering, direct box selection, repeated-click
cycling for overlaps, new-box drawing, existing-box move/resize, relabel,
delete, one shared pending queue, atomic annotation saves, and automatic crop
refresh for only affected images.

The work extends existing domain and service layers instead of reviving the old
monolithic GUI. The GUI will call testable annotation-editor services for image
loading, coordinate transforms, hit testing, pending change staging, JSON
commit, and affected-image crop refresh. Tests and manual smoke checks use
fixtures, synthetic manifests, and selected-partition state only.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Tkinter/ttk for GUI, Pillow for image loading/rendering/crops, pytest for tests  
**Storage**: Existing source images and annotation JSON remain primary; generated crops, crop manifests, partition manifests, state files, and operation logs remain derived local files  
**Testing**: pytest unit tests for annotation editor services and coordinate logic; integration tests over `tests/fixtures/small_dataset`; manual GUI smoke tests for canvas interactions  
**Target Platform**: Windows desktop first, with portable path handling through `pathlib`  
**Project Type**: Local desktop curation application plus reusable Python package and compatibility wrappers  
**Performance Goals**: Load and render one selected source image quickly; stage canvas edits without blocking; save and refresh only images affected by pending annotation edits; never require a full-dataset crop rebuild for this feature  
**Constraints**: Original image files are immutable; annotation JSON writes are atomic; annotation edits are staged in one shared pending queue; Tkinter calls stay on the main thread; long save/refresh operations use worker callbacks; no full-dataset scans or all-dataset crop generation in implementation or tests  
**Scale/Scope**: Current production dataset scale is 56,176 image/annotation pairs, but this feature operates on selected partitions, fixture datasets, and synthetic manifests only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Source data integrity**: PASS. The plan keeps original images immutable,
  stages annotation edits, writes JSON atomically, and provides summaries before
  clearing pending changes.
- **Core workflow parity**: PASS. The plan restores source-image browsing,
  all-box display, box drawing, label assignment, box selection/editing,
  deletion through pending save, save, and affected-crop refresh.
- **Stable identity**: PASS. New and existing boxes use stable
  `curation_bbox_id` values; crop records remain linked through source image and
  bbox identity.
- **Derived artifact reproducibility**: PASS. Crops remain derived from
  annotation JSON and selected-partition manifests.
- **Responsive partitioned GUI**: PASS. The GUI works from a selected partition,
  supports editing before crop generation, and uses workers for save/refresh.
- **Testable services**: PASS. Coordinate transforms, hit testing, annotation
  loading, staging, commit, and affected-image refresh are planned as services
  testable without Tkinter.
- **Controlled vocabulary**: PASS. New and relabeled boxes use the centralized
  approved PIDRay label list with space-separated labels; unknown existing
  labels are shown for review rather than silently changed.

Initial gate status: PASS. No known violations.

## Current Architecture Findings

- `src/xray_curation/gui/image_review.py` currently renders a selected crop's
  source image as a Pillow bitmap with one rectangle drawn directly onto the
  image. It has no editable canvas state, no all-box rendering, no hit testing,
  and no mouse bindings for draw/move/resize.
- `src/xray_curation/services/annotation_store.py` already provides atomic JSON
  load/save, bbox ID assignment/preservation, crop-level pending changes, and
  grouped commit by annotation path. It needs annotation-edit operations for
  add, move/resize, relabel, and delete.
- `src/xray_curation/services/dataset_index.py` already persists selected
  partition manifests. It can support source-image browsing before crops exist
  by loading image records from the selected partition manifest.
- `src/xray_curation/services/crop_generator.py` already refreshes changed
  images by detecting annotation signatures. It needs a focused
  affected-image refresh path after a known annotation save, so the GUI does not
  wait for a broader stale scan and does not rebuild unaffected partition crops.
- `src/xray_curation/gui/crop_browser.py` owns the shared `CurationState`,
  crop table, Preview tab, pending panel, and Save Pending action. It should
  remain the integration shell, but image-level editing should live in a new
  annotation editor panel/service rather than expanding crop-browser methods
  indefinitely.
- `src/xray_curation/legacy/reviewProposals_gui.py` and `GUI_Dataset/`
  wrappers remain compatibility entry points only. The restored editor must be
  implemented in `src/xray_curation`, not by reintroducing legacy monolithic
  code.

## Project Structure

### Documentation (this feature)

```text
specs/002-annotation-editor/
├── plan.md
├── spec.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── annotation-editor.md
└── tasks.md              # created later by /speckit-tasks
```

### Source Code (repository root)

```text
src/xray_curation/
├── domain/
│   ├── annotations.py       # extend rectangle validation/coordinate helpers
│   └── operations.py        # pending change payload conventions if needed
├── services/
│   ├── annotation_store.py  # extend commit/stage behavior for annotation edits
│   ├── annotation_editor.py # new source-image/box editing service
│   ├── crop_generator.py    # affected-image crop refresh helper
│   ├── crop_manifest.py     # manifest updates after affected-image refresh
│   └── dataset_index.py     # selected-partition image lookup helpers
├── gui/
│   ├── annotation_editor.py # new Tkinter canvas editor panel
│   ├── crop_browser.py      # wire Preview tab, shared queue, save/refresh
│   ├── image_review.py      # refactor into preview host or reuse helpers
│   ├── operation_panels.py  # shared pending summary improvements
│   └── state.py             # selected image/box/editor state
└── legacy/
    └── ...                  # wrappers remain compatibility-only

tests/
├── unit/
│   ├── test_annotation_editor_service.py
│   ├── test_annotation_editor_geometry.py
│   ├── test_annotation_editor_pending.py
│   └── test_affected_crop_refresh.py
├── integration/
│   ├── test_annotation_editor_workflow.py
│   └── test_annotation_editor_pre_crop_browsing.py
└── fixtures/
    └── small_dataset/
```

**Structure Decision**: Add a narrow annotation-editor service and GUI panel to
the existing `src/xray_curation` package. Keep annotation/crop persistence in
services, keep all Tkinter canvas behavior in `gui/annotation_editor.py`, and
reuse the existing shared `CurationState.pending_changes` list rather than
introducing a second pending queue.

## Phase 0: Research Decisions

See [research.md](research.md). Key decisions:

- Restore the old GUI workflow through new services and a new canvas panel, not
  by copying the monolithic legacy script.
- Store and edit all box coordinates in source-image coordinates; use a
  deterministic canvas transform for display and hit testing.
- Use repeated-click cycling for overlapping boxes under the cursor.
- Extend the existing `PendingChange` model with annotation-edit operations and
  keep one shared queue and one Save Pending action.
- Automatically refresh only affected-image crops after a save when crop state
  exists; if crops have not been generated yet, save annotations and leave the
  image ready for later selected-partition generation.

## Phase 1: Design Decisions

See [data-model.md](data-model.md) and
[contracts/annotation-editor.md](contracts/annotation-editor.md).

- Add `SourceImageContext`, `EditableBoundingBox`, `CanvasTransform`,
  `AnnotationEdit`, `SharedPendingQueue`, and `AffectedImageRefresh` concepts.
- Add service operations for selected-partition image browsing, annotation
  loading, rectangle validation, hit testing, overlap cycling, staging
  add/move/resize/relabel/delete, shared commit, and affected-image refresh.
- Add an Annotation Editor panel in the Preview tab with modes for browse,
  draw, move/resize, relabel, delete, cancel, and save pending.
- Preserve unsupported shapes and unrelated JSON fields on every save.
- Keep crop records keyed by stable crop/bbox identity and rewrite affected
  image crop records after automatic refresh.

## Post-Design Constitution Check

- **Source data integrity**: PASS. The design stages all changes and commits
  JSON atomically while preserving unsupported/unrelated JSON content.
- **Core workflow parity**: PASS. The design covers all clarified legacy editor
  workflows, including drag-move/resize and source browsing before crops exist.
- **Stable identity**: PASS. Existing `curation_bbox_id` is preserved across
  coordinate edits; new boxes receive stable IDs before commit; crop records are
  refreshed from the updated annotation.
- **Derived artifact reproducibility**: PASS. Crops are regenerated only for
  affected source images and remain derived from annotation JSON.
- **Responsive partitioned GUI**: PASS. Source browsing uses selected
  partition manifests and save/refresh work is worker-backed.
- **Testable services**: PASS. Geometry, hit testing, staging, commit, and
  refresh are service-testable without Tkinter.
- **Controlled vocabulary**: PASS. Label selection uses approved PIDRay labels
  and preserves unknown existing labels for review.

Post-design gate status: PASS. No known violations.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |
