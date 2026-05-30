import csv
from pathlib import Path

from running_coach.pipeline import (
    _execution_signals,
    _parse_target_km,
    _pace_to_sec,
)


def test_parse_target_km_variants():
    assert _parse_target_km("10 km") == 10.0
    assert _parse_target_km("8.5 km") == 8.5
    assert _parse_target_km("30-45 min") is None
    assert _parse_target_km("by_feel") is None
    assert _parse_target_km("") is None


def test_pace_to_sec_variants():
    assert _pace_to_sec("6:15") == 375
    assert _pace_to_sec("easy") is None
    assert _pace_to_sec(None) is None
    assert _pace_to_sec("controlled") is None


class _W:
    def __init__(self, pid, dist, pace):
        self.planned_workout_id = pid
        self.distance_km = dist
        self.avg_pace = pace


def _write_plan(tmp_path: Path, rows):
    p = tmp_path / "data/plan/planned_workouts.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    fields = ["planned_workout_id", "planned_distance_or_duration", "planned_intensity_range"]
    with p.open("w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return tmp_path


def test_no_plan_id_returns_all_false(tmp_path):
    assert _execution_signals(tmp_path, _W(None, 10, "6:00")) == {
        "workout_truncated": False, "overpaced": False, "underpaced": False
    }


def test_unmatched_plan_returns_all_false(tmp_path):
    _write_plan(tmp_path, [{"planned_workout_id": "other", "planned_distance_or_duration": "10 km", "planned_intensity_range": "6:15-6:20/km"}])
    assert _execution_signals(tmp_path, _W("plan-x", 10, "6:00")) == {
        "workout_truncated": False, "overpaced": False, "underpaced": False
    }


def test_truncated_when_executed_far_below_target(tmp_path):
    _write_plan(tmp_path, [{"planned_workout_id": "p", "planned_distance_or_duration": "10 km", "planned_intensity_range": "easy"}])
    assert _execution_signals(tmp_path, _W("p", 5.0, None))["workout_truncated"] is True


def test_pace_within_range_does_not_fire(tmp_path):
    _write_plan(tmp_path, [{"planned_workout_id": "p", "planned_distance_or_duration": "10 km", "planned_intensity_range": "6:15-6:20/km"}])
    s = _execution_signals(tmp_path, _W("p", 10.0, "6:18"))
    assert s["overpaced"] is False and s["underpaced"] is False


def test_overpaced_and_underpaced(tmp_path):
    _write_plan(tmp_path, [{"planned_workout_id": "p", "planned_distance_or_duration": "10 km", "planned_intensity_range": "6:15-6:20/km"}])
    assert _execution_signals(tmp_path, _W("p", 10.0, "5:20"))["overpaced"] is True
    assert _execution_signals(tmp_path, _W("p", 10.0, "7:30"))["underpaced"] is True
