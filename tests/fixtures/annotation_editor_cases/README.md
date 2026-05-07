# Annotation Editor Fixture Cases

These JSON files are copied into temporary `small_dataset` test roots by pytest fixtures. Tests must not mutate the checked-in fixture dataset directly and must not scan or generate crops for the production dataset.

- `overlap_unknown_unsupported.json`: two overlapping rectangular boxes, one unknown legacy label, one unsupported polygon, and one invalid rectangle. It supports source-context loading, warning, stable identity, and overlap-cycling tests.
