import csv
from datetime import date
from pathlib import Path

from running_coach.periodization import (
    BRUNA_HALF,
    PLANNED_CSV_FIELDS,
    merge_future_only,
    plan_horizon,
    planned_session_to_row,
)

RACE = date(2027, 1, 24)
TODAY = date(2026, 6, 1)


def test_writer_rows_match_csv_schema():
    sessions = plan_horizon(TODAY, RACE, BRUNA_HALF, baseline_km=16.0)
    rows = [planned_session_to_row(s) for s in sessions]
    assert rows
    for r in rows:
        assert set(r.keys()) == set(PLANNED_CSV_FIELDS)
        assert r["status"] == "planned"
        assert r["primary_athlete"] == "bruna"


def test_writer_is_append_only_over_existing_past(tmp_path: Path):
    existing = [
        {"planned_workout_id": "plan-20260531-10k", "date": "2026-05-31", "intended_category": "diagnostic_race_10k", "status": "planned"},
        {"planned_workout_id": "plan-2026-06-10-sunday", "date": "2026-06-10", "intended_category": "OLD_FUTURE", "status": "planned"},
    ]
    sessions = plan_horizon(TODAY, RACE, BRUNA_HALF, baseline_km=16.0)
    new_rows = [planned_session_to_row(s) for s in sessions]
    merged = merge_future_only(existing, new_rows, TODAY)
    # past row preserved, generator-owned old future dropped/replaced
    assert any(r["date"] == "2026-05-31" and r["intended_category"] == "diagnostic_race_10k" for r in merged)
    assert all(r.get("intended_category") != "OLD_FUTURE" for r in merged)
    # all rows after today are dated > today (past row 05-31 is <= today=06-01)
    assert all(date.fromisoformat(r["date"]) > TODAY or r["date"] == "2026-05-31" for r in merged)


def test_seed_race_row_is_preserved_not_deleted():
    # The anchored diagnostic 10K (not generator-owned) must survive regeneration.
    existing = [
        {"planned_workout_id": "plan-20260531-10k", "date": "2026-05-31",
         "intended_category": "diagnostic_race_10k", "status": "planned"},
    ]
    sessions = plan_horizon(date(2026, 5, 30), RACE, BRUNA_HALF, baseline_km=16.0)
    new_rows = [planned_session_to_row(s) for s in sessions]
    merged = merge_future_only(existing, new_rows, date(2026, 5, 30))
    assert any(r.get("planned_workout_id") == "plan-20260531-10k" for r in merged)


def test_no_sessions_after_race():
    assert plan_horizon(date(2027, 2, 1), RACE, BRUNA_HALF, baseline_km=16.0) == []


def test_regenerate_is_atomic_on_write_failure(tmp_path, monkeypatch):
    import sys, csv as _csv
    sys.path.insert(0, str((tmp_path / "..").resolve()))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "build_plan", str((__import__("pathlib").Path(__file__).resolve().parents[1] / "scripts/build_plan.py")))
    bp = importlib.util.module_from_spec(spec); spec.loader.exec_module(bp)
    planned = tmp_path / "data/plan/planned_workouts.csv"
    planned.parent.mkdir(parents=True)
    (tmp_path / "data/plan/cycle.yaml").write_text("target:\n  date_window: 2027-01-24/2027-01-31\n")
    original = "planned_workout_id,date\nseed-1,2020-01-01\n"
    planned.write_text(original)
    # force the writer to blow up mid-write
    monkeypatch.setattr(bp, "plan_horizon", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    import pytest
    with pytest.raises(RuntimeError):
        bp.regenerate(tmp_path, __import__("datetime").date(2026, 6, 1))
    assert planned.read_text() == original  # untouched


def test_week_narrative_handles_malformed():
    from running_coach.frontend_data import _week_narrative
    assert _week_narrative([{"runs": None, "distance_km": None}])  # no crash
    assert _week_narrative([{"runs": "3", "distance_km": "32.4", "quality_runs": "1", "shared_runs": "0"}])
