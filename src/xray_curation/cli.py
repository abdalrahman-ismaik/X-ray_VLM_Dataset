from __future__ import annotations

import argparse
import json
from pathlib import Path

from xray_curation.config import DEFAULT_PARTITION_SIZE, default_dataset_root
from xray_curation.services.crop_generator import generate_crops_for_partition
from xray_curation.services.dataset_index import build_dataset_manifest


def _dataset_arg(value: str | None) -> Path:
    return Path(value) if value else default_dataset_root()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="xray-curation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    gui_parser = subparsers.add_parser("gui", help="Launch the desktop curation GUI")
    gui_parser.add_argument("--dataset", default=None)

    index_parser = subparsers.add_parser("index", help="Create partition manifests")
    index_parser.add_argument("--dataset", default=None)
    index_parser.add_argument("--partition-size", type=int, default=DEFAULT_PARTITION_SIZE)

    crops_parser = subparsers.add_parser("generate-crops", help="Generate crops for one partition")
    crops_parser.add_argument("--dataset", default=None)
    crops_parser.add_argument("--partition-id", required=True)
    crops_parser.add_argument("--partition-size", type=int, default=DEFAULT_PARTITION_SIZE)
    crops_parser.add_argument("--overwrite", action="store_true")
    crops_parser.add_argument("--padding", type=int, default=0)

    args = parser.parse_args(argv)
    dataset = _dataset_arg(getattr(args, "dataset", None))

    if args.command == "gui":
        from xray_curation.gui.app import run_app

        run_app(dataset)
        return 0

    if args.command == "index":
        manifest = build_dataset_manifest(
            dataset,
            partition_size=args.partition_size,
            persist=True,
        )
        print(
            json.dumps(
                {
                    "dataset_root": manifest["dataset_root"],
                    "partition_size": manifest["partition_size"],
                    "image_count": manifest["image_count"],
                    "partitions": manifest["partitions"],
                },
                indent=2,
            )
        )
        return 0

    if args.command == "generate-crops":
        result = generate_crops_for_partition(
            dataset,
            partition_id=args.partition_id,
            partition_size=args.partition_size,
            overwrite=args.overwrite,
            padding=args.padding,
        )
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.success else 1

    parser.error(f"Unsupported command: {args.command}")
    return 2
