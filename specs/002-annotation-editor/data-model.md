# Data Model: Annotation Editor Restoration

## SourceImageContext

Represents one source image loaded from the selected partition.

**Fields**:

- `dataset_root`: root path for the active dataset batch.
- `partition_id`: selected partition identifier such as `part-0001`.
- `image_id`: stable image identifier from the partition manifest.
- `image_path`: immutable source image path.
- `annotation_path`: JSON annotation path for the image.
- `ordinal`: image position inside the selected partition.
- `image_size`: width and height loaded from the source image.
- `boxes`: supported rectangular boxes as `EditableBoundingBox` records.
- `unsupported_shape_count`: count of shapes preserved but not editable.
- `load_warnings`: non-fatal warnings such as unknown labels or unsupported shapes.

**Relationships**:

- Loaded from a selected partition image record.
- Owns zero or more `EditableBoundingBox` records.
- Produces `AnnotationEdit` pending changes.

**Validation rules**:

- `image_path` must exist and must not be modified.
- `annotation_path` must be loadable JSON before edits can be committed.
- Missing or corrupted files produce a visible GUI error and do not close the app.

## EditableBoundingBox

Represents one supported rectangular annotation shape in source-image coordinates.

**Fields**:

- `bbox_id`: stable `curation_bbox_id`.
- `shape_index`: current shape index in the loaded JSON.
- `label`: current annotation label.
- `points`: normalized rectangle coordinates in image space.
- `status`: `active`, `pending_add`, `pending_update`, `pending_relabel`, `pending_delete`, or `invalid`.
- `is_selected`: true when the canvas selection is this box.
- `source_crop_id`: optional crop record linked to this box when crops exist.

**Relationships**:

- Belongs to one `SourceImageContext`.
- May be linked to one active `CropRecord` through `image_id` and `bbox_id`.
- May have zero or more staged `AnnotationEdit` entries before save.

**Validation rules**:

- `bbox_id` must be present or assigned before save.
- `points` must describe a rectangle inside image bounds with width and height of at least 2 image pixels.
- Newly added and relabeled boxes must use an approved PIDRay label.
- Unknown existing labels are shown for review and not silently normalized.

## CanvasTransform

Converts between immutable source-image coordinates and the visible Tkinter canvas.

**Fields**:

- `image_width`, `image_height`: source image size.
- `canvas_width`, `canvas_height`: available canvas size.
- `scale`: uniform scale factor used to fit the image.
- `offset_x`, `offset_y`: canvas offsets for centering the scaled image.

**Relationships**:

- Used by the GUI canvas and annotation-editor service.
- Applies to the active `SourceImageContext`.

**Validation rules**:

- The transform must be recalculated after canvas resize or image change.
- Persisted coordinates are always image coordinates, never canvas coordinates.
- Conversion clamps drag and resize results to image bounds before staging, then rejects boxes smaller than 2 image pixels wide or 2 image pixels tall.

## AnnotationEdit

Represents a reviewer action staged before annotation JSON is changed.

**Fields**:

- `change_id`: unique pending-change identifier.
- `operation`: `annotation_add`, `annotation_update_box`, `annotation_relabel`, or `annotation_delete`.
- `dataset_root`: active dataset root.
- `partition_id`: selected partition.
- `image_id`: affected source image.
- `annotation_path`: JSON file to update on save.
- `bbox_id`: existing stable bbox ID or temporary ID for a new box.
- `label`: approved label for add or relabel operations.
- `points`: normalized rectangle points for add or coordinate edit operations.
- `previous_values`: optional snapshot for summaries and conflict detection.

**Relationships**:

- Stored in the shared pending queue alongside crop correction pending changes.
- Applied by `annotation_store` during one Save Pending action.
- Produces an `AffectedImageRefresh` when committed.

**Validation rules**:

- Add requires valid `points` and approved `label`.
- Coordinate edit requires valid `bbox_id` and valid replacement `points`.
- Relabel requires valid `bbox_id` and approved replacement `label`.
- Delete requires valid `bbox_id` and remains cancellable before save.
- Conflicting edits to the same box must not be merged automatically; Save Pending must be blocked with a conflict summary while the pending changes remain visible for cancellation or correction.

## SharedPendingQueue

Represents the single reviewer-visible queue for crop corrections and annotation-editor edits.

**Fields**:

- `changes`: ordered list of existing `PendingChange` objects plus annotation edit payloads.
- `affected_annotation_paths`: derived set of JSON paths touched by annotation edits.
- `affected_image_ids`: derived set of image IDs that need crop refresh after save.
- `summary`: reviewer-facing counts grouped by operation and image.

**Relationships**:

- Owned by GUI `CurationState`.
- Rendered by `PendingChangesPanel`.
- Committed by one Save Pending action.

**Validation rules**:

- Cancel removes the selected pending change without writing JSON.
- Save applies all valid pending changes atomically per annotation file.
- Failed validation keeps pending changes visible and reports what must be fixed.

## AffectedImageRefresh

Represents the post-save crop refresh work for annotation edits.

**Fields**:

- `dataset_root`: active dataset root.
- `partition_id`: selected partition.
- `image_ids`: images whose annotations changed.
- `crop_manifest_path`: selected partition crop manifest when it exists.
- `refreshed_crop_ids`: crop records regenerated or updated.
- `removed_crop_ids`: crop records removed because boxes were deleted.
- `skipped_reason`: reason refresh was skipped, such as no crop manifest yet.

**Relationships**:

- Created after successful annotation JSON commit.
- Uses selected partition state and existing crop manifest only.
- Updates crop browser state after worker completion.

**Validation rules**:

- Refresh must process only `image_ids`.
- If no crop manifest exists, save still succeeds and the GUI reports that crop generation can be run later.
- Original source images remain immutable.

## State Transitions

1. `partition selected`: source images can be browsed from the partition manifest.
2. `image loaded`: all supported boxes are displayed; unsupported shapes are reported.
3. `box selected`: reviewer can relabel, move, resize, delete, or inspect the box.
4. `new box drawn`: reviewer must assign an approved label before staging.
5. `edit staged`: shared pending queue contains the annotation edit; source JSON is unchanged.
6. `edit cancelled`: pending edit is removed; source JSON is unchanged.
7. `save pending`: valid crop and annotation changes are committed atomically.
8. `affected refresh`: only changed images are refreshed when crop state exists.
9. `state reloaded`: GUI reloads the active image and crop browser from updated manifests.
