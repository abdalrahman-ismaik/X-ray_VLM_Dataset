# Bounding-Box Identity Rules

Each rectangle shape receives a stable `flags.curation_bbox_id` value when annotations are loaded with ID assignment enabled.

Rules:

- Existing `flags.curation_bbox_id` values are preserved.
- Missing IDs are derived from image ID and rectangle coordinates.
- Label changes do not change the ID.
- Reordering shapes does not change existing IDs because the ID is stored on the shape.
- Crop IDs are derived from image ID and bounding-box ID, not from class folder names or crop filenames.
- Annotation writes are atomic: data is written to a temporary file and moved into place.

This allows a crop to be renamed, relabeled, moved between class groups, or soft-deleted later without losing the source bounding-box link.
