# Research: Dataset Curation Refactor

## Decision: Use a `src/` Package Layout

**Decision**: Move importable application code into `src/xray_curation/`, with tests at repository root and legacy scripts kept as wrappers during migration.

**Rationale**: The current repository mixes scripts, data, generated crops, and configuration. The Python Packaging User Guide describes `src/` layout as separating import packages from the repository root and helping avoid accidental imports from the working tree. For this project, that separation is useful because the dataset root contains large files and legacy scripts that should not become importable application modules.

**Alternatives considered**:

- Keep flat scripts in `GUI_Dataset/`: fastest initially, but preserves duplication and hard-coded paths.
- Move everything under one `app.py`: reduces file count, but keeps GUI, data access, and operations coupled.

**Reference**: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/

## Decision: Keep Tkinter, but Move Long Work Out of Event Handlers

**Decision**: Keep Tkinter/ttk as the GUI technology for the refactor, but make crop generation, validation, label standardization, and moved-crop imports service operations that run outside direct event handlers. UI updates must be marshalled back through the Tk event loop.

**Rationale**: The existing GUI already uses Tkinter and the team has a working review surface. Python's Tkinter docs explain that Tcl/Tk is event-driven and long-running computations should not run in event handlers. TkDocs similarly emphasizes returning quickly to the event loop and using timer events/threads for long work. The refactor should respect that model instead of rebuilding the GUI stack.

**Alternatives considered**:

- Rebuild as a web app: stronger long-term collaboration story, but too large for this refactor and unnecessary for a local research workflow.
- Keep background threads inside the GUI class: workable short-term, but keeps operation logic hard to test and reuse.

**References**:

- https://docs.python.org/3/library/tkinter.html#threading-model
- https://tkdocs.com/tutorial/eventloop.html

## Decision: Treat Crops as Derived Data with Manifests

**Decision**: Store crop state in a partition-level manifest keyed by stable crop/bounding-box IDs. Generated crop files are cache artifacts. Class folder names and crop filenames are not authoritative.

**Rationale**: The current utilities infer annotation edits from crop filenames and class folders, which breaks when labels are renamed, typos are corrected, crops are moved, or rectangle indexes change. Visual dataset tools such as FiftyOne support object patch views that keep patches connected to source labels, and DVC frames data processing as reproducible stages with code, dependencies, and outputs. The same principle applies here: crops should be reproducible outputs with explicit metadata.

**Alternatives considered**:

- Keep class folders as source of truth: familiar, but fragile and already causing stale-state problems.
- Use a database first: better querying, but heavier for a single-user local workflow and harder to inspect/debug than file manifests.

**References**:

- https://docs.voxel51.com/user_guide/using_views.html
- https://docs.voxel51.com/user_guide/app.html#viewing-object-patches
- https://doc.dvc.org/start/data-pipelines/data-pipelines

## Decision: Partition by Stable Sorted Image Order

**Decision**: Partition images by a stable sorted image list, using 10,000 images per partition and a smaller final partition.

**Rationale**: The user explicitly requested 10,000-image parts. Sorting filenames is deterministic, easy to explain, independent of filesystem traversal order, and sufficient for the current batch layout. A future dataset manifest can override this order if research sampling requirements change.

**Alternatives considered**:

- Random partitioning: useful for model training splits, but poor for repeatable review sessions unless seeded and tracked.
- Class-balanced partitioning: attractive for review load balancing, but requires a full annotation scan before first use and could slow startup.

## Decision: Standardize Labels Through One Vocabulary Service

**Decision**: Implement one shared vocabulary module containing the approved PIDRay class names, legacy aliases, normalization rules, and unknown-label review behavior.

**Rationale**: The current scripts duplicate label cleanup and convert spaces to underscores differently. The approved class labels must be displayed and stored with spaces. A single service prevents the GUI and utilities from diverging.

**Alternatives considered**:

- Keep per-script label cleanup: preserves current inconsistencies.
- Automatically fuzzy-match unknowns: dangerous for research labels; unknowns should be reviewer-confirmed.

## Decision: Use Reviewable Operation Summaries

**Decision**: All large or destructive operations produce summaries before applying changes: files affected, crops changed, labels mapped, unknown labels, pending deletions, skipped items, and errors.

**Rationale**: The existing workflow asks ad hoc prompts in utility scripts and requires closing the GUI. Reviewable summaries make operations safer and allow the GUI to be the primary correction surface.

**Alternatives considered**:

- Apply changes immediately: fastest, but risks silent annotation loss.
- Write only console logs: insufficient when operations run inside the GUI.
