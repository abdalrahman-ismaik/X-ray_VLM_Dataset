# Feature Specification: Dataset Curation Refactor

**Feature Branch**: `001-dataset-curation-refactor`
**Created**: 2026-05-06
**Status**: Draft
**Input**: User description: "Refactor the VLM image dataset cleaning GUI and utility scripts so crop generation is partitioned, crops can be browsed inside the GUI, utility workflows can run without closing the GUI, crop regeneration is efficient, and class labels are standardized to the PIDRay class format."

## Clarifications

### Session 2026-05-06

- Q: What should be the primary workflow for crop-based corrections? -> A: GUI is primary; external moved crop folders are supported only through an explicit import/apply action.
- Q: How should crop identity be tracked as crops are renamed, relabeled, deleted, or moved? -> A: Each crop has a stable manifest identity independent of class folder and crop filename.
- Q: What should deleting a crop mean? -> A: Soft-delete first; remove the bounding box only after reviewer confirms or saves.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Work on Dataset Partitions (Priority: P1)

As a VLM dataset reviewer, I want to choose a 10,000-image partition before generating crops so that each review session is small enough to process, inspect, and recover from independently.

**Why this priority**: The current all-at-once crop generation over 56,176 images is too heavy and blocks practical review of the dataset.

**Independent Test**: Can be tested by opening the curation app, selecting a partition, generating crops only for that partition, and verifying that no crops outside the selected partition are created or modified.

**Acceptance Scenarios**:

1. **Given** a dataset containing 56,176 image/annotation pairs, **When** the reviewer starts crop generation, **Then** the app presents deterministic partition choices of 10,000 images each, with the final partition containing the remaining images.
2. **Given** the reviewer selects partition 3, **When** crop generation runs, **Then** only images assigned to partition 3 are processed and the resulting crops are associated with partition 3.
3. **Given** a partition already has generated crops, **When** the reviewer opens the app again, **Then** the app shows that partition's crop status and does not require deleting existing crops before continuing.

---

### User Story 2 - Browse and Correct Crops in the GUI (Priority: P1)

As a dataset reviewer, I want to browse crop thumbnails and their parent images inside the same GUI so that I can quickly find wrong labels, inspect context, and correct annotations without switching between folders and scripts.

**Why this priority**: The current GUI shows one full image at a time, while many label-correction decisions are driven by object crops.

**Independent Test**: Can be tested by selecting a partition and class, browsing a crop list or grid, opening a crop, viewing its parent image and bounding box, and applying a label correction from the same interface.

**Acceptance Scenarios**:

1. **Given** crops exist for a selected partition, **When** the reviewer opens the crop browser, **Then** the GUI displays browsable crops with class, source image, and annotation identity visible.
2. **Given** a crop is selected, **When** the reviewer requests context, **Then** the GUI opens the parent image with the corresponding bounding box selected.
3. **Given** a crop has the wrong class, **When** the reviewer changes its class in the GUI, **Then** the underlying annotation is updated and the crop view reflects the new class without closing the app.
4. **Given** a crop is renamed, relabeled, deleted, or moved between class groups, **When** the reviewer saves the change, **Then** the crop remains linked to the intended source image and bounding box through stable identity rather than folder or filename alone.
5. **Given** a reviewer deletes a crop, **When** the deletion is first requested, **Then** the crop and bounding box are marked as pending deletion and the bounding box is removed only after the reviewer confirms or saves.

---

### User Story 3 - Run Curation Utilities Without Closing the GUI (Priority: P2)

As a dataset reviewer, I want the existing utility workflows to be available from the GUI so that saving changes, detecting missing crops, updating annotations from moved crops, and refreshing views can happen in one session.

**Why this priority**: Closing the GUI to run helper scripts breaks the review flow and makes it easier to lose context or operate on stale data.

**Independent Test**: Can be tested by editing annotations, saving them, running a missing-crop validation, and refreshing crop views without restarting the GUI.

**Acceptance Scenarios**:

1. **Given** the reviewer has unsaved annotation edits, **When** they run a utility action, **Then** the app either saves the required changes first or clearly prompts the reviewer before using stale data.
2. **Given** crops have been moved between class groups outside the GUI, **When** the reviewer explicitly imports and applies those moves, **Then** the affected annotations are updated and a reviewable summary is shown.
3. **Given** crops are missing for existing boxes, **When** the reviewer runs missing-crop detection, **Then** the app lists affected annotations and allows the reviewer to confirm removals before any deletion is applied.

---

### User Story 4 - Standardize Class Labels (Priority: P2)

As a VLM research team member, I want all labels and class folders standardized to the PIDRay class-label format so that downstream experiments consume one consistent taxonomy across PIDRay and compatible SIXray classes.

**Why this priority**: Current class folders include underscore formats and typos, which can fragment classes and create training/evaluation noise.

**Independent Test**: Can be tested by running a label-standardization review and verifying that labels and crop group names use only the approved class names, with non-matching labels flagged for reviewer decision.

**Acceptance Scenarios**:

1. **Given** an annotation label or crop folder uses underscores, **When** standardization runs, **Then** it is mapped to the approved space-separated class name when an unambiguous match exists.
2. **Given** a misspelled or unknown class is found, **When** standardization runs, **Then** it is flagged in a review list rather than silently changed to an uncertain class.
3. **Given** a reviewer creates or relabels a box, **When** they choose a class, **Then** the GUI offers only approved class labels by default while preserving an explicit review path for unknown labels.

---

### User Story 5 - Resume Efficiently Across Sessions (Priority: P3)

As a dataset reviewer, I want generated crops, review decisions, and validation summaries to persist by partition so that I can stop and resume work without regenerating everything.

**Why this priority**: The current workflow of deleting crops and regenerating them wastes time and makes the process fragile.

**Independent Test**: Can be tested by generating crops for a partition, closing the GUI, reopening it, and confirming the app resumes from the existing partition state without requiring regeneration.

**Acceptance Scenarios**:

1. **Given** partition crops already exist, **When** the reviewer reopens the app, **Then** the app identifies reusable crops and provides options to continue, refresh changed images, or rebuild the partition.
2. **Given** only some annotations changed after crop generation, **When** the reviewer refreshes crops, **Then** only affected images are regenerated unless the reviewer explicitly requests a full rebuild.

### Edge Cases

- The final partition contains fewer than 10,000 images and must still be selectable and fully processable.
- Image files and annotation JSON files may be missing, corrupted, or mismatched; the app must report these without stopping the entire partition run.
- A single image may contain non-rectangle shapes; crop generation and validation must ignore or flag unsupported shapes consistently.
- Crop filenames, crop display names, class folders, or source image names may change or contain separators; crop identity must still resolve to the correct annotation through stable manifest identity.
- A reviewer may change labels while crop generation is running; the app must prevent conflicting writes or clearly sequence the operations.
- A reviewer may cancel a pending crop deletion before confirming or saving; the crop and bounding box must remain unchanged in the annotation.
- Existing crop folders may contain legacy names such as underscores or misspellings; migration must distinguish safe mappings from uncertain mappings.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST divide the image list into deterministic partitions of 10,000 images each, preserving a stable image order across sessions.
- **FR-002**: The system MUST ask the reviewer which partition to work on before generating or browsing crops.
- **FR-003**: The system MUST generate crops only for the selected partition unless the reviewer explicitly selects a broader scope.
- **FR-004**: The system MUST persist partition crop state so an existing partition can be resumed without deleting or regenerating all crops.
- **FR-005**: The system MUST allow reviewers to refresh crops for changed annotations without rebuilding unaffected partition crops.
- **FR-006**: The system MUST provide an in-GUI crop browser that supports browsing by partition, class label, crop identity, and source image.
- **FR-007**: The system MUST allow a reviewer to open the source image and selected bounding box from any crop.
- **FR-008**: The system MUST make the GUI crop browsing workflow the primary place for crop-based relabeling and deletion decisions, keeping crop state and annotation state consistent.
- **FR-009**: The system MUST expose missing-crop detection, explicit import/apply of external moved-crop changes, label standardization, crop refresh, and save workflows from inside the GUI.
- **FR-010**: The system MUST prevent utility workflows from operating on stale unsaved edits without reviewer confirmation.
- **FR-011**: The system MUST provide a reviewable summary before applying destructive changes such as annotation deletion or large label migrations.
- **FR-012**: The system MUST maintain a single approved class-label vocabulary using these exact labels: Backpack, Belt, Box, Cable, Can, Clips, Coins, Electrical Device, Electronic Device, Glass Bottle, Handbag, Headset, Insulated Bottle, Ipad, Jar, Keyboard, Keys, Laptop, Laptop Charger, Laptop Power Adapter, Lighter, Mobile Phone, Nail Cutter, Plastic Bottle, Plastic Tray, Power Bank, Screwdriver, Spoon, Suitcase, Sunglasses, Thick Cables, Umbrella, Wallet, Watch.
- **FR-013**: The system MUST store and display approved class labels with spaces, not underscores.
- **FR-014**: The system MUST map unambiguous legacy class spellings and underscore folder names to the approved labels.
- **FR-015**: The system MUST flag unknown or ambiguous labels for reviewer decision instead of silently modifying them.
- **FR-016**: The system MUST track crop-to-annotation identity through a stable manifest identity that is independent of class folder and crop filename.
- **FR-017**: The system MUST produce human-readable run summaries for crop generation, label standardization, missing-crop detection, moved-crop updates, and save operations.
- **FR-018**: The system MUST preserve original image files and avoid modifying them during curation.
- **FR-019**: The system MUST keep annotation updates recoverable by making it clear which files changed and by allowing the reviewer to review changes before large operations are applied.
- **FR-020**: The system MUST support the current dataset scale of at least 56,176 image/annotation pairs without requiring a full-dataset crop rebuild for ordinary review work.
- **FR-021**: The system MUST allow crop display name, class label, deletion status, and class grouping to change without losing the link to the intended source image and bounding box.
- **FR-022**: The system MUST treat crop deletion as a pending soft-delete until the reviewer confirms or saves, and MUST allow cancellation before the bounding box is removed from the annotation.

### Key Entities

- **Dataset**: The full collection of image files and matching annotation files being curated.
- **Partition**: A deterministic subset of the dataset, normally 10,000 images, selected as the unit of crop generation and review.
- **Image**: A source X-ray image with a stable filename and matching annotation file.
- **Annotation File**: The JSON record for an image, including image metadata and labeled shapes.
- **Bounding Box**: A rectangular object annotation with label, points, and identity within an annotation file.
- **Crop**: An image patch generated from a bounding box, linked by stable manifest identity to its source image, source annotation, class label, and partition.
- **Class Label**: One approved PIDRay-format class name or an unknown label awaiting reviewer resolution.
- **Curation Operation**: A reviewer-triggered action such as crop generation, relabeling, deletion confirmation, moved-crop update, or label standardization.
- **Run Summary**: The reviewable result of a curation operation, including counts, warnings, errors, and changed annotations.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Reviewers can generate crops for any 10,000-image partition without processing images outside that partition.
- **SC-002**: Reviewers can reopen the app and resume a previously generated partition without deleting crop folders or regenerating all 56,176 images.
- **SC-003**: Reviewers can navigate from a crop to its source image and selected bounding box in no more than two user actions.
- **SC-004**: At least 95% of ordinary label corrections, defined as relabel, rename, move group, soft-delete, restore, and save/apply, can be completed from inside the GUI without closing it to run a separate script.
- **SC-005**: Label standardization leaves zero approved labels represented with underscores in annotations or displayed class names.
- **SC-006**: Unknown or ambiguous labels are reported for review with a count and source locations before any migration is applied.
- **SC-007**: A crop refresh after editing a small number of annotations processes only affected images unless the reviewer requests a full partition rebuild.
- **SC-008**: For each curation operation, the reviewer receives a summary showing processed items, changed annotations, skipped items, and errors.

## Assumptions

- The primary reviewer is a research team member curating object-detection annotations for VLM experiments.
- The current dataset contains 56,176 image/annotation pairs under a batch-style folder layout.
- The default partition size is exactly 10,000 images, with the final partition containing the remaining images.
- Image order for partitioning is based on a stable sorted list of image filenames unless a future dataset manifest explicitly defines another order.
- Existing JSON annotations are the source of truth for bounding boxes; crops are derived artifacts that can be regenerated.
- Existing utility behaviors remain valuable, but they should become integrated curation operations rather than separate workflows requiring the GUI to close; manual crop-folder moves are a legacy/external workflow applied only through an explicit GUI import/apply action.
- Original image files are immutable during curation.
- The approved class-label vocabulary is the PIDRay-format list supplied by the user, and compatible SIXray labels should use the same format when present.
