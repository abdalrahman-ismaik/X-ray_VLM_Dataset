# Contract: Annotation Editor Restoration

This contract describes the service and GUI behavior for restoring image-level annotation editing inside the refactored desktop curation app.

## Preconditions

- A dataset root is selected.
- The dataset has been indexed into partition manifests.
- A partition is selected.
- The active workflow uses fixture data, synthetic manifests, or selected-partition state only during implementation and tests.

## GUI Workflow Contract

### Browse Source Images Before Crops

**Trigger**: Reviewer selects a partition and opens Annotation Editor mode.

**Expected behavior**:

- The GUI lists or steps through source images in the selected partition even when no crop manifest exists.
- Loading one image displays the full image and all supported rectangular boxes.
- Unsupported shapes are reported in status text and preserved.

### Open From Crop Context

**Trigger**: Reviewer selects a crop in the crop browser and opens the Preview tab.

**Expected behavior**:

- The source image for the crop is loaded.
- All supported boxes are displayed.
- The crop-linked box is selected and visually highlighted.

### Select And Cycle Boxes

**Trigger**: Reviewer clicks on the image canvas.

**Expected behavior**:

- If one box is under the cursor, that box becomes selected.
- If multiple boxes are under the cursor, repeated clicks within 4 canvas pixels of the previous click point cycle through the matching boxes in ascending annotation shape order.
- The selected box details show image ID, bbox ID, label, and pending status.

### Draw A New Box

**Trigger**: Reviewer enters draw mode, drags a rectangle, and chooses a label.

**Expected behavior**:

- Drag direction can be any corner to any opposite corner.
- The preview rectangle is normalized to image coordinates.
- The reviewer must choose an approved PIDRay label before staging.
- Invalid boxes are not staged and the GUI shows a clear message.

### Move Or Resize A Box

**Trigger**: Reviewer selects an existing box and drags the box body or resize handles.

**Expected behavior**:

- Dragging the body stages a coordinate update after validation.
- Dragging a handle stages a resize after validation.
- The box is clamped to image bounds, and staging is blocked if the clamped box is smaller than 2 image pixels wide or 2 image pixels tall.
- Source JSON remains unchanged until Save Pending.

### Relabel Or Delete A Box

**Trigger**: Reviewer selects a box and chooses relabel or delete.

**Expected behavior**:

- Relabel uses approved PIDRay labels by default.
- Delete stages a pending deletion and keeps it cancellable before save.
- Unknown existing labels are shown for review and are not silently converted.

### Save Pending And Refresh

**Trigger**: Reviewer clicks the shared Save Pending action.

**Expected behavior**:

- Crop corrections and annotation-editor edits are saved through one shared pending queue.
- Annotation JSON is written atomically.
- Unsupported shapes and unrelated JSON fields are preserved.
- New boxes receive stable bbox IDs.
- Existing bbox IDs are preserved after move, resize, relabel, and save.
- If a crop manifest exists, only affected image crops are refreshed.
- If no crop manifest exists, the GUI reports that annotations were saved and crops can be generated later.

## Service Contracts

### `list_partition_source_images`

**Input**:

- `dataset_root`
- `partition_id`

**Output**:

- Ordered source-image summaries for the selected partition.

**Rules**:

- Must read the selected partition manifest.
- Must not scan the full dataset.

### `load_source_image_context`

**Input**:

- `dataset_root`
- `partition_id`
- `image_id`

**Output**:

- `SourceImageContext`

**Rules**:

- Loads one image and one annotation JSON file.
- Assigns or exposes stable bbox IDs for supported rectangles.
- Preserves unsupported shapes in the backing JSON.

### `hit_test_boxes`

**Input**:

- `SourceImageContext`
- image-coordinate point
- optional previous click point
- optional previous selected bbox ID

**Output**:

- selected `bbox_id` or no selection

**Rules**:

- Returns deterministic results for a single hit.
- Cycles through all hit boxes in ascending annotation shape order when the click point repeats within 4 canvas pixels of the previous click point.

### `stage_annotation_add`

**Input**:

- `SourceImageContext`
- normalized image-coordinate rectangle
- approved label

**Output**:

- pending annotation add change

**Rules**:

- Rejects invalid rectangles, including rectangles smaller than 2 image pixels wide or 2 image pixels tall after normalization.
- Rejects labels outside the approved PIDRay vocabulary.
- Does not write JSON.

### `stage_annotation_update_box`

**Input**:

- `SourceImageContext`
- `bbox_id`
- normalized image-coordinate rectangle

**Output**:

- pending annotation coordinate edit

**Rules**:

- Requires an existing supported box.
- Preserves `bbox_id`.
- Does not write JSON.

### `stage_annotation_relabel`

**Input**:

- `SourceImageContext`
- `bbox_id`
- approved label

**Output**:

- pending annotation relabel change

**Rules**:

- Requires an existing supported box.
- Rejects labels outside the approved PIDRay vocabulary.
- Does not silently normalize ambiguous existing labels.

### `stage_annotation_delete`

**Input**:

- `SourceImageContext`
- `bbox_id`

**Output**:

- pending annotation delete change

**Rules**:

- Requires an existing supported box.
- The delete is cancellable before Save Pending.
- Does not write JSON until committed.

### `commit_shared_pending_changes`

**Input**:

- `dataset_root`
- `partition_id`
- pending changes containing crop corrections and annotation edits

**Output**:

- operation result summary
- affected image IDs

**Rules**:

- Applies crop and annotation changes through one Save Pending action.
- Writes annotation JSON atomically.
- Preserves unsupported shapes and unrelated fields.
- Reports validation failures without clearing pending changes.

### `refresh_affected_image_crops`

**Input**:

- `dataset_root`
- `partition_id`
- affected image IDs

**Output**:

- operation result summary

**Rules**:

- Refreshes only affected images.
- Updates the selected partition crop manifest when it exists.
- Skips with a clear message when crops have not been generated yet.
- Must not generate crops for all partitions or the full dataset.

## Pending Change Payloads

Annotation edit payloads use the existing pending-change container and store these operation-specific fields:

```text
annotation_add:
  annotation_path
  image_id
  temporary_bbox_id
  label
  points

annotation_update_box:
  annotation_path
  image_id
  bbox_id
  points
  previous_points

annotation_relabel:
  annotation_path
  image_id
  bbox_id
  label
  previous_label

annotation_delete:
  annotation_path
  image_id
  bbox_id
  previous_label
  previous_points
```

## Error Contract

- Missing image: report the path and keep the partition selected.
- Missing annotation JSON: report the path and allow the reviewer to move to another image.
- Invalid rectangle: do not stage the change and explain the invalid condition.
- Unknown existing label: display it for review and require an approved label for new or relabeled boxes.
- Conflicting pending edits: keep pending changes visible and block Save Pending with a conflict summary until the reviewer cancels or corrects the conflict.
- Refresh skipped: report that no crop manifest exists yet and no crop rebuild was performed.

## Progress Contract

Long operations must update GUI status text and progress state:

- Loading one image: short status message.
- Saving pending edits: indeterminate progress if exact count is unknown.
- Refreshing affected crops: determinate progress when affected image count is known.
- Completion: summary with saved, cancelled, deleted, relabeled, coordinate-edited, and refreshed counts.
