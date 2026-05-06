# GUI Smoke Tests

Use only a fixture dataset or a deliberately selected partition.

1. Start the app with `python -m xray_curation.gui.app` from an environment that has the package on `PYTHONPATH`, or use the CLI during early migration.
2. Select a dataset batch folder that contains `images/` and `json/`.
3. Click `Index Dataset`.
4. Confirm the partition selector lists deterministic partition IDs such as `part-0001`.
5. Select one partition and click `Generate Crops`.
6. Confirm crops and `crop_manifest.json` are written only under `curation/partitions/<partition-id>/`.

Do not select all partitions or delete generated crops manually as part of this smoke test.

## Recorded Smoke Result

Recorded on 2026-05-06 using fixture/synthetic-safe checks only:

- `python -m compileall -q src GUI_Dataset`: passed.
- `python GUI_Dataset\reviewProposals_gui.py --help`: passed.
- `python GUI_Dataset\Add_NewClass.py --help`: passed.
- `python GUI_Dataset\missing_crops_detector.py --help`: passed.
- `python GUI_Dataset\Moved_crops_json_updation_utility.py --help`: passed.
- Unit tests: `22 passed`.
- Integration tests: `9 passed`.

Manual visual interaction with a real selected partition remains the first user-run check before production curation. The smoke result above verifies that GUI modules and legacy launchers import and expose safe selected-partition entry points without touching the full dataset.
