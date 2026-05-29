from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from running_coach.garmin import GARMIN_ACTIVITY_FIELDS, parse_garmin_csv_text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--garmin", required=True)
    parser.add_argument("--output", default="data/processed/activities.csv")
    args = parser.parse_args()

    source = Path(args.garmin)
    rows = parse_garmin_csv_text(
        source.read_text(encoding="utf-8-sig"), source_file=source.name
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=GARMIN_ACTIVITY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
