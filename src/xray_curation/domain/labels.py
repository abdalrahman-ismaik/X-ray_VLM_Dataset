from __future__ import annotations

APPROVED_PIDRAY_LABELS: tuple[str, ...] = (
    "Backpack",
    "Belt",
    "Box",
    "Cable",
    "Can",
    "Clips",
    "Coins",
    "Electrical Device",
    "Electronic Device",
    "Glass Bottle",
    "Handbag",
    "Headset",
    "Insulated Bottle",
    "Ipad",
    "Jar",
    "Keyboard",
    "Keys",
    "Laptop",
    "Laptop Charger",
    "Laptop Power Adapter",
    "Lighter",
    "Mobile Phone",
    "Nail Cutter",
    "Plastic Bottle",
    "Plastic Tray",
    "Power Bank",
    "Screwdriver",
    "Spoon",
    "Suitcase",
    "Sunglasses",
    "Thick Cables",
    "Umbrella",
    "Wallet",
    "Watch",
)

APPROVED_SIXRAY_LABELS: tuple[str, ...] = (
    "Gun",
    "Knife",
    "Wrench",
    "Pliers",
    "Scissors",
    "Hammer",
)

APPROVED_FORMAL_LABELS: tuple[str, ...] = tuple(
    dict.fromkeys((*APPROVED_PIDRAY_LABELS, *APPROVED_SIXRAY_LABELS))
)

LEGACY_LABEL_ALIASES: dict[str, str] = {
    label.replace(" ", "_"): label for label in APPROVED_FORMAL_LABELS
}


def label_key(label: str) -> str:
    return " ".join(label.replace("_", " ").split()).casefold()


_LABEL_LOOKUP: dict[str, str] = {}
for _label in APPROVED_FORMAL_LABELS:
    _LABEL_LOOKUP[label_key(_label)] = _label
    _LABEL_LOOKUP[label_key(_label.replace(" ", "_"))] = _label
for _alias, _target in LEGACY_LABEL_ALIASES.items():
    _LABEL_LOOKUP[label_key(_alias)] = _target

APPROVED_PIDRAY_LABEL_SET = frozenset(APPROVED_PIDRAY_LABELS)
APPROVED_SIXRAY_LABEL_SET = frozenset(APPROVED_SIXRAY_LABELS)
APPROVED_FORMAL_LABEL_SET = frozenset(APPROVED_FORMAL_LABELS)
CUSTOM_LABELS: tuple[str, ...] = ()
CUSTOM_LABEL_SET = frozenset()


def normalize_label_text(label: str) -> str:
    return " ".join(label.replace("_", " ").split())


def set_custom_labels(labels: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    global CUSTOM_LABELS, CUSTOM_LABEL_SET
    normalized: list[str] = []
    seen = set(_LABEL_LOOKUP)
    for label in labels:
        clean = normalize_label_text(str(label))
        key = label_key(clean)
        if not clean or key in seen:
            continue
        normalized.append(clean)
        seen.add(key)
    CUSTOM_LABELS = tuple(sorted(normalized, key=str.casefold))
    CUSTOM_LABEL_SET = frozenset(CUSTOM_LABELS)
    return CUSTOM_LABELS


def available_labels() -> tuple[str, ...]:
    return (*APPROVED_FORMAL_LABELS, *CUSTOM_LABELS)


def canonical_label(label: str) -> str | None:
    return _LABEL_LOOKUP.get(label_key(label))


def is_approved_label(label: str) -> bool:
    return label in APPROVED_FORMAL_LABEL_SET or label in CUSTOM_LABEL_SET


def label_requires_standardization(label: str) -> bool:
    canonical = canonical_label(label)
    return canonical is not None and canonical != label
