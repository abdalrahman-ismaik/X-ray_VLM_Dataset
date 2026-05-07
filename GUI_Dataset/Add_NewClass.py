from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from xray_curation.gui.app import run_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Launch the refactored X-ray dataset curation GUI."
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help="Optional dataset root, for example C:/path/to/dataset.",
    )
    args = parser.parse_args(argv)
    run_app(args.dataset)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
