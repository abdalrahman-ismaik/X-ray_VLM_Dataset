from __future__ import annotations

import argparse
from pathlib import Path

from xray_curation.gui.app import run_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compatibility launcher for the refactored X-ray dataset curation GUI. "
            "The legacy monolithic reviewProposals GUI is preserved only in project "
            "history; active review and annotation workflows live under "
            "src/xray_curation/gui and services."
        )
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help="Optional dataset root containing images/ and json/.",
    )
    args = parser.parse_args(argv)
    run_app(Path(args.dataset) if args.dataset else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
