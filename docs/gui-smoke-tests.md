# GUI Smoke Tests

Use only a fixture dataset or a deliberately selected partition.

1. Start the app with `python -m xray_curation.gui.app` from an environment that has the package on `PYTHONPATH`, or use the CLI during early migration.
2. Select a dataset batch folder that contains `images/` and `json/`.
3. Click `Index Dataset`.
4. Confirm the partition selector lists deterministic partition IDs such as `part-0001`.
5. Select one partition and click `Generate Crops`.
6. Confirm crops and `crop_manifest.json` are written only under `curation/partitions/<partition-id>/`.

Do not select all partitions or delete generated crops manually as part of this smoke test.

## Annotation Editor MVP Regression Notes

Use `tests/fixtures/small_dataset` or a deliberately selected partition only.

1. Index the fixture dataset with a small partition size such as `4`.
2. Select `part-0001` before generating crops.
3. Confirm the Preview tab shows a source image and all supported rectangular boxes.
4. Click overlapping boxes in the same canvas area to confirm selection cycles in annotation shape order.
5. Generate fixture crops for the selected partition only, then select a crop and confirm the matching source image and bounding box are selected.
6. Confirm unsupported shapes, invalid rectangles, missing files, and unknown labels surface as status messages instead of blocking source-image browsing.

## Annotation Editor Full Workflow Smoke Notes

Use fixture data or one deliberately selected partition. Do not scan the production dataset and do not generate crops for every partition.

1. Start the GUI with `python run_gui.py --dataset tests\fixtures\small_dataset`.
2. Click `Index Dataset`, select one partition, and open the `Preview` tab before generating crops.
3. Confirm selected partition source-image browsing works with `Previous Image` and `Next Image`.
4. Select a crop after fixture crops exist and confirm crop selection opens the source context and highlights the matching bounding box.
5. Click an existing box to select it, then click the same canvas point repeatedly when boxes overlap to confirm overlapping-box selection cycles in annotation shape order.
6. Click `Draw Box`, drag a rectangle in any direction, choose an approved PIDRay label, and confirm the new box appears as a pending edit.
7. Select an existing box and drag its body to move it.
8. Select an existing box and drag a corner handle to resize it.
9. Use `Relabel Box` to stage an approved PIDRay label change.
10. Use `Delete Box` to stage a reviewable deletion.
11. Use `Cancel Box Edit` and confirm pending edits for the selected box are removed before save.
12. Stage at least one crop correction and one annotation edit, then confirm both appear in the shared `Pending` tab.
13. Click the shared `Save Pending` action and confirm annotation JSON saves atomically.
14. When a fixture crop manifest exists, confirm saving annotation edits performs affected-image-only crop refresh instead of rebuilding the selected partition.

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

## Recorded Annotation Editor Guidance Result

Recorded on 2026-05-07 using fixture/synthetic-safe checks only:

- `python -m pytest tests`: passed, 67 tests.
- `python -m py_compile src\xray_curation\gui\app.py src\xray_curation\gui\crop_browser.py src\xray_curation\gui\annotation_editor.py`: passed.
- Guidance coverage checks verify that the GUI and README mention selected partition source-image browsing, crop selection source context, box selection, overlapping-box click cycling, `Draw Box`, approved PIDRay label assignment, move, resize, `Relabel Box`, `Delete Box`, `Cancel Box Edit`, the shared `Save Pending` action, atomic annotation saves, and affected-image-only crop refresh.
- Empty-state guidance checks verify that the Preview tab tells reviewers to index the dataset, select a partition, browse source images, use `Draw Box`, and save with `Save Pending`.
- Full human click-through on a real selected partition is still recommended before production curation, but it should use the workflow above and must remain limited to one selected partition.
