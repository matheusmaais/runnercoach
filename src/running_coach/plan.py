from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from running_coach.csv_utils import decode_json_cell


def load_planned_workouts(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            row["week_number"] = int(row["week_number"])
            row["allowed_fallbacks"] = decode_json_cell(row["allowed_fallbacks"])
            row["contraindications"] = decode_json_cell(row["contraindications"])
            rows.append(row)
    return rows
