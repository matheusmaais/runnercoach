#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from running_coach.sheets import build_dashboard_workbook


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the running coach dashboard workbook.")
    parser.add_argument("--repo-root", default=REPO_ROOT, type=Path)
    parser.add_argument(
        "--output",
        default=None,
        type=Path,
        help="Workbook path. Defaults to reports/dashboard.xlsx under repo root.",
    )
    args = parser.parse_args()

    output_path = build_dashboard_workbook(args.repo_root, args.output)
    print(f"dashboard_written={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
