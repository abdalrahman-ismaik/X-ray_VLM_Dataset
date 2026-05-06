# Contract: Curation Operations

These contracts describe the service operations the GUI and optional CLI wrappers call. They are implementation-facing contracts, not external network APIs.

## Common Result Shape

Every operation returns:

```json
{
  "operation_id": "op-20260506-000001",
  "operation_type": "generate_crops",
  "status": "preview|applied|cancelled|failed",
  "partition_id": "part-0001",
  "summary": {
    "processed": 0,
    "changed": 0,
    "skipped": 0,
    "warnings": 0,
    "errors": 0
  },
  "warnings": [],
  "errors": [],
  "changed_files": []
}
```

## Select Partition

**Purpose**: Load or create the partition list for a dataset and choose the active review partition.

**Request**

```json
{
  "dataset_id": "batch_1",
  "partition_id": "part-0001"
}
```

**Response**

```json
{
  "partition_id": "part-0001",
  "image_count": 10000,
  "status": "ready|not_generated|stale|error",
  "crop_count": 0,
  "warnings": []
}
```

## Generate Crops

**Purpose**: Generate or resume crops for the selected partition.

**Request**

```json
{
  "dataset_id": "batch_1",
  "partition_id": "part-0001",
  "mode": "resume|refresh_changed|rebuild",
  "dry_run": false
}
```

**Rules**

- Processes only images in `partition_id`.
- Uses annotation rectangles as the source.
- Creates or updates `CropManifest`.
- Does not delete annotation boxes.

## Browse Crops

**Purpose**: Return crop records for the GUI crop browser.

**Request**

```json
{
  "partition_id": "part-0001",
  "label": "Laptop",
  "status": "active",
  "source_image": null,
  "text_query": null,
  "limit": 200,
  "offset": 0
}
```

**Response**

```json
{
  "items": [
    {
      "crop_id": "crop-abc123",
      "bbox_id": "bbox-abc123",
      "label": "Laptop",
      "display_name": "xray_00020 Laptop 003",
      "crop_path": "batch_1/curation/partitions/part-0001/crops/crop-abc123.jpg",
      "source_image_name": "xray_00020.jpg",
      "status": "active"
    }
  ],
  "total": 1
}
```

## Open Crop Context

**Purpose**: Open the parent image and select the bbox linked to a crop.

**Request**

```json
{
  "crop_id": "crop-abc123"
}
```

**Response**

```json
{
  "image_id": "image-001",
  "image_path": "batch_1/images/xray_00020.jpg",
  "annotation_path": "batch_1/json/xray_00020.json",
  "bbox_id": "bbox-abc123",
  "points": [[10, 20], [50, 80]]
}
```

## Stage Crop Edit

**Purpose**: Add a pending crop/bbox change from the GUI.

**Request**

```json
{
  "crop_id": "crop-abc123",
  "change_type": "relabel|soft_delete|restore|rename|move_group",
  "value": "Laptop Charger"
}
```

**Rules**

- Relabel, move group, and rename preserve `crop_id`.
- Soft delete marks the crop and bbox pending deletion.
- No annotation deletion happens until commit.

## Commit Pending Changes

**Purpose**: Apply approved pending changes to annotation JSON and manifests.

**Request**

```json
{
  "dataset_id": "batch_1",
  "partition_id": "part-0001",
  "change_ids": ["change-001", "change-002"],
  "confirm_destructive": true
}
```

**Rules**

- Destructive changes require `confirm_destructive=true`.
- Writes annotation files atomically.
- Returns changed files and a summary.

## Standardize Labels

**Purpose**: Preview or apply mappings from legacy labels/folders to approved labels.

**Request**

```json
{
  "dataset_id": "batch_1",
  "partition_id": "part-0001",
  "scope": "partition|dataset",
  "mode": "preview|apply"
}
```

**Rules**

- Approved labels use spaces.
- Ambiguous and unknown labels are reported before apply.
- Apply mode changes only mappings that were reviewed or unambiguous.

## Detect Missing Crops

**Purpose**: Compare annotation boxes and crop manifest/files.

**Request**

```json
{
  "partition_id": "part-0001",
  "mode": "preview|stage_deletions"
}
```

**Rules**

- Missing crop files do not automatically delete annotations.
- `stage_deletions` creates pending soft-delete changes.

## Import External Moved Crops

**Purpose**: Support legacy/manual crop folder moves as an explicit import/apply action.

**Request**

```json
{
  "partition_id": "part-0001",
  "external_crop_root": "batch_1/class_crops",
  "mode": "preview|apply"
}
```

**Rules**

- External moves are not automatically trusted.
- The importer resolves records through stable manifest identity when possible.
- Unresolvable crop files are reported for manual review.
