# Repository organization review

Reviewed on 2026-09-16 against `main` at `80b2d48` and the local documentation
changes accompanying this review.

## Findings

The committed repository has a clear application/service/domain structure,
separate unit and integration tests, small fixtures, compatibility launchers,
and dedicated documentation and specification folders. The public GitHub
`main` matched the local commit at review time.

The working folder initially had 107 tracked files missing under `src/`,
`tests/`, `docs/`, `specs/`, and `GUI_Dataset/`. These included the application
and its test suite. All were restored from the current commit with the owner's
approval. This was a local working-folder issue; the files were still present
in the committed GitHub repository.

## Documentation improvements

- Added four actual GUI screenshots under `docs/images/`, with captions,
  descriptive alt text, and capture notes.
- Made the root README a project overview with installation, a short workflow,
  repository layout, and documentation links.
- Preserved the previous detailed README in `docs/gui-guide.md` and adjusted
  its relative links.
- Documented copying the fixture before experimenting so demo edits do not
  change committed test data.

## Checks

- At the reviewed commit, the repository tracked 163 files totaling about
  892 KiB; the largest was `gui/crop_browser.py` at about 97 KiB. The new
  documentation screenshots account for additional, intentional binary assets.
- No raw dataset folders, ZIP archives, bytecode caches, or `.env` files were
  present in that tracked file list. This is a repository hygiene check, not a
  full security or history audit.
- Ignore rules cover the local dataset, raw batch data, generated curation
  files, virtual environments, build output, and pytest caches. Representative
  dataset and generated-fixture paths were checked with `git check-ignore`.
- All 132 tests passed in the restored working folder after the documentation
  changes, using Python 3.13.14 and a fresh environment installed with `.[dev]`
  (pytest 9.1.1, Pillow 12.3.0).
- Source and wrapper compile checks passed, and `run_gui.py --help` worked from
  the fresh environment.
- All 29 local links and anchors in the README and documentation resolved.
  All four PNG screenshots decoded at 1880 x 980 and were visually inspected.
- Every restored file matched its Git index content. This documentation update
  changes only the README and the new documentation assets.

## Remaining housekeeping

| Item | Suggested follow-up |
| --- | --- |
| No `LICENSE` file or GitHub license metadata | The owner should select the intended code license and document dataset/image reuse terms separately. |
| No GitHub Actions workflow | Add a Windows test job that installs `.[dev]` and runs the fixture-based suite on pushes and pull requests. |
| Empty GitHub description and topics | Add a short desktop-curation description and relevant topics such as `xray`, `annotation-tool`, `tkinter`, and `dataset-curation`. |
| Large GUI module | `gui/crop_browser.py` is roughly 2,500 lines. Consider extracting focused views when changing that area; the existing service/domain split is useful. |

The project-specific `.agents/`, `.specify/`, and `specs/` folders are referenced
by the development workflow and are not disposable cache folders. No license,
remote repository settings, or application behavior was changed by this review.
