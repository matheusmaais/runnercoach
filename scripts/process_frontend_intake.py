#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from running_coach.operational import process_frontend_intake  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Process a GitHub Pages frontend intake file.")
    parser.add_argument("intake_path", type=Path)
    parser.add_argument("--repo-root", default=REPO_ROOT, type=Path)
    args = parser.parse_args()

    result = process_frontend_intake(args.repo_root, args.intake_path)
    if result.checkin_path:
        print(f"checkin_path={result.checkin_path}")
    if result.garmin_csv_path:
        print(f"garmin_csv_path={result.garmin_csv_path}")
    print(f"run_llm={str(result.run_llm).lower()}")
    print(f"commit_results={str(result.commit_results).lower()}")


if __name__ == "__main__":
    main()
