from datetime import date

from running_coach.models import Phase
from running_coach.periodization import (
    BRUNA_HALF,
    SessionType,
    derive_phase_schedule,
    merge_future_only,
    plan_horizon,
)

TODAY = date(2026, 6, 1)
RACE = date(2027, 1, 24)


def test_phase_schedule_reverse_anchored_taper_abuts_race():
    blocks = derive_phase_schedule(TODAY, RACE)
    assert blocks[0].start <= TODAY <= blocks[0].end
    assert blocks[-1].phase == Phase.HALF_TAPER
    # Taper ends on/just after race week; specific work precedes it.
    assert blocks[-1].end >= RACE - __import__("datetime").timedelta(days=7)
    phases = [b.phase for b in blocks]
    # half_specific comes right before taper
    assert phases[-2] == Phase.HALF_SPECIFIC


def test_phase_schedule_truncates_when_time_is_short():
    # 4 weeks out: must still taper + do specific work, dropping early phases.
    short = derive_phase_schedule(date(2026, 12, 27), RACE)
    assert short[-1].phase == Phase.HALF_TAPER
    assert sum(b.weeks for b in short) >= 1
    assert Phase.BASE not in [b.phase for b in short]


def test_horizon_is_future_only():
    sessions = plan_horizon(TODAY, RACE, BRUNA_HALF, baseline_km=20.0)
    assert sessions
    assert all(s.date > TODAY for s in sessions)


def test_horizon_sessions_are_phase_correct():
    sessions = plan_horizon(TODAY, RACE, BRUNA_HALF, baseline_km=20.0, horizon_weeks=8)
    # Early weeks are BASE -> all easy/long, no quality intervals.
    quality = {SessionType.TEMPO_HMP, SessionType.HMP_INTERVALS, SessionType.INTERVALS_5_10K}
    base_sessions = [s for s in sessions if s.phase == Phase.BASE]
    assert base_sessions
    assert all(s.session not in quality for s in base_sessions)
    # Sundays are long runs with a distance.
    sundays = [s for s in sessions if s.day == "sunday"]
    assert sundays and all(s.distance_km is not None for s in sundays)


def test_horizon_blocks_quality_when_disabled():
    sessions = plan_horizon(
        TODAY, RACE, BRUNA_HALF, baseline_km=20.0, allow_quality=False
    )
    quality = {SessionType.TEMPO_HMP, SessionType.HMP_INTERVALS, SessionType.INTERVALS_5_10K}
    assert all(s.session not in quality for s in sessions)


def test_merge_future_only_preserves_past_byte_identical():
    existing = [
        {"planned_workout_id": "plan-20260528-x", "date": "2026-05-28", "intended_category": "diagnostic_race_10k"},
        {"planned_workout_id": "plan-2026-06-10-sunday", "date": "2026-06-10", "intended_category": "OLD_FUTURE"},
    ]
    new_future = [
        {"planned_workout_id": "plan-2026-06-10-sunday", "date": "2026-06-10", "intended_category": "NEW"},
        {"planned_workout_id": "plan-2026-05-20-x", "date": "2026-05-20", "intended_category": "SHOULD_BE_IGNORED"},
    ]
    merged = merge_future_only(existing, new_future, TODAY)
    # Past row preserved exactly; generator-owned future replaced; injected past ignored.
    assert any(r["date"] == "2026-05-28" and r["intended_category"] == "diagnostic_race_10k" for r in merged)
    assert any(r["date"] == "2026-06-10" and r["intended_category"] == "NEW" for r in merged)
    assert all(r.get("intended_category") != "OLD_FUTURE" for r in merged)
    assert all(r.get("intended_category") != "SHOULD_BE_IGNORED" for r in merged)


def test_plan_horizon_deterministic():
    a = plan_horizon(TODAY, RACE, BRUNA_HALF, baseline_km=20.0)
    b = plan_horizon(TODAY, RACE, BRUNA_HALF, baseline_km=20.0)
    assert a == b


# --- Codex living-plan review regressions ---

def test_short_schedule_keeps_specific_and_taper():
    # 4 weeks out: must keep BOTH half_specific and taper (drop early phases).
    blocks = derive_phase_schedule(date(2026, 12, 27), RACE)
    phases = [b.phase for b in blocks]
    assert Phase.HALF_TAPER in phases
    assert Phase.HALF_SPECIFIC in phases


def test_race_day_is_not_a_generated_session():
    sessions = plan_horizon(date(2027, 1, 18), RACE, BRUNA_HALF, baseline_km=30.0)
    assert all(s.date != RACE for s in sessions)


def test_merge_future_only_returns_immutable_snapshot():
    existing = [{"date": "2026-05-28", "nested": {"x": 1}}]
    merged = merge_future_only(existing, [], TODAY)
    existing[0]["nested"]["x"] = 99
    assert merged[0]["nested"]["x"] == 1
