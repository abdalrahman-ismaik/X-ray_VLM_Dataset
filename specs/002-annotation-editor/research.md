# Research: Annotation Editor Restoration

## Decision: Restore Workflow Through New Services And A Canvas Panel

**Rationale**: The legacy GUI contains the missing annotation-editor behavior, but copying the monolithic script back into the refactored app would reintroduce hard-coded paths, duplicated JSON logic, and GUI-owned persistence. The new implementation should add a narrow `annotation_editor` service for source-image context, geometry, hit testing, staging, commit, and refresh support, plus a Tkinter canvas panel that calls those services.

**Alternatives considered**:

- Copy the old editor code directly: rejected because it would bypass the service layer and recreate the organization problems this refactor is solving.
- Keep annotation editing as a separate legacy script: rejected because reviewers would still need to close the GUI and lose the unified pending workflow.

## Decision: Source Images Are Browsed From Selected Partition Manifests

**Rationale**: Annotation Editor mode must work before crops exist. The selected partition manifest already defines the bounded working set, so the GUI can browse only those images and load each image annotation on demand. This satisfies the no full-dataset scan rule while allowing image-level review before crop generation.

**Alternatives considered**:

- Require a crop manifest before editing: rejected because missing-box annotation often happens before crops are generated.
- Scan the dataset root each time the editor opens: rejected because it risks UI lag and violates the selected-partition workflow.

## Decision: Store Geometry In Source-Image Coordinates

**Rationale**: Annotation JSON uses source-image coordinates, while the GUI canvas may scale the image. The editor should keep all persisted box points in image coordinates and use a deterministic `CanvasTransform` for display, hit testing, drawing, moving, and resizing. This avoids rounding drift and keeps saved boxes independent from window size.

**Alternatives considered**:

- Store edited display coordinates and convert only on save: rejected because zoom, resizing, and repeated edits would accumulate avoidable precision errors.
- Draw directly onto a Pillow preview image: rejected because it cannot support interactive selection, handles, drag movement, or resize behavior cleanly.

## Decision: Editable Shapes Are Rectangular Boxes Only

**Rationale**: The restored legacy workflow is specifically about rectangular bounding boxes. Unsupported shapes must remain visible in summaries where useful, but they are not editable in this feature. Saves must preserve unsupported shapes and unrelated JSON fields exactly unless the reviewer staged a supported-box change.

**Alternatives considered**:

- Add polygon and arbitrary shape editing: rejected as out of scope and risky for dataset integrity.
- Drop unsupported shapes during save: rejected because it violates source data integrity and could destroy annotation information.

## Decision: Overlapping Boxes Use Repeated-Click Cycling

**Rationale**: X-ray objects can overlap. A single click point may hit multiple boxes, so the service should return all candidate boxes in deterministic annotation order and cycle through them when the same canvas point is clicked repeatedly. The active box must be visually distinct in the GUI.

**Alternatives considered**:

- Always choose the smallest box: rejected because it can make larger overlapping boxes hard to select.
- Always choose the first shape in JSON order: rejected because the reviewer cannot reach the other boxes under the same point.

## Decision: Annotation Edits Use The Existing Shared Pending Queue

**Rationale**: The refactored GUI already has a pending queue for crop corrections. Annotation edits should be represented as pending operations in the same queue so the reviewer has one place to review, cancel, and save work. New operation names should cover `annotation_add`, `annotation_update_box`, `annotation_relabel`, and `annotation_delete`.

**Alternatives considered**:

- Add a second annotation-only save queue: rejected because it splits reviewer attention and makes mixed crop and annotation edits harder to audit.
- Write annotation edits immediately after a drag or label change: rejected because it removes the reviewable save workflow and increases accidental edit risk.

## Decision: Atomic JSON Commit Preserves Existing Content

**Rationale**: Annotation JSON is the source of truth for labels and boxes. Commits must load the current file, apply only staged supported-box edits, preserve unrelated fields and unsupported shapes, assign or preserve stable bbox IDs, and save through the existing atomic JSON writer.

**Alternatives considered**:

- Rewrite the file from an in-memory simplified model: rejected because it could drop unsupported fields, metadata, or unknown shapes.
- Update crop manifests without saving annotations: rejected because crops are derived artifacts and must not become the source of truth.

## Decision: Refresh Only Affected Image Crops After Save

**Rationale**: When annotation edits are saved for one image, only crops derived from that image need refresh. The service should run a focused affected-image refresh when a crop manifest already exists for the selected partition. If crops do not exist yet, the save succeeds and later selected-partition crop generation will include the new annotation state.

**Alternatives considered**:

- Rebuild the full partition after every edit: rejected because it is slower than necessary and can make the GUI feel blocked.
- Rebuild all dataset crops after every edit: rejected because it violates the explicit full-dataset constraint.

## Decision: Keep Tkinter Responsive With Worker-Backed Save And Refresh

**Rationale**: Canvas interaction must stay on the Tkinter main thread, but disk writes and crop refresh can take enough time to show progress. The GUI should use the existing worker pattern for save/refresh operations, update a status/progress indicator, and disable conflicting controls while work is active.

**Alternatives considered**:

- Do all save and refresh work synchronously in button handlers: rejected because it can freeze the app and repeat the lag the reviewer reported.
- Move canvas drawing to a background thread: rejected because Tkinter widget updates must stay on the main thread.

## Decision: Test With Fixtures, Synthetic Manifests, And Selected Partitions Only

**Rationale**: The feature is primarily service logic plus GUI wiring. Unit tests can cover geometry, hit testing, staging, and commit behavior. Integration tests can use `tests/fixtures/small_dataset` and synthetic partition/crop manifests. No test should scan `dataset`, `batch_1`, or generate crops for the full production dataset.

**Alternatives considered**:

- Use production data for confidence: rejected because it is slow, not reproducible, and violates the implementation constraint.
- Rely on manual GUI testing only: rejected because stable identity and JSON preservation need automated regression coverage.

## Resolved Unknowns

No open clarification markers remain in `spec.md`. The clarified decisions are included in this research output and reflected in the design artifacts.
