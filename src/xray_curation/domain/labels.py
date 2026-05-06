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

LEGACY_LABEL_ALIASES: dict[str, str] = {
    label.replace(" ", "_"): label for label in APPROVED_PIDRAY_LABELS
}


def label_key(label: str) -> str:
    return " ".join(label.replace("_", " ").split()).casefold()


_LABEL_LOOKUP: dict[str, str] = {}
for _label in APPROVED_PIDRAY_LABELS:
    _LABEL_LOOKUP[label_key(_label)] = _label
    _LABEL_LOOKUP[label_key(_label.replace(" ", "_"))] = _label
for _alias, _target in LEGACY_LABEL_ALIASES.items():
    _LABEL_LOOKUP[label_key(_alias)] = _target

APPROVED_PIDRAY_LABEL_SET = frozenset(APPROVED_PIDRAY_LABELS)


def normalize_label_text(label: str) -> str:
    return " ".join(label.replace("_", " ").split())


def canonical_label(label: str) -> str | None:
    return _LABEL_LOOKUP.get(label_key(label))


def is_approved_label(label: str) -> bool:
    return label in APPROVED_PIDRAY_LABEL_SET


def label_requires_standardization(label: str) -> bool:
    canonical = canonical_label(label)
    return canonical is not None and canonical != label
