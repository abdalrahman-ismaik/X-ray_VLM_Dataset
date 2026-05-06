# Data Model: Dataset Curation Refactor

## DatasetConfig

Represents one dataset batch that can be opened by the app.

**Fields**

- `dataset_id`: stable identifier, e.g. `batch_1`.
- `root_path`: dataset batch root.
- `images_dir`: directory containing source images.
- `annotations_dir`: directory containing JSON annotation files.
- `curation_dir`: directory containing derived manifests, logs, and crop artifacts.
- `partition_size`: default `10000`.
- `supported_extensions`: image extensions accepted by the app.

**Validation Rules**

- `images_dir` and `annotations_dir` must exist before review starts.
- Source image files are read-only from the app's perspective.
- `curation_dir` may be created by the app.

## DatasetManifest

Stable index of source images and annotations for a batch.

**Fields**

- `dataset_id`
- `created_at`
- `updated_at`
- `image_count`
- `annotation_count`
- `images`: ordered list of `ImageRecord`
- `partitions`: ordered list of `Partition`

**Validation Rules**

- Image order must be deterministic.
- Missing image/annotation pairs are listed as warnings, not fatal startup errors.
- Regenerating the manifest must preserve existing stable IDs where possible.

## ImageRecord

Represents one source image and its matching annotation.

**Fields**

- `image_id`: stable ID derived from dataset ID and image path.
- `image_name`
- `image_path`
- `annotation_path`
- `partition_id`
- `width`
- `height`
- `status`: `ready`, `missing_image`, `missing_annotation`, `invalid_annotation`

**Relationships**

- Belongs to one `DatasetManifest`.
- Belongs to one `Partition`.
- Has zero or more `BoundingBox` records.

## AnnotationFile

Represents the JSON annotation document for one image.

**Fields**

- `annotation_path`
- `image_id`
- `image_name`
- `image_width`
- `image_height`
- `shapes`: source shapes from the JSON file.
- `dirty`: whether in-memory changes are pending save.

**Validation Rules**

- Non-list `shapes` is normalized to an empty list with a warning.
- The app must preserve unknown JSON fields when saving.
- Only rectangle shapes are eligible for crop generation.

## BoundingBox

Represents a rectangular object annotation.

**Fields**

- `bbox_id`: stable curation identity. This should be stored or mirrored in the annotation metadata so it survives label changes and shape reordering.
- `image_id`
- `annotation_path`
- `shape_index`: current position in the source JSON, used as a lookup hint only.
- `label`: approved label or unknown review label.
- `points`: two rectangle points from the source annotation.
- `points_hash`: hash used to detect geometry drift during refresh.
- `status`: `active`, `pending_delete`, `deleted`, `unsupported`, `invalid`

**Validation Rules**

- `bbox_id` is the identity for crop and operation updates, not `shape_index`.
- `shape_index` must be recalculated after deletion or reordering.
- Pending deletion can be cancelled before commit.

## ClassLabelVocabulary

Approved PIDRay class labels and legacy mappings.

**Approved Labels**

Backpack, Belt, Box, Cable, Can, Clips, Coins, Electrical Device, Electronic Device, Glass Bottle, Handbag, Headset, Insulated Bottle, Ipad, Jar, Keyboard, Keys, Laptop, Laptop Charger, Laptop Power Adapter, Lighter, Mobile Phone, Nail Cutter, Plastic Bottle, Plastic Tray, Power Bank, Screwdriver, Spoon, Suitcase, Sunglasses, Thick Cables, Umbrella, Wallet, Watch.

**Fields**

- `approved_labels`: ordered list of approved display labels.
- `aliases`: map of unambiguous legacy spellings/folder names to approved labels.
- `unknown_labels`: labels requiring reviewer decision.

**Validation Rules**

- Approved labels are stored and displayed with spaces, never underscores.
- Underscore aliases are normalized only when the mapping is unambiguous.
- Unknown or ambiguous labels are flagged for review before migration.

## Partition

Review unit for crop generation and browsing.

**Fields**

- `partition_id`: e.g. `part-0001`.
- `dataset_id`
- `index_start`: zero-based inclusive source image index.
- `index_end`: zero-based exclusive source image index.
- `image_count`
- `status`: `not_generated`, `generating`, `ready`, `stale`, `refreshing`, `error`
- `last_generated_at`
- `crop_count`
- `warning_count`

**State Transitions**

- `not_generated` -> `generating` -> `ready`
- `ready` -> `stale` when source annotations change
- `stale` -> `refreshing` -> `ready`
- Any active state -> `error` with a recoverable run summary

## CropRecord

Represents one generated crop and its review state.

**Fields**

- `crop_id`: stable ID linked to `bbox_id`.
- `bbox_id`
- `image_id`
- `partition_id`
- `label`
- `display_name`
- `crop_path`
- `source_image_path`
- `source_annotation_path`
- `bbox_points`
- `bbox_points_hash`
- `status`: `active`, `pending_delete`, `deleted`, `missing_file`, `stale`
- `generated_at`
- `updated_at`

**Validation Rules**

- `crop_id` is independent of filename, class label, and class folder.
- Relabeling updates `label` and the source annotation but preserves `crop_id`.
- Renaming updates `display_name` or file path but preserves `crop_id`.
- Deletion is soft until commit/save.

## CropManifest

Partition-level manifest for generated crops.

**Fields**

- `partition_id`
- `dataset_id`
- `manifest_version`
- `generated_from`
- `records`: map of `crop_id` to `CropRecord`
- `summary`: counts by status and label

**Validation Rules**

- Manifest writes must be atomic: write temp file, then replace.
- Missing crop files are represented as record status, not immediate annotation deletion.
- A manifest can be rebuilt from annotations and source images.

## PendingChange

An unapplied review decision.

**Fields**

- `change_id`
- `operation_id`
- `target_type`: `bbox`, `crop`, `label`, `manifest`
- `target_id`
- `change_type`: `relabel`, `soft_delete`, `restore`, `rename`, `move_group`, `standardize_label`
- `before`
- `after`
- `created_at`
- `review_status`: `pending`, `approved`, `cancelled`, `applied`

**Validation Rules**

- Destructive changes require approval before apply.
- Cancelled changes must leave annotation JSON unchanged.
- Applied changes must be included in the operation summary.

## OperationRun

Summary and audit record for a curation operation.

**Fields**

- `operation_id`
- `operation_type`: `generate_crops`, `refresh_crops`, `standardize_labels`, `detect_missing_crops`, `import_external_moves`, `save_annotations`
- `partition_id`
- `status`: `queued`, `running`, `preview`, `applied`, `cancelled`, `failed`
- `started_at`
- `finished_at`
- `inputs`
- `summary_counts`
- `warnings`
- `errors`
- `changed_files`

**Validation Rules**

- Every operation visible from the GUI returns an operation summary.
- Failed operations must not leave partially written annotation files.
- Operation logs are append-only.
