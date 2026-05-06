# Test Results: Dataset Curation Refactor

Recorded on 2026-05-06.

## Unit Tests

Command:

```powershell
python -m pytest tests\unit
```

Result:

- `22 passed in 0.90s`

Coverage included:

- Annotation JSON preservation and bbox identity.
- Crop identity and manifest lookup.
- Approved PIDRay labels and aliases.
- Operation guards, summaries, and operation logs.
- Partition assignment and partition state.
- Pending relabel, rename, move group, soft-delete, restore, and commit behavior.

## Integration Tests

Command:

```powershell
python -m pytest tests\integration
```

Result:

- `9 passed in 1.02s`

Coverage included:

- Partition-only crop generation.
- Contract result shapes.
- Synthetic 10,001-image manifest without real image files.
- Crop browser source-context lookup.
- Missing-crop detection and staged deletion.
- External moved-crop preview/apply.
- Label standardization preview/apply.
- Resume and refresh-changed workflow.

## Smoke Checks

Command:

```powershell
python -m compileall -q src GUI_Dataset
```

Result:

- Passed with no output.

Wrapper help checks passed:

- `python GUI_Dataset\reviewProposals_gui.py --help`
- `python GUI_Dataset\Add_NewClass.py --help`
- `python GUI_Dataset\missing_crops_detector.py --help`
- `python GUI_Dataset\Moved_crops_json_updation_utility.py --help`

No full-dataset scan was run. No crops were generated for all 56,176 images.
