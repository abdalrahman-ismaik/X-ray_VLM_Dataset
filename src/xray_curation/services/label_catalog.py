from __future__ import annotations

from pathlib import Path
from typing import Any

from xray_curation.config import DatasetConfig
from xray_curation.domain.labels import (
    APPROVED_FORMAL_LABELS,
    available_labels,
    label_key,
    normalize_label_text,
    set_custom_labels,
)
from xray_curation.services.annotation_store import load_json, save_json_atomic

LABEL_CATALOG_VERSION = 1


def custom_labels_path(dataset_root: str | Path) -> Path:
    return DatasetConfig.from_root(dataset_root).curation_dir / "custom_labels.json"


def normalize_custom_labels(labels: list[Any] | tuple[Any, ...]) -> tuple[str, ...]:
    approved_keys = {label_key(label) for label in APPROVED_FORMAL_LABELS}
    seen = set(approved_keys)
    normalized: list[str] = []
    for label in labels:
        clean = normalize_label_text(str(label))
        key = label_key(clean)
        if not clean or key in seen:
            continue
        normalized.append(clean)
        seen.add(key)
    return tuple(sorted(normalized, key=str.casefold))


def load_custom_labels(dataset_root: str | Path | None) -> tuple[str, ...]:
    if dataset_root is None:
        return set_custom_labels(())
    path = custom_labels_path(dataset_root)
    if not path.exists():
        return set_custom_labels(())
    payload = load_json(path)
    labels = normalize_custom_labels(payload.get("custom_labels", []))
    return set_custom_labels(labels)


def write_custom_labels(dataset_root: str | Path, labels: tuple[str, ...]) -> Path:
    path = custom_labels_path(dataset_root)
    save_json_atomic(
        path,
        {
            "version": LABEL_CATALOG_VERSION,
            "custom_labels": list(normalize_custom_labels(labels)),
        },
    )
    return path


def add_custom_label(dataset_root: str | Path, label: str) -> tuple[tuple[str, ...], bool]:
    existing = load_custom_labels(dataset_root)
    clean = normalize_label_text(label)
    if not clean:
        raise ValueError("Class label cannot be empty.")
    if label_key(clean) in {label_key(item) for item in APPROVED_FORMAL_LABELS}:
        return existing, False
    if label_key(clean) in {label_key(item) for item in existing}:
        return existing, False
    updated = normalize_custom_labels([*existing, clean])
    write_custom_labels(dataset_root, updated)
    set_custom_labels(updated)
    return updated, True


def available_label_choices(dataset_root: str | Path | None = None) -> tuple[str, ...]:
    load_custom_labels(dataset_root)
    return available_labels()
