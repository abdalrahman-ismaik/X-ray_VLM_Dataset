from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from xray_curation.services.annotation_store import commit_pending_changes
from xray_curation.services.validation import (
    detect_missing_crops,
    stage_missing_crop_deletions,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Detect missing crops for one selected curation partition."
    )
    parser.add_argument("--dataset", required=True, help="Dataset batch root with curation manifests")
    parser.add_argument("--partition-id", required=True, help="Partition ID, for example part-0001")
    parser.add_argument(
        "--stage",
        action="store_true",
        help="Return staged soft-delete changes for missing crops without saving annotations.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply staged soft-delete changes to annotations.",
    )
    args = parser.parse_args(argv)

    if args.apply:
        stage_result, changes = stage_missing_crop_deletions(args.dataset, args.partition_id)
        commit_result = commit_pending_changes(changes)
        payload = {
            "stage": stage_result.to_dict(),
            "commit": commit_result.to_dict(),
        }
        print(json.dumps(payload, indent=2))
        return 0 if commit_result.success else 1

    if args.stage:
        stage_result, changes = stage_missing_crop_deletions(args.dataset, args.partition_id)
        payload = stage_result.to_dict()
        payload["pending_changes"] = [
            {
                "change_id": change.change_id,
                "target_id": change.target_id,
                "operation": change.operation,
                "payload": change.payload,
            }
            for change in changes
        ]
        print(json.dumps(payload, indent=2))
        return 0 if stage_result.success else 1

    result = detect_missing_crops(args.dataset, args.partition_id)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
