# Legacy Compatibility Wrappers

This folder is kept only so older commands and habits do not break.

The refactored application code now lives in:

```text
src/xray_curation/
```

Recommended GUI entry point from the repository root:

```powershell
python run_gui.py --dataset dataset
```

Alternative package command:

```powershell
python -m xray_curation gui --dataset dataset
```

The scripts in this folder are thin wrappers around the new package:

- `reviewProposals_gui.py` launches the new GUI.
- `Add_NewClass.py` launches the new GUI.
- `missing_crops_detector.py` calls the selected-partition missing-crop service.
- `Moved_crops_json_updation_utility.py` calls the selected-partition moved-crop import service.

Do not add new curation logic here. Add reusable logic under `src/xray_curation/services/` and GUI code under `src/xray_curation/gui/`.
