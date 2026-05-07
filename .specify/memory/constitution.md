<!--
Sync Impact Report
Version change: placeholder -> 1.0.0
Modified principles:
- Placeholder principles -> I. Source Data Integrity
- Placeholder principles -> II. Core Workflow Parity
- Placeholder principles -> III. Stable Identity and Derived Artifacts
- Placeholder principles -> IV. Responsive Partitioned GUI Workflow
- Placeholder principles -> V. Testable Services and Controlled Vocabulary
Added sections:
- Data and Architecture Constraints
- Development Workflow and Quality Gates
Removed sections:
- Placeholder Section 2
- Placeholder Section 3
Templates requiring updates:
- .specify/templates/plan-template.md: updated
- .specify/templates/spec-template.md: updated
- .specify/templates/tasks-template.md: updated
- .specify/templates/commands/: not present in this repository
Runtime guidance requiring updates:
- README.md: updated
Follow-up TODOs:
- None
-->
# X-ray VLM Dataset Curation Constitution

## Core Principles

### I. Source Data Integrity

Original X-ray image files MUST remain immutable. Annotation JSON files are the
source of truth for labels and bounding boxes; generated crops, manifests, and
partition state are derived artifacts. Destructive annotation changes, including
bounding-box deletion and large label migrations, MUST be staged or summarized
for reviewer confirmation before they are committed. Writes to annotation JSON
MUST be atomic and recoverable, and the reviewer MUST be able to identify which
annotation files changed.

Rationale: The dataset supports research experiments, so accidental source data
loss or silent annotation mutation can invalidate downstream training and
evaluation.

### II. Core Workflow Parity

Refactors MUST preserve the core reviewer workflows provided by the legacy GUI
unless the feature specification explicitly removes or replaces them. Core
workflows include browsing source images, viewing all current bounding boxes,
drawing a new bounding box, assigning an approved label, selecting an existing
box, editing or relabeling it, deleting it through a reviewable path, saving
annotation edits, and refreshing affected crops. A new GUI release MUST NOT be
considered functionally complete if these old workflows are absent and not
tracked as explicit follow-up scope.

Rationale: Architecture cleanup is valuable only if it keeps the research team
able to perform the annotation work that the tool exists to support.

### III. Stable Identity and Derived Artifacts

Bounding boxes and crops MUST be tracked through stable identities that do not
depend on crop filenames, class folders, visual order, or rectangle index alone.
Crops MUST be reproducible from annotation JSON and partition manifests. Class
folder names and crop display names MAY change, but those changes MUST NOT break
the link from a crop to its source image, annotation file, and bounding box.

Rationale: Reviewers rename, relabel, move, delete, and restore objects during
curation. Stable identity prevents those operations from corrupting the wrong
annotation.

### IV. Responsive Partitioned GUI Workflow

The GUI is the primary curation interface. It MUST work on a selected dataset
partition by default and MUST NOT scan or generate crops for the full 56,176
image dataset unless the reviewer explicitly chooses that scope. Long-running
operations, including indexing, crop generation, validation, and refresh, MUST
run without blocking the Tkinter event loop and MUST expose progress or status
feedback. Reviewers MUST be able to continue the workflow without closing the
GUI to run utility scripts.

Rationale: The dataset is too large for all-at-once review, and blocking GUI
operations make the tool feel broken even when work is still running.

### V. Testable Services and Controlled Vocabulary

Dataset indexing, annotation storage, crop generation, crop manifests, pending
changes, validation, and label standardization MUST live in importable services
that can be tested without launching Tkinter. Tests MUST use fixtures, synthetic
manifests, or selected-partition data rather than scanning the full dataset.
Approved PIDRay labels MUST be centralized and displayed with spaces, not
underscores; unknown or ambiguous labels MUST be reported for reviewer decision.

Rationale: Separating service logic from the GUI reduces duplicated scripts,
makes regressions easier to catch, and keeps labels consistent for VLM research.

## Data and Architecture Constraints

The project targets a local Windows desktop workflow using Python 3.11+,
Tkinter/ttk, Pillow, pathlib-based file handling, and pytest. Importable
application code MUST live under `src/xray_curation/`; legacy scripts in
`GUI_Dataset/` MAY remain only as compatibility wrappers around the new package.

Dataset roots are expected to contain `images/` and `json/`. Generated curation
state MUST live under the selected dataset root, normally in `curation/`, and
MUST be safe to regenerate from annotations and manifests. The default workflow
uses deterministic 10,000-image partitions; broader operations require explicit
reviewer intent.

## Development Workflow and Quality Gates

Every feature plan MUST run a Constitution Check before research/design and
again after design. The check MUST include:

- Source data integrity and reviewable annotation changes
- Core workflow parity with the legacy GUI, including bounding-box editing
- Stable crop and bounding-box identity
- Reproducible derived artifacts
- Responsive selected-partition GUI behavior
- Testable non-GUI services
- Approved PIDRay label vocabulary and unknown-label review

Specifications MUST call out any legacy workflow being removed, delayed, or
changed. Task lists MUST include service tests for annotation/crop behavior,
integration tests over fixtures or synthetic manifests, and manual GUI smoke
tests for visual and canvas interactions when GUI behavior changes. Implementers
MUST avoid full-dataset scans or all-dataset crop generation during tests unless
the user explicitly requests that scope.

## Governance

This constitution supersedes conflicting project practices, plans, and task
lists. Amendments MUST be made through a documented Spec Kit constitution
update, include a Sync Impact Report, and propagate any changed gates to
templates and runtime guidance. Each plan, implementation, and review MUST
explain any constitution violation in a complexity or risk section before the
work proceeds.

Versioning follows semantic versioning:

- MAJOR: Removing or redefining a principle in a way that permits previously
  forbidden behavior.
- MINOR: Adding a new principle or materially expanding required gates.
- PATCH: Clarifying wording without changing required behavior.

Compliance is reviewed at planning time, after design, before implementation
completion, and before legacy wrappers are considered complete.

**Version**: 1.0.0 | **Ratified**: 2026-05-07 | **Last Amended**: 2026-05-07
