# Tasks: Annotation Editor Restoration

**Input**: Design documents from `specs/002-annotation-editor/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/annotation-editor.md, quickstart.md, checklists/requirements.md

**Tests**: Included because `spec.md`, `plan.md`, and `quickstart.md` require pytest unit and integration coverage for annotation-editor geometry, source-image browsing, overlap selection, pending edits, atomic saves, stable identity, affected-image refresh, and fixture-only validation.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested as an independently useful increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on incomplete tasks in the same phase.
- **[Story]**: Maps task to a user story from `spec.md`.
- Every task includes an exact file path.

## Constitution-Driven Guardrails

- Do not scan the full dataset during implementation or tests.
- Do not generate crops for all 56,176 images.
- Use `tests/fixtures/small_dataset`, synthetic manifests, and selected-partition state only.
- Preserve original image files.
- Keep annotation JSON as the source of truth and crops as derived artifacts.
- Restore the legacy workflows inside the refactored `src/xray_curation` architecture, not by reviving the old monolithic GUI as the main implementation.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the new module and test-file scaffolding without changing production dataset files.

- [X] T001 Create annotation editor service module skeleton in `src/xray_curation/services/annotation_editor.py`
- [X] T002 Create annotation editor GUI panel module skeleton in `src/xray_curation/gui/annotation_editor.py`
- [X] T003 [P] Create geometry unit test file in `tests/unit/test_annotation_editor_geometry.py`
- [X] T004 [P] Create service unit test file in `tests/unit/test_annotation_editor_service.py`
- [X] T005 [P] Create pending-change unit test file in `tests/unit/test_annotation_editor_pending.py`
- [X] T006 [P] Create affected-refresh unit test file in `tests/unit/test_affected_crop_refresh.py`
- [X] T007 [P] Create pre-crop browsing integration test file in `tests/integration/test_annotation_editor_pre_crop_browsing.py`
- [X] T008 [P] Create full workflow integration test file in `tests/integration/test_annotation_editor_workflow.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement shared geometry, source-image context, pending operation conventions, fixtures, and selected-partition helpers needed by all annotation-editor stories.

**CRITICAL**: No user story work should begin until this phase is complete.

- [X] T009 Extend rectangle normalization, validation, clamping, and minimum-size helpers in `src/xray_curation/domain/annotations.py`
- [X] T010 [P] Define `SourceImageContext`, `EditableBoundingBox`, `CanvasTransform`, and annotation edit helper dataclasses in `src/xray_curation/services/annotation_editor.py`
- [X] T011 [P] Define annotation edit operation constants and payload conventions in `src/xray_curation/domain/operations.py`
- [X] T012 [P] Extend GUI curation state for active source image, selected bbox, editor mode, and worker progress in `src/xray_curation/gui/state.py`
- [X] T013 Implement selected-partition image lookup without crop-manifest dependency in `src/xray_curation/services/dataset_index.py`
- [X] T014 Implement annotation edit conflict detection and shared pending summary grouping in `src/xray_curation/services/validation.py`
- [X] T015 [P] Add dedicated annotation-editor fixture JSON cases for overlapping boxes, unknown labels, and unsupported shapes in `tests/fixtures/annotation_editor_cases/overlap_unknown_unsupported.json`
- [X] T016 [P] Document dedicated annotation-editor fixture cases and how tests copy them into temporary datasets in `tests/fixtures/annotation_editor_cases/README.md`
- [X] T017 [P] Add shared fixture copy helpers for mutation-safe annotation tests in `tests/conftest.py`
- [X] T018 Add regression notes for avoiding full-dataset scans in `docs/gui-smoke-tests.md`

**Checkpoint**: Geometry, selected-partition source lookup, shared pending conventions, and fixtures are ready.

---

## Phase 3: User Story 1 - Inspect and Select Image Boxes (Priority: P1) MVP

**Goal**: Reviewers can browse source images from a selected partition before crops exist, see all supported rectangular boxes, select boxes directly on the image, and cycle through overlapping boxes.

**Independent Test**: Open the GUI or service tests against `tests/fixtures/small_dataset`, select `part-0001`, browse a source image before crop generation, verify all supported boxes are present, select a box by image coordinate, and cycle through overlapping boxes without scanning the production dataset.

### Tests for User Story 1

- [X] T019 [P] [US1] Add CanvasTransform fit, round-trip conversion, and image-bound clamping tests in `tests/unit/test_annotation_editor_geometry.py`
- [X] T020 [P] [US1] Add source-image listing tests that require only selected partition manifests in `tests/unit/test_annotation_editor_service.py`
- [X] T021 [P] [US1] Add source context loading tests for supported rectangles, unsupported shapes, unknown labels, and stable bbox IDs in `tests/unit/test_annotation_editor_service.py`
- [X] T022 [P] [US1] Add hit-test and repeated-click overlap cycling tests in `tests/unit/test_annotation_editor_geometry.py`
- [X] T023 [P] [US1] Add pre-crop partition browsing integration test in `tests/integration/test_annotation_editor_pre_crop_browsing.py`
- [X] T024 [P] [US1] Add crop-context source image selection integration test in `tests/integration/test_annotation_editor_workflow.py`

### Implementation for User Story 1

- [X] T025 [US1] Implement CanvasTransform image-to-canvas and canvas-to-image conversion in `src/xray_curation/services/annotation_editor.py`
- [X] T026 [US1] Implement `list_partition_source_images` service using selected partition manifests in `src/xray_curation/services/annotation_editor.py`
- [X] T027 [US1] Implement `load_source_image_context` with supported rectangle extraction and unsupported-shape warnings in `src/xray_curation/services/annotation_editor.py`
- [X] T028 [US1] Implement deterministic `hit_test_boxes` and repeated-click cycling in `src/xray_curation/services/annotation_editor.py`
- [X] T029 [US1] Implement source-image canvas rendering with all boxes and selected-box styling in `src/xray_curation/gui/annotation_editor.py`
- [X] T030 [US1] Implement selected-box details display for image ID, bbox ID, label, and pending status in `src/xray_curation/gui/annotation_editor.py`
- [X] T031 [US1] Wire Annotation Editor panel into the Preview tab in `src/xray_curation/gui/crop_browser.py`
- [X] T032 [US1] Wire crop-selection context to select the matching source bbox in `src/xray_curation/gui/crop_browser.py`
- [X] T033 [US1] Add source-image previous/next browsing controls before crops exist in `src/xray_curation/gui/annotation_editor.py`
- [X] T034 [US1] Surface missing image, missing JSON, unsupported shape, and unknown label status messages in `src/xray_curation/gui/annotation_editor.py`

**Checkpoint**: US1 is independently functional as the MVP for image inspection and selection.

---

## Phase 4: User Story 2 - Draw and Label New Boxes (Priority: P1)

**Goal**: Reviewers can draw a new rectangular box on the source image, assign an approved PIDRay label, stage it, save it atomically, and preserve the original image file.

**Independent Test**: Use a copied fixture dataset, draw a rectangle in any direction, choose an approved label, stage and save the new box, verify the annotation JSON has a stable bbox ID, and verify the source image bytes are unchanged.

### Tests for User Story 2

- [X] T035 [P] [US2] Add drawn rectangle normalization tests for all drag directions in `tests/unit/test_annotation_editor_geometry.py`
- [X] T036 [P] [US2] Add invalid new-box validation tests for tiny, zero-area, and out-of-bounds rectangles in `tests/unit/test_annotation_editor_geometry.py`
- [X] T037 [P] [US2] Add approved PIDRay label validation tests for new annotation boxes in `tests/unit/test_annotation_editor_pending.py`
- [X] T038 [P] [US2] Add `annotation_add` staging tests proving JSON is unchanged before save in `tests/unit/test_annotation_editor_pending.py`
- [X] T039 [P] [US2] Add atomic save and stable bbox ID tests for newly added boxes in `tests/unit/test_annotation_editor_service.py`
- [X] T040 [P] [US2] Add draw-label-save integration test with original image immutability assertion in `tests/integration/test_annotation_editor_workflow.py`

### Implementation for User Story 2

- [X] T041 [US2] Implement draw mode state, drag start, drag update, and drag preview in `src/xray_curation/gui/annotation_editor.py`
- [X] T042 [US2] Implement approved PIDRay label selector for new boxes in `src/xray_curation/gui/annotation_editor.py`
- [X] T043 [US2] Implement new-box validation and label validation service helpers in `src/xray_curation/services/annotation_editor.py`
- [X] T044 [US2] Implement `stage_annotation_add` pending-change creation in `src/xray_curation/services/annotation_editor.py`
- [X] T045 [US2] Extend pending list rendering for `annotation_add` summaries in `src/xray_curation/gui/operation_panels.py`
- [X] T046 [US2] Extend annotation JSON commit logic for `annotation_add` with stable bbox ID assignment in `src/xray_curation/services/annotation_store.py`
- [X] T047 [US2] Wire shared Save Pending for new annotation boxes in `src/xray_curation/gui/crop_browser.py`
- [X] T048 [US2] Reload the active source image after saving a new box in `src/xray_curation/gui/annotation_editor.py`

**Checkpoint**: US2 is independently functional for adding missing annotations.

---

## Phase 5: User Story 3 - Edit, Delete, Save, and Refresh Affected Crops (Priority: P1)

**Goal**: Reviewers can move, resize, relabel, delete, cancel, and save existing boxes through the shared pending queue, with automatic refresh of only affected image crops when crop state exists.

**Independent Test**: Use fixture crops, select an existing box, drag-move or drag-resize it, stage a relabel, stage and cancel a deletion, save one edit, and verify only the affected image crops refresh while bbox and crop identity remain stable.

### Tests for User Story 3

- [X] T049 [P] [US3] Add drag-move and drag-resize coordinate staging tests in `tests/unit/test_annotation_editor_geometry.py`
- [X] T050 [P] [US3] Add annotation relabel, coordinate update, delete, and cancel pending tests in `tests/unit/test_annotation_editor_pending.py`
- [X] T051 [P] [US3] Add conflicting same-bbox pending edit tests in `tests/unit/test_annotation_editor_pending.py`
- [X] T052 [P] [US3] Add atomic commit tests preserving unsupported shapes and unrelated JSON fields in `tests/unit/test_annotation_editor_service.py`
- [X] T053 [P] [US3] Add stable bbox identity preservation tests for move, resize, relabel, and delete in `tests/unit/test_annotation_editor_service.py`
- [X] T054 [P] [US3] Add affected-image-only crop refresh tests with synthetic selected-partition manifests in `tests/unit/test_affected_crop_refresh.py`
- [X] T055 [P] [US3] Add refresh-skipped-when-no-crop-manifest test in `tests/unit/test_affected_crop_refresh.py`
- [X] T056 [P] [US3] Add mixed crop correction and annotation edit integration test in `tests/integration/test_annotation_editor_workflow.py`
- [X] T057 [P] [US3] Add move-resize-relabel-delete-save-refresh integration test in `tests/integration/test_annotation_editor_workflow.py`

### Implementation for User Story 3

- [X] T058 [US3] Implement `stage_annotation_update_box`, `stage_annotation_relabel`, and `stage_annotation_delete` in `src/xray_curation/services/annotation_editor.py`
- [X] T059 [US3] Implement body-drag move behavior for selected boxes in `src/xray_curation/gui/annotation_editor.py`
- [X] T060 [US3] Implement resize handles and drag-resize behavior for selected boxes in `src/xray_curation/gui/annotation_editor.py`
- [X] T061 [US3] Implement selected-box relabel control using approved PIDRay labels in `src/xray_curation/gui/annotation_editor.py`
- [X] T062 [US3] Implement selected-box pending delete and restore/cancel interactions in `src/xray_curation/gui/annotation_editor.py`
- [X] T063 [US3] Extend pending list rendering for coordinate edit, relabel, and delete summaries in `src/xray_curation/gui/operation_panels.py`
- [X] T064 [US3] Extend annotation JSON commit logic for update, relabel, and delete operations in `src/xray_curation/services/annotation_store.py`
- [X] T065 [US3] Implement shared pending commit orchestration for crop corrections and annotation edits in `src/xray_curation/services/annotation_store.py`
- [X] T066 [US3] Implement affected-image crop refresh helper that accepts explicit image IDs in `src/xray_curation/services/crop_generator.py`
- [X] T067 [US3] Update crop manifest records after affected-image refresh in `src/xray_curation/services/crop_manifest.py`
- [X] T068 [US3] Wire Save Pending worker progress and error callbacks for annotation saves and affected refresh in `src/xray_curation/gui/workers.py`
- [X] T069 [US3] Wire shared Save Pending to commit annotation edits, refresh affected crops, and preserve pending changes on failure in `src/xray_curation/gui/crop_browser.py`
- [X] T070 [US3] Reload crop browser rows and active source context after affected-image refresh in `src/xray_curation/gui/crop_browser.py`
- [X] T071 [US3] Add operation result counts for added, coordinate-edited, relabeled, deleted, cancelled, refreshed, and skipped items in `src/xray_curation/services/validation.py`

**Checkpoint**: US3 is independently functional for safe editing, save, and affected crop refresh.

---

## Phase 6: User Story 4 - Guide Reviewers Through Annotation Editor Mode (Priority: P2)

**Goal**: Reviewers have clear in-app and README guidance for when to browse crops, when to edit source annotations, how pending changes work, and how affected refresh behaves.

**Independent Test**: Open the GUI against the fixture dataset and confirm the Workflow or Preview guidance explains partition selection, source-image browsing, box selection, drawing, label assignment, staging, saving, and affected crop refresh without needing outside instructions.

### Tests for User Story 4

- [X] T072 [P] [US4] Add guidance text coverage tests for required workflow concepts in `tests/unit/test_annotation_editor_guidance.py`
- [X] T073 [P] [US4] Add README workflow coverage test for Annotation Editor instructions in `tests/unit/test_annotation_editor_guidance.py`
- [X] T074 [P] [US4] Add GUI empty-state guidance integration test in `tests/integration/test_annotation_editor_pre_crop_browsing.py`

### Implementation for User Story 4

- [X] T075 [US4] Add Annotation Editor workflow guidance content constants in `src/xray_curation/gui/annotation_editor.py`
- [X] T076 [US4] Add actionable empty-state and no-selection guidance in `src/xray_curation/gui/annotation_editor.py`
- [X] T077 [US4] Add workflow guide text for annotation editing to the GUI shell in `src/xray_curation/gui/app.py`
- [X] T078 [US4] Update README usage instructions for Annotation Editor mode in `README.md`
- [X] T079 [US4] Update manual GUI smoke-test steps for drawing, selecting, editing, deleting, saving, and refresh in `docs/gui-smoke-tests.md`
- [X] T080 [US4] Run the manual GUI smoke test for Annotation Editor canvas interactions on fixture data and record the result in `docs/gui-smoke-tests.md`
- [X] T081 [US4] Review checklist and specification consistency for drag/resize scope in `specs/002-annotation-editor/checklists/requirements.md`

**Checkpoint**: US4 guidance is complete and testable independently.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, cleanup, and documentation consistency across all stories.

- [X] T082 [P] Run focused annotation editor unit tests and record results in `specs/002-annotation-editor/quickstart.md`
- [X] T083 [P] Run focused annotation editor integration tests and record results in `specs/002-annotation-editor/quickstart.md`
- [X] T084 Run `python -m compileall -q src GUI_Dataset run_gui.py` and record result in `specs/002-annotation-editor/quickstart.md`
- [X] T085 [P] Review legacy wrapper compatibility notes in `src/xray_curation/legacy/reviewProposals_gui.py`
- [X] T086 [P] Review GUI module import boundaries to keep persistence out of Tkinter code in `src/xray_curation/gui/annotation_editor.py`
- [X] T087 [P] Review service module import boundaries to keep GUI dependencies out of services in `src/xray_curation/services/annotation_editor.py`
- [X] T088 Run final cross-artifact consistency review and record implementation caveats in `specs/002-annotation-editor/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: No dependencies.
- **Phase 2 Foundational**: Depends on Phase 1. Blocks all user stories.
- **Phase 3 US1**: Depends on Phase 2. MVP for source-image inspection and selection.
- **Phase 4 US2**: Depends on Phase 2 and can reuse US1 canvas/context work.
- **Phase 5 US3**: Depends on Phase 2 and should integrate with US1 and US2 for the full editor workflow.
- **Phase 6 US4**: Depends on the UI surfaces from US1 through US3.
- **Phase 7 Polish**: Depends on the stories selected for implementation.

### User Story Dependencies

- **US1 (P1)**: First MVP story; enables source-image browsing and selection.
- **US2 (P1)**: Can begin after foundational tasks, but GUI draw/save wiring is simpler after US1 canvas exists.
- **US3 (P1)**: Builds on US1 selection and US2 pending-save paths for full edit/delete/save/refresh.
- **US4 (P2)**: Documents and guides the completed editor behavior.

### Parallel Opportunities

- Setup scaffolding tasks T003 through T008 can run in parallel.
- Foundational fixture and state tasks T010 through T017 can run in parallel when they do not touch the same file.
- US1 test tasks T019 through T024 can run in parallel before implementation.
- US2 test tasks T035 through T040 can run in parallel before implementation.
- US3 test tasks T049 through T057 can run in parallel before implementation.
- US4 test tasks T072 through T074 can run in parallel.
- Service tasks and GUI tasks can often be split between workers if they avoid editing the same files simultaneously.

---

## Parallel Example: User Story 1

```text
Task: "T019 [US1] Add CanvasTransform fit, round-trip conversion, and image-bound clamping tests in tests/unit/test_annotation_editor_geometry.py"
Task: "T020 [US1] Add source-image listing tests that require only selected partition manifests in tests/unit/test_annotation_editor_service.py"
Task: "T023 [US1] Add pre-crop partition browsing integration test in tests/integration/test_annotation_editor_pre_crop_browsing.py"
```

## Parallel Example: User Story 2

```text
Task: "T035 [US2] Add drawn rectangle normalization tests for all drag directions in tests/unit/test_annotation_editor_geometry.py"
Task: "T037 [US2] Add approved PIDRay label validation tests for new annotation boxes in tests/unit/test_annotation_editor_pending.py"
Task: "T040 [US2] Add draw-label-save integration test with original image immutability assertion in tests/integration/test_annotation_editor_workflow.py"
```

## Parallel Example: User Story 3

```text
Task: "T050 [US3] Add annotation relabel, coordinate update, delete, and cancel pending tests in tests/unit/test_annotation_editor_pending.py"
Task: "T054 [US3] Add affected-image-only crop refresh tests with synthetic selected-partition manifests in tests/unit/test_affected_crop_refresh.py"
Task: "T057 [US3] Add move-resize-relabel-delete-save-refresh integration test in tests/integration/test_annotation_editor_workflow.py"
```

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 Setup.
2. Complete Phase 2 Foundational.
3. Complete Phase 3 US1.
4. Stop and validate source-image browsing, all-box display, direct selection, and overlap cycling on fixtures.

### Full P1 Restoration

1. Add Phase 4 US2 for drawing and labeling new boxes.
2. Add Phase 5 US3 for move, resize, relabel, delete, atomic save, and affected-image refresh.
3. Validate with focused pytest commands from `specs/002-annotation-editor/quickstart.md`.

### Guidance And Polish

1. Add Phase 6 US4 guidance once the UI flow is stable.
2. Complete Phase 7 validation and cleanup.
3. Preserve legacy wrappers as compatibility entry points only.

## Notes

- Tests should use copied fixtures or temporary directories for mutation tests.
- Any crop generation in this feature must target fixture data or explicit selected-partition image IDs only.
- Do not add tasks that require indexing or processing the full production dataset.
- Avoid moving implementation back into `src/xray_curation/legacy/` or `GUI_Dataset/`.
