# Feature Specification: Annotation Editor Restoration

**Feature Branch**: `002-annotation-editor`  
**Created**: 2026-05-07  
**Status**: Draft  
**Input**: User description: "Restore the legacy image annotation editor inside the refactored GUI so reviewers can view all boxes, select boxes, draw new rectangular boxes, assign approved labels, edit or relabel boxes, delete boxes through the pending save workflow, save JSON atomically, refresh only affected crops, preserve stable identity, avoid modifying original images, avoid full-dataset scans, and document the workflow in the README and GUI."

## Clarifications

### Session 2026-05-07

- Q: Should existing bounding boxes support coordinate editing in this feature? -> A: Existing boxes can be drag-moved and drag-resized on the canvas in this feature.
- Q: What should happen to crops immediately after saving annotation edits? -> A: Automatically refresh only crops for the affected image immediately after saving annotation edits.
- Q: Should Annotation Editor work before crops are generated? -> A: Annotation Editor can browse source images in the selected partition even if no crops exist yet.
- Q: Should crop corrections and annotation-editor edits share one pending queue/save button? -> A: Crop corrections and annotation-editor edits use one shared pending queue and one Save Pending action.
- Q: How should overlapping boxes be selected? -> A: Repeated clicks within 4 canvas pixels of the previous click point cycle through overlapping boxes under the cursor in ascending annotation shape order.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inspect and Select Image Boxes (Priority: P1)

As a dataset reviewer, I want the source-image preview to show every existing bounding box for the selected image so that I can inspect the full annotation context and select the exact object I need to edit.

**Why this priority**: The current refactored GUI only highlights the selected crop's box. The old GUI allowed image-level annotation review, and reviewers need that context before drawing, deleting, or editing boxes.

**Independent Test**: Can be tested with a fixture partition by opening Annotation Editor before crop generation, browsing a source image in the selected partition, verifying all boxes on the source image are visible, selecting a box directly on the image, and confirming the selected box details are shown without scanning the full dataset.

**Acceptance Scenarios**:

1. **Given** a selected partition with source images and annotations, **When** the reviewer opens Annotation Editor before crop generation, **Then** the GUI allows browsing source images from that selected partition.
2. **Given** a selected crop whose source image has multiple boxes, **When** the reviewer opens the Preview area, **Then** the GUI displays the full source image with all supported rectangular boxes visible and the crop's original box highlighted as selected.
3. **Given** all boxes are visible on the source image, **When** the reviewer clicks inside an existing box, **Then** that box becomes the selected annotation and its label, identity, and source image are displayed.
4. **Given** multiple boxes overlap under the cursor, **When** the reviewer repeatedly clicks within 4 canvas pixels of the previous click point, **Then** selection cycles through the overlapping boxes in ascending annotation shape order and the active box remains visually clear.
5. **Given** the selected image contains unsupported or invalid shapes, **When** the annotation editor loads the image, **Then** supported rectangular boxes remain editable and unsupported shapes are reported without blocking the whole image review.

---

### User Story 2 - Draw and Label New Boxes (Priority: P1)

As a dataset reviewer, I want to draw a new rectangular bounding box on the source image and assign an approved PIDRay label so that missing object annotations can be added from inside the refactored GUI.

**Why this priority**: Adding missing boxes was a core old-GUI workflow. Without it, the refactored GUI cannot replace the original annotation editor.

**Independent Test**: Can be tested with a fixture image by choosing draw mode, dragging a rectangle, selecting an approved label, staging the new box, saving it, and verifying the annotation JSON contains the new labeled box with stable identity while the original image file is unchanged.

**Acceptance Scenarios**:

1. **Given** the reviewer is viewing a source image, **When** they enter draw mode and drag a rectangle, **Then** the GUI previews the new bounding box on the image before saving.
2. **Given** a new box has been drawn, **When** the reviewer assigns a class label, **Then** the GUI offers approved PIDRay labels by default using the exact space-separated label format.
3. **Given** the reviewer confirms a newly drawn labeled box, **When** they save pending annotation edits, **Then** the new box is written to the source annotation JSON atomically and receives a stable bounding-box identity.
4. **Given** a drawn rectangle is too small, outside the image, or otherwise invalid, **When** the reviewer tries to stage it, **Then** the GUI prevents saving and explains what must be corrected.

---

### User Story 3 - Edit, Delete, Save, and Refresh Affected Crops (Priority: P1)

As a dataset reviewer, I want to move, resize, relabel, or delete an existing bounding box through the same shared pending-change workflow used for crop corrections so that all annotation edits stay safe and synchronized with partition crops.

**Why this priority**: Coordinate correction, relabeling, and deletion are core annotation activities, and the refactored crop browser must stay consistent with the annotation JSON after those edits.

**Independent Test**: Can be tested with fixture crops by selecting an existing box on the source image, drag-moving or drag-resizing it, staging a relabel, staging a deletion, cancelling one change, saving another, and verifying only the affected image's crops are refreshed automatically.

**Acceptance Scenarios**:

1. **Given** an existing box is selected on the source image, **When** the reviewer changes its label, **Then** the change is staged as a pending annotation edit and the original JSON remains unchanged until save.
2. **Given** an existing box is selected on the source image, **When** the reviewer drag-moves or drag-resizes it, **Then** the coordinate change is staged as a pending annotation edit and the original JSON remains unchanged until save.
3. **Given** an existing box is selected, **When** the reviewer requests deletion, **Then** the box is marked for pending deletion and can be cancelled before the annotation JSON is modified.
4. **Given** crop corrections and annotation-editor edits are staged together, **When** the reviewer reviews the pending list, **Then** the GUI shows one shared pending queue containing both kinds of changes.
5. **Given** pending annotation edits exist for one image, **When** the reviewer uses Save Pending, **Then** annotation JSON is written atomically, the changed image is identified, and only crops derived from that image are refreshed immediately.
6. **Given** a selected box is linked to an existing crop, **When** the box is moved, resized, relabeled, or deleted, **Then** crop identity and bounding-box identity remain stable until deletion is committed, and the crop browser reflects the new state after refresh.

---

### User Story 4 - Guide Reviewers Through Annotation Editor Mode (Priority: P2)

As a reviewer using the refactored GUI, I want clear in-app and README guidance for Annotation Editor mode so that I understand when to browse crops, when to draw/edit boxes, and how saving and refresh work.

**Why this priority**: The GUI now contains crop review, utilities, and image annotation editing. Clear guidance prevents accidental destructive actions and reduces confusion for new users.

**Independent Test**: Can be tested by opening the GUI without prior knowledge and confirming the Workflow or Preview guidance explains how to inspect boxes, draw boxes, assign labels, stage changes, save, and refresh affected crops.

**Acceptance Scenarios**:

1. **Given** the reviewer opens the GUI, **When** they view the workflow guide, **Then** it includes Annotation Editor mode steps alongside crop browsing steps.
2. **Given** the reviewer enters Annotation Editor mode, **When** no box is selected or no label is chosen, **Then** the GUI displays actionable status text instead of leaving the reviewer unclear.

### Edge Cases

- The source image has many overlapping boxes; repeated clicks within 4 canvas pixels of the previous click point must cycle through boxes under the cursor in ascending annotation shape order and make the active box clear.
- The reviewer draws a rectangle from any corner direction; the stored box must still normalize to valid image coordinates.
- The reviewer drag-moves or drag-resizes an existing box beyond image bounds; the editor must clamp coordinates to image bounds and reject staging only when the clamped box becomes smaller than 2 image pixels wide or 2 image pixels tall.
- The reviewer cancels a newly drawn box before saving; no annotation JSON changes are written.
- The reviewer stages edits to multiple boxes in the same image; the pending summary must identify all affected boxes.
- The reviewer stages crop corrections and annotation-editor edits before saving; the shared pending queue must show both without duplicate or conflicting operations.
- The reviewer edits an annotation before partition crops were generated; the annotation JSON is saved and the affected image is ready for later selected-partition crop generation.
- The reviewer edits an annotation after partition crops were generated; only the affected image is refreshed automatically.
- The selected image is missing, corrupted, or has mismatched JSON metadata; the GUI must report the issue and keep the app usable.
- Unsupported shapes exist in the annotation JSON; they must be preserved and not accidentally deleted.
- Unknown legacy labels may already exist; the editor must not silently map ambiguous labels while drawing or relabeling boxes.
- Tests and implementation must not scan the full dataset or generate crops for all 56,176 images.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide an Annotation Editor mode in the refactored GUI's source-image preview area.
- **FR-002**: The system MUST allow source-image browsing for the selected partition before crops are generated.
- **FR-003**: The system MUST display all supported rectangular bounding boxes for the active source image, not only the selected crop's bounding box.
- **FR-004**: The system MUST visually distinguish the selected bounding box from other boxes.
- **FR-005**: The system MUST allow a reviewer to select an existing bounding box directly from the source image view.
- **FR-006**: The system MUST show selected-box details including image identity, bounding-box identity, current label, and pending status.
- **FR-007**: The system MUST allow a reviewer to draw a new rectangular bounding box on the source image.
- **FR-008**: The system MUST normalize drawn rectangles to valid image-coordinate bounding boxes regardless of drag direction.
- **FR-009**: The system MUST prevent invalid new boxes from being staged, including boxes outside the image or below a minimum size of 2 image pixels wide and 2 image pixels tall after normalization.
- **FR-010**: The system MUST allow the reviewer to assign an approved PIDRay class label to a new bounding box.
- **FR-011**: The system MUST allow the reviewer to relabel an existing selected bounding box using approved PIDRay labels by default.
- **FR-012**: The system MUST allow the reviewer to drag-move an existing selected bounding box on the source image canvas.
- **FR-013**: The system MUST allow the reviewer to drag-resize an existing selected bounding box on the source image canvas.
- **FR-014**: The system MUST normalize moved or resized box coordinates, clamp them to image bounds, and reject staging if the clamped box is smaller than 2 image pixels wide or 2 image pixels tall.
- **FR-015**: The system MUST preserve an explicit review path for unknown existing labels without silently converting ambiguous labels.
- **FR-016**: The system MUST allow a reviewer to stage deletion of a selected bounding box through a pending/reviewable workflow.
- **FR-017**: The system MUST allow cancellation of pending add, coordinate edit, relabel, or delete edits before annotation JSON is changed.
- **FR-018**: The system MUST use one shared pending queue for crop corrections and annotation-editor edits.
- **FR-019**: The system MUST use one Save Pending action for committed crop corrections and annotation-editor edits.
- **FR-020**: The system MUST save annotation edits atomically to the relevant source JSON file only after reviewer confirmation.
- **FR-021**: The system MUST preserve unsupported shapes and unrelated annotation fields when saving edited annotation JSON.
- **FR-022**: The system MUST assign stable bounding-box identity to newly added boxes.
- **FR-023**: The system MUST preserve stable identity for existing boxes after selection, coordinate edit, relabel, save, and crop refresh.
- **FR-024**: The system MUST keep crop records linked to the intended source image and bounding box after annotation edits.
- **FR-025**: The system MUST automatically refresh only crops for images affected by saved annotation edits unless the reviewer explicitly requests a broader rebuild.
- **FR-026**: The system MUST never modify original image files.
- **FR-027**: The system MUST avoid full-dataset scans and all-dataset crop generation during implementation, tests, and default GUI annotation-editor workflows.
- **FR-028**: The system MUST provide reviewer-visible summaries for saved annotation edits, including added, coordinate-edited, relabeled, deleted, cancelled, and refreshed items.
- **FR-029**: The system MUST keep the GUI responsive while loading annotations, saving edits, and refreshing affected crops.
- **FR-030**: The system MUST provide in-GUI workflow guidance for Annotation Editor mode.
- **FR-031**: The README MUST document how to use Annotation Editor mode and how it interacts with crop browsing, pending changes, save, and refresh.
- **FR-032**: The system MUST support validation through fixture datasets, synthetic manifests, and selected-partition state only.
- **FR-033**: The system MUST cycle through overlapping bounding boxes under the cursor when the reviewer repeatedly clicks within 4 canvas pixels of the previous click point, using ascending annotation shape order as the deterministic cycle order.

### Constitution Alignment *(mandatory for curation GUI changes)*

- **Core workflow parity**: This feature restores the legacy source-image annotation workflows that are currently missing: viewing all boxes, drawing new boxes, assigning labels, selecting/editing boxes, deleting boxes, saving edits, and refreshing affected crops.
- **Data safety**: Original images remain immutable. Annotation JSON changes are staged, summarized, cancellable before save, and written atomically only after reviewer confirmation.
- **Partition scope**: Implementation and tests operate on fixture annotations, fixture crops, synthetic manifests, and selected-partition state only. Full-dataset scans and all-dataset crop generation are out of scope.
- **Label vocabulary**: New and relabeled boxes use the approved PIDRay class vocabulary with spaces. Unknown or ambiguous existing labels are shown for review rather than silently changed.

### Key Entities *(include if feature involves data)*

- **Source Image**: The full X-ray image being reviewed in the Preview area; original image bytes are immutable and the image can be reached through selected-partition browsing or crop context.
- **Annotation File**: The JSON source of truth for one source image, including metadata, rectangular boxes, unsupported shapes, and unrelated fields that must be preserved.
- **Bounding Box**: A rectangular object annotation with image-coordinate points, label, stable identity, selection state, and optional pending edit status.
- **Annotation Edit**: A pending reviewer action that adds, moves, resizes, relabels, deletes, restores, or cancels a bounding-box change before save.
- **Shared Pending Queue**: The single review list that contains crop corrections and annotation-editor edits before the reviewer uses Save Pending.
- **Affected Image**: A source image whose annotation JSON changed and whose derived crops need automatic refresh.
- **Crop Record**: A derived crop manifest entry linked to a source image and bounding-box identity.
- **Approved Label**: One PIDRay class label from the centralized vocabulary, displayed with spaces rather than underscores.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer can open a fixture source image from selected-partition browsing before crop generation and see all supported boxes.
- **SC-002**: A reviewer can open a fixture source image and see all supported boxes with one box selected in no more than two actions after choosing a crop.
- **SC-003**: A reviewer can draw, label, stage, save, and verify a new bounding box on a fixture image without modifying the original image file.
- **SC-004**: A reviewer can select an existing box, drag-move or drag-resize it, save it, and see the updated crop region after affected-crop refresh.
- **SC-005**: A reviewer can select an existing box, relabel it, save it, and see the updated label in both the source-image view and crop browser after affected-crop refresh.
- **SC-006**: A reviewer can stage both a crop correction and an annotation-editor edit and see both in one shared pending queue.
- **SC-007**: A reviewer can stage and cancel a box deletion before save, leaving the annotation JSON unchanged.
- **SC-008**: Saved annotation edits report counts for added, coordinate-edited, relabeled, deleted, cancelled, and refreshed items.
- **SC-009**: Refresh after saving edits to one fixture image processes only that affected image unless the reviewer explicitly requests a broader rebuild.
- **SC-010**: Unsupported annotation shapes and unrelated JSON fields remain present after saving box edits.
- **SC-011**: Automated tests for this feature complete using fixtures, synthetic manifests, or selected-partition state without scanning the full 56,176-image dataset.
- **SC-012**: In-app guidance and README instructions are sufficient for a reviewer to identify how to enter Annotation Editor mode, draw a box, assign a label, save, and refresh affected crops.
- **SC-013**: A reviewer can select each box in a group of overlapping fixture boxes by repeatedly clicking within 4 canvas pixels of the previous click point, with selection cycling in annotation shape order and the active box visibly changing each time.

## Assumptions

- Annotation Editor mode is added to the existing refactored GUI rather than reintroducing the old monolithic GUI script.
- Rectangular bounding boxes are the only editable shape type for this feature; unsupported shapes are preserved and reported.
- Newly drawn boxes require an approved PIDRay label before they can be staged.
- Existing boxes can be drag-moved and drag-resized on the source image canvas in this feature.
- Annotation Editor can browse source images in the selected partition even when no crops have been generated yet.
- Crop refresh after annotation edits happens automatically for the affected image using existing selected-partition state rather than rebuilding all partitions.
- Crop corrections and annotation-editor edits share one pending queue and one Save Pending action.
- Repeated clicks within 4 canvas pixels of the previous click point cycle through overlapping bounding boxes under the cursor in ascending annotation shape order.
- Existing legacy wrapper scripts remain compatibility entry points and should not become the primary implementation location.
