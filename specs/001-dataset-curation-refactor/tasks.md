# Tasks: Dataset Curation Refactor

**Input**: Design documents from `specs/001-dataset-curation-refactor/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/curation-operations.md, quickstart.md

**Tests**: Included because `plan.md` and `quickstart.md` define pytest unit/integration coverage for labels, partitions, crop identity, soft-delete, annotation preservation, and partition crop generation.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested as an independently useful increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on incomplete tasks in the same phase
- **[Story]**: Maps task to a user story from `spec.md`
- Every task includes an exact file path

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the Python package, test layout, and migration scaffolding without changing dataset files.

- [X] T001 Create Python package metadata and dependencies in `pyproject.toml`
- [X] T002 Create package entry files in `src/xray_curation/__init__.py` and `src/xray_curation/__main__.py`
- [X] T003 [P] Create package directory skeleton in `src/xray_curation/domain/.gitkeep`, `src/xray_curation/services/.gitkeep`, `src/xray_curation/gui/.gitkeep`, and `src/xray_curation/legacy/.gitkeep`
- [X] T004 [P] Create test directory skeleton in `tests/unit/.gitkeep`, `tests/integration/.gitkeep`, and `tests/fixtures/small_dataset/.gitkeep`
- [X] T005 [P] Add pytest configuration and test markers in `pyproject.toml`
- [X] T006 Create development notes for legacy-script migration in `docs/legacy-migration.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement shared domain objects, configuration, JSON safety, operation results, and fixture data needed by all stories.

**CRITICAL**: No user story work should begin until this phase is complete.

- [X] T007 Define dataset configuration loading and default paths in `src/xray_curation/config.py`
- [X] T008 [P] Define dataset, image, annotation, partition, crop, pending change, and operation result dataclasses in `src/xray_curation/domain/operations.py`
- [X] T009 [P] Define annotation shape and bounding-box domain helpers in `src/xray_curation/domain/annotations.py`
- [X] T010 [P] Define crop identity and crop status domain helpers in `src/xray_curation/domain/crops.py`
- [X] T011 [P] Define partition identity and partition status helpers in `src/xray_curation/domain/partitions.py`
- [X] T012 [P] Define approved PIDRay label constants and alias placeholders in `src/xray_curation/domain/labels.py`
- [X] T013 Implement atomic JSON load/save and error wrapping in `src/xray_curation/services/annotation_store.py`
- [X] T014 [P] Define stable bbox ID persistence rules and migration notes in `docs/bbox-identity.md`
- [X] T015 Implement bbox ID assignment, preservation, and lookup during annotation load/save in `src/xray_curation/services/annotation_store.py`
- [X] T016 [P] Add unit tests for bbox ID creation, preservation after relabel, and preservation after shape reorder in `tests/unit/test_bbox_identity.py`
- [X] T017 Implement operation result creation and summary serialization in `src/xray_curation/services/validation.py`
- [X] T018 Create a tiny fixture dataset with 6 images, 6 JSON files, and known labels in `tests/fixtures/small_dataset/`
- [X] T019 [P] Add unit tests for annotation JSON preservation and invalid shapes in `tests/unit/test_annotation_store.py`
- [X] T020 [P] Add unit tests for operation result summaries in `tests/unit/test_operation_results.py`
- [X] T021 [P] Add unit tests for domain identity helpers in `tests/unit/test_crop_identity.py`

**Checkpoint**: Foundation ready. User-story work can now begin.

---

## Phase 3: User Story 1 - Work on Dataset Partitions (Priority: P1) MVP

**Goal**: Reviewers can select a deterministic 10,000-image partition and generate crops only for that partition.

**Independent Test**: Open the app or CLI against the small fixture dataset, select a partition, generate crops, and verify only images assigned to that partition are processed.

### Tests for User Story 1

- [X] T022 [P] [US1] Add unit tests for deterministic partition assignment and final short partition in `tests/unit/test_partitions.py`
- [X] T023 [P] [US1] Add integration test for partition-only crop generation in `tests/integration/test_partition_crop_generation.py`
- [X] T024 [P] [US1] Add contract test for Select Partition and Generate Crops result shapes in `tests/integration/test_curation_contracts.py`
- [X] T025 [P] [US1] Add synthetic 10,000-image manifest test without real image files in `tests/integration/test_large_partition_manifest.py`

### Implementation for User Story 1

- [X] T026 [US1] Implement dataset indexing and stable image ordering in `src/xray_curation/services/dataset_index.py`
- [X] T027 [US1] Implement partition list creation and persistence in `src/xray_curation/services/dataset_index.py`
- [X] T028 [US1] Implement crop generation for a selected partition in `src/xray_curation/services/crop_generator.py`
- [X] T029 [US1] Implement partition crop manifest creation in `src/xray_curation/services/crop_manifest.py`
- [X] T030 [US1] Add `index` and `generate-crops` CLI commands in `src/xray_curation/cli.py`
- [X] T031 [US1] Create GUI app shell and partition selector in `src/xray_curation/gui/app.py`
- [X] T032 [US1] Implement GUI worker queue for crop generation progress in `src/xray_curation/gui/workers.py`
- [X] T033 [US1] Wire partition selection and crop generation actions into `src/xray_curation/gui/app.py`
- [X] T034 [US1] Add manual smoke-test notes for partition selection in `docs/gui-smoke-tests.md`

**Checkpoint**: US1 is independently functional as the MVP.

---

## Phase 4: User Story 2 - Browse and Correct Crops in the GUI (Priority: P1)

**Goal**: Reviewers can browse crops, open source image context, relabel/rename/move group, and soft-delete crops without losing the source bounding-box link.

**Independent Test**: Generate fixture crops, browse them in the GUI, open a crop's parent image, stage a relabel, stage a soft-delete, cancel one change, and save another change.

### Tests for User Story 2

- [X] T035 [P] [US2] Add unit tests for crop manifest lookups independent of filename and folder in `tests/unit/test_crop_manifest.py`
- [X] T036 [P] [US2] Add unit tests for pending relabel, rename, move group, soft-delete, restore, and commit behavior in `tests/unit/test_pending_changes.py`
- [X] T037 [P] [US2] Add integration test for crop browser service and source-context lookup in `tests/integration/test_crop_browser_workflow.py`

### Implementation for User Story 2

- [X] T038 [US2] Implement crop manifest read/query/update operations in `src/xray_curation/services/crop_manifest.py`
- [X] T039 [US2] Implement crop browsing filters by partition, class, source image, status, and text query in `src/xray_curation/services/crop_manifest.py`
- [X] T040 [US2] Implement source image and bounding-box context lookup from crop ID in `src/xray_curation/services/crop_manifest.py`
- [X] T041 [US2] Implement pending change staging and cancellation in `src/xray_curation/services/annotation_store.py`
- [X] T042 [US2] Implement commit of approved pending changes with atomic annotation writes in `src/xray_curation/services/annotation_store.py`
- [X] T043 [US2] Create GUI crop browser view in `src/xray_curation/gui/crop_browser.py`
- [X] T044 [US2] Create GUI image review view with selected bounding-box context in `src/xray_curation/gui/image_review.py`
- [X] T045 [US2] Create GUI application state container for active dataset, partition, selected crop, selected image, and pending changes in `src/xray_curation/gui/state.py`
- [X] T046 [US2] Wire crop relabel, rename, move group, soft-delete, restore, and save actions into `src/xray_curation/gui/crop_browser.py`
- [X] T047 [US2] Add pending change summary display in `src/xray_curation/gui/operation_panels.py`

**Checkpoint**: US2 is independently functional on generated fixture crops.

---

## Phase 5: User Story 3 - Run Curation Utilities Without Closing the GUI (Priority: P2)

**Goal**: Existing utility workflows run from inside the GUI with stale-edit protection and reviewable summaries; refresh controls are exposed here, while efficient refresh-changed behavior is completed in US5.

**Independent Test**: Stage an annotation change, run each utility from the GUI, and verify the GUI either prompts about unsaved edits or produces a preview/apply summary without closing.

### Tests for User Story 3

- [X] T048 [P] [US3] Add integration test for missing-crop detection preview and staged deletions in `tests/integration/test_missing_crops_workflow.py`
- [X] T049 [P] [US3] Add integration test for explicit external moved-crop import preview/apply in `tests/integration/test_external_moves_workflow.py`
- [X] T050 [P] [US3] Add unit tests for stale unsaved edit guards in `tests/unit/test_operation_guards.py`

### Implementation for User Story 3

- [X] T051 [US3] Implement missing-crop detection service using crop manifests in `src/xray_curation/services/validation.py`
- [X] T052 [US3] Implement external moved-crop import preview/apply service in `src/xray_curation/services/crop_manifest.py`
- [X] T053 [US3] Implement stale unsaved edit guard service in `src/xray_curation/services/validation.py`
- [X] T054 [US3] Add utility action panels for missing crops, external moves, refresh, and save workflows in `src/xray_curation/gui/operation_panels.py`
- [X] T055 [US3] Wire utility operation progress and summaries into `src/xray_curation/gui/workers.py`
- [X] T056 [US3] Convert `GUI_Dataset/missing_crops_detector.py` into a thin wrapper around `src/xray_curation/services/validation.py`
- [X] T057 [US3] Convert `GUI_Dataset/Moved_crops_json_updation_utility.py` into a thin wrapper around `src/xray_curation/services/crop_manifest.py`

**Checkpoint**: US3 utilities are available without closing the GUI.

---

## Phase 6: User Story 4 - Standardize Class Labels (Priority: P2)

**Goal**: Approved PIDRay labels are used consistently with spaces, and unknown or ambiguous legacy labels are reviewable before migration.

**Independent Test**: Run label standardization preview on fixture annotations and legacy crop folder names, verify unambiguous mappings are proposed, unknowns are flagged, and apply mode writes approved labels with spaces.

### Tests for User Story 4

- [X] T058 [P] [US4] Add unit tests for approved PIDRay labels and underscore alias normalization in `tests/unit/test_labels.py`
- [X] T059 [P] [US4] Add integration test for label standardization preview/apply workflow in `tests/integration/test_label_standardization.py`

### Implementation for User Story 4

- [X] T060 [US4] Fill approved PIDRay vocabulary and unambiguous legacy aliases in `src/xray_curation/domain/labels.py`
- [X] T061 [US4] Implement label normalization, alias resolution, and unknown-label reporting in `src/xray_curation/services/label_standardizer.py`
- [X] T062 [US4] Integrate approved label choices into GUI relabel controls in `src/xray_curation/gui/crop_browser.py`
- [X] T063 [US4] Add label standardization preview/apply panel in `src/xray_curation/gui/operation_panels.py`
- [X] T064 [US4] Convert `GUI_Dataset/Add_NewClass.py` into a thin launcher or wrapper for the refactored GUI in `GUI_Dataset/Add_NewClass.py`

**Checkpoint**: US4 label standardization is independently functional.

---

## Phase 7: User Story 5 - Resume Efficiently Across Sessions (Priority: P3)

**Goal**: Reviewers can resume partition work, detect stale crop state, and refresh only changed images.

**Independent Test**: Generate crops for a fixture partition, close/reopen the app, verify existing state is reused, edit one annotation, and refresh only that affected image.

### Tests for User Story 5

- [X] T065 [P] [US5] Add unit tests for partition state transitions and stale detection in `tests/unit/test_partition_state.py`
- [X] T066 [P] [US5] Add integration test for resume and refresh-changed workflow in `tests/integration/test_resume_refresh_workflow.py`
- [X] T067 [P] [US5] Add unit tests for append-only operation log serialization in `tests/unit/test_operation_log.py`

### Implementation for User Story 5

- [X] T068 [US5] Implement partition state loading, ready/stale/error transitions, and summaries in `src/xray_curation/services/dataset_index.py`
- [X] T069 [US5] Implement annotation change detection for crop refresh in `src/xray_curation/services/crop_generator.py`
- [X] T070 [US5] Implement refresh-changed mode for selected partition crops in `src/xray_curation/services/crop_generator.py`
- [X] T071 [US5] Implement append-only operation log writes in `src/xray_curation/services/validation.py`
- [X] T072 [US5] Add GUI resume, refresh changed, and rebuild actions in `src/xray_curation/gui/app.py`
- [X] T073 [US5] Convert `GUI_Dataset/reviewProposals_gui.py` into a thin launcher for `src/xray_curation/gui/app.py`

**Checkpoint**: US5 resume workflow is independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation, cleanup, and safety checks across all implemented stories.

- [X] T074 [P] Update quickstart implementation commands and expected outputs in `specs/001-dataset-curation-refactor/quickstart.md`
- [X] T075 [P] Update architecture notes and migration status in `docs/legacy-migration.md`
- [X] T076 [P] Add a dataset `.gitignore` policy for generated curation artifacts in `.gitignore`
- [X] T077 Run unit test command and record results in `specs/001-dataset-curation-refactor/test-results.md`
- [X] T078 Run integration test command and record results in `specs/001-dataset-curation-refactor/test-results.md`
- [X] T079 Run manual GUI smoke checklist and record results in `docs/gui-smoke-tests.md`
- [X] T080 Review `specs/001-dataset-curation-refactor/checklists/refactor-readiness.md` and resolve or document any unchecked requirement-quality items before release
- [X] T081 Remove duplicated helper logic from legacy wrappers after service migration in `GUI_Dataset/reviewProposals_gui.py`, `GUI_Dataset/Add_NewClass.py`, `GUI_Dataset/missing_crops_detector.py`, and `GUI_Dataset/Moved_crops_json_updation_utility.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: No dependencies.
- **Phase 2 Foundational**: Depends on Phase 1; blocks all user stories.
- **Phase 3 US1**: Depends on Phase 2; MVP.
- **Phase 4 US2**: Depends on Phase 2 and benefits from US1 crop generation, but crop browser services can be developed against fixture manifests.
- **Phase 5 US3**: Depends on Phase 2; integrates most cleanly after US2 pending-change services.
- **Phase 6 US4**: Depends on Phase 2; can run in parallel with US3 after label constants exist.
- **Phase 7 US5**: Depends on US1 partition/crop generation and benefits from US2 manifest services.
- **Phase 8 Polish**: Depends on whichever stories are included in the release.

### User Story Dependencies

- **US1 Work on Dataset Partitions**: First MVP; no dependency on other stories after foundation.
- **US2 Browse and Correct Crops**: Uses crop manifests from US1 but can be developed with fixture manifests.
- **US3 Run Curation Utilities**: Uses pending changes and summaries from US2.
- **US4 Standardize Class Labels**: Uses foundational label constants; can proceed alongside US3.
- **US5 Resume Efficiently Across Sessions**: Uses partition generation from US1 and manifest state from US2.

### Within Each User Story

- Tests first, then models/services, then GUI/legacy wrappers.
- Service layer tasks precede GUI wiring tasks.
- GUI tasks that touch different files can run in parallel once shared services exist.
- Legacy wrapper conversion happens after the corresponding service exists.

---

## Parallel Opportunities

- Setup directory and fixture tasks T003-T006 can run in parallel after T001-T002.
- Foundational domain helpers T008-T012, bbox identity docs T014, and tests T016, T019-T021 can run in parallel once package skeleton exists.
- US1 test tasks T022-T025 can run in parallel.
- US2 test tasks T035-T037 can run in parallel, and GUI files T043-T047 can split after services T038-T042.
- US3 utility tests T048-T050 can run in parallel.
- US4 label tests T058-T059 can run in parallel.
- US5 resume tests T065-T067 can run in parallel.
- Polish docs T074-T076 can run in parallel.

## Parallel Example: User Story 1

```text
Task: "T022 [P] [US1] Add unit tests for deterministic partition assignment and final short partition in tests/unit/test_partitions.py"
Task: "T023 [P] [US1] Add integration test for partition-only crop generation in tests/integration/test_partition_crop_generation.py"
Task: "T024 [P] [US1] Add contract test for Select Partition and Generate Crops result shapes in tests/integration/test_curation_contracts.py"
Task: "T025 [P] [US1] Add synthetic 10,000-image manifest test without real image files in tests/integration/test_large_partition_manifest.py"
```

## Parallel Example: User Story 2

```text
Task: "T043 [US2] Create GUI crop browser view in src/xray_curation/gui/crop_browser.py"
Task: "T044 [US2] Create GUI image review view with selected bounding-box context in src/xray_curation/gui/image_review.py"
Task: "T045 [US2] Create GUI application state container for active dataset, partition, selected crop, selected image, and pending changes in src/xray_curation/gui/state.py"
```

## Parallel Example: User Story 4

```text
Task: "T058 [P] [US4] Add unit tests for approved PIDRay labels and underscore alias normalization in tests/unit/test_labels.py"
Task: "T059 [P] [US4] Add integration test for label standardization preview/apply workflow in tests/integration/test_label_standardization.py"
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1 setup.
2. Complete Phase 2 foundation.
3. Complete Phase 3 US1.
4. Validate partition selection and partition-only crop generation on `tests/fixtures/small_dataset/`.
5. Demo the GUI selecting one partition and generating only that partition's crops.

### Incremental Delivery

1. US1: partitioned crop generation.
2. US2: crop browsing and safe correction workflow.
3. US3: integrated utilities.
4. US4: label standardization.
5. US5: resume and refresh efficiency.

### Migration Strategy

1. Build and test services under `src/xray_curation/`.
2. Route new GUI flows through services.
3. Convert legacy scripts under `GUI_Dataset/` to thin wrappers.
4. Remove duplicated path, JSON, label, and crop helper logic from legacy scripts.
5. Keep dataset files under `batch_1/images` and `batch_1/json` unchanged; write generated state under `batch_1/curation`.

---

## Notes

- `[P]` tasks touch separate files or can be implemented independently after their phase prerequisites.
- `[US#]` labels map directly to user stories in `spec.md`.
- Tests are intentionally focused on service behavior and small fixtures to avoid scanning the 56,176-image dataset during development.
- Do not run full-dataset crop generation as part of task validation; use fixtures and selected partitions.
