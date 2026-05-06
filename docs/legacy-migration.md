# Legacy Migration Notes

The existing scripts in `GUI_Dataset/` stay in place during the migration so current review work is not blocked.

Phase 1 to Phase 3 introduce the new package shell, domain models, file-backed services, CLI entry points, and a minimal Tkinter partition selector. Later phases can convert the legacy scripts into thin wrappers around these services instead of duplicating JSON, crop, and label logic.

Migration rules:

- Keep original image files immutable.
- Treat generated crops and manifests as derived local artifacts under `batch_*/curation/`.
- Add stable bounding-box IDs before relying on crop filenames or class folders.
- Move logic into `src/xray_curation/services/` before wiring it into GUI views.
- Use fixture datasets for automated tests; do not run tests against the full research dataset.

## Migration Status

Completed wrapper conversions:

- `GUI_Dataset/reviewProposals_gui.py` launches `xray_curation.gui.app`.
- `GUI_Dataset/Add_NewClass.py` launches `xray_curation.gui.app`.
- `GUI_Dataset/missing_crops_detector.py` calls selected-partition missing-crop services.
- `GUI_Dataset/Moved_crops_json_updation_utility.py` calls selected-partition external-move services.

Core logic now lives under `src/xray_curation/`:

- `domain/` contains labels, annotation identity, crop identity, partition helpers, and operation dataclasses.
- `services/` contains JSON safety, indexing, crop generation, manifest queries, validation, label standardization, refresh-changed behavior, and operation logs.
- `gui/` contains the Tkinter shell, crop browser, source context panel, utility panel, label standardization panel, state container, and worker helpers.

Legacy wrappers intentionally keep only argument parsing, package path setup, and service/GUI delegation.
