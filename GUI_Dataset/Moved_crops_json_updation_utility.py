from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from xray_curation.services.crop_manifest import (
    apply_external_moves,
    preview_external_moves,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preview or apply explicit external moved-crop imports for one partition."
    )
    parser.add_argument("--dataset", required=True, help="Dataset batch root with curation manifests")
    parser.add_argument("--partition-id", required=True, help="Partition ID, for example part-0001")
    parser.add_argument(
        "--external-root",
        required=True,
        help="Folder containing explicitly moved crop files grouped by target class folder.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply previewed moves to annotations and the selected partition crop manifest.",
    )
    args = parser.parse_args(argv)

    if args.apply:
        result = apply_external_moves(args.dataset, args.partition_id, args.external_root)
    else:
        result = preview_external_moves(args.dataset, args.partition_id, args.external_root)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
