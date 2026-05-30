#!/usr/bin/env python3
"""Regenerate the living plan (future rows only) in data/plan/planned_workouts.csv.

Reads the A-race window from cycle.yaml, derives the baseline from processed
workouts, generates the rolling horizon (phase-correct sessions + safe volume),
and merges append-only so past planned rows are never mutated.
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from running_coach.periodization import (  # noqa: E402
    BRUNA_HALF,
    PLANNED_CSV_FIELDS,
    merge_future_only,
    plan_horizon,
    planned_session_to_row,
)


def _race_date(repo_root: Path) -> date:
    cycle = yaml.safe_load((repo_root / "data/plan/cycle.yaml").read_text()) or {}
    window = (cycle.get("target") or {}).get("date_window", "")
    start = window.split("/")[0] if window else "2027-01-24"
    return date.fromisoformat(start)


def _baseline_km(repo_root: Path) -> float:
    path = repo_root / "data/processed/workouts.csv"
    if not path.exists():
        return 20.0
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    # mean weekly running km over the last 4 ISO weeks present in the data
    weekly: dict[str, float] = {}
    for r in rows:
        d = r.get("local_date") or r.get("date")
        if not d or (r.get("activity_type") or "").strip().casefold() != "corrida":
            continue
        try:
            wk = date.fromisoformat(d).isocalendar()
            dist = float(r.get("distance_km") or 0)
        except ValueError:
            continue
        key = f"{wk.year}-{wk.week:02d}"
        weekly[key] = weekly.get(key, 0.0) + dist
    if not weekly:
        return 20.0
    recent = [v for _, v in sorted(weekly.items())[-4:]]
    return max(12.0, round(sum(recent) / len(recent), 1))


def _read_existing(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate the living plan (future rows only).")
    parser.add_argument("--repo-root", default=REPO_ROOT, type=Path)
    parser.add_argument("--today", default=date.today().isoformat())
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    today = date.fromisoformat(args.today)
    race = _race_date(repo_root)
    baseline = _baseline_km(repo_root)

    sessions = plan_horizon(today, race, BRUNA_HALF, baseline_km=baseline)
    new_rows = [planned_session_to_row(s) for s in sessions]

    planned_path = repo_root / "data/plan/planned_workouts.csv"
    merged = merge_future_only(_read_existing(planned_path), new_rows, today)

    with planned_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PLANNED_CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in merged:
            writer.writerow({k: row.get(k, "") for k in PLANNED_CSV_FIELDS})

    print(f"plan_written rows={len(merged)} future={len(new_rows)} baseline_km={baseline} race={race}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
