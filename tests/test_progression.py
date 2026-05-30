from running_coach.accumulation import AccumulatedState
from running_coach.progression import suggest_fourth_day, MIN_GREEN_WEEKS


def _state(**kw):
    base = dict(last_7d_distance_km=24.0, prior_28d_mean_7d_distance_km=24.0,
                load_ratio=1.0, achilles_recent_max=0, achilles_is_rising=False,
                days_since_all_out_race=None, in_post_race_recovery=False,
                history_days=40, insufficient_history=False)
    base.update(kw)
    return AccumulatedState(**base)


def test_suggests_when_sustained_green():
    s = suggest_fourth_day(_state(), run_days_per_week=3, consecutive_green_weeks=MIN_GREEN_WEEKS)
    assert s.should_suggest and "4º dia" in s.message and s.science_refs


def test_no_suggest_when_not_enough_green_weeks():
    assert not suggest_fourth_day(_state(), 3, MIN_GREEN_WEEKS - 1).should_suggest


def test_no_suggest_when_achilles_or_spike_or_ramping():
    assert not suggest_fourth_day(_state(achilles_recent_max=4), 3, 8).should_suggest
    assert not suggest_fourth_day(_state(achilles_is_rising=True), 3, 8).should_suggest
    assert not suggest_fourth_day(_state(load_ratio=1.3), 3, 8).should_suggest
    assert not suggest_fourth_day(_state(in_post_race_recovery=True), 3, 8).should_suggest
    assert not suggest_fourth_day(_state(insufficient_history=True), 3, 8).should_suggest


def test_no_suggest_when_already_four_days():
    assert not suggest_fourth_day(_state(), run_days_per_week=4, consecutive_green_weeks=8).should_suggest


def test_adapter_blocks_on_unsorted_latest_bad_week():
    from running_coach.frontend_data import _progression_suggestion
    from datetime import date, timedelta
    today = date.today()
    rows = [{"local_date": (today - timedelta(days=3 * i)).isoformat(),
             "activity_type": "corrida", "distance_km": "8", "bruna_pse": "6",
             "matheus_achilles_after": "0", "matheus_achilles_morning": "0"} for i in range(8)]
    # latest day has PSE 8 -> must reset streak even though placed first (unsorted)
    rows[0] = {**rows[0], "local_date": today.isoformat(), "bruna_pse": "8"}
    import random
    random.shuffle(rows)
    assert _progression_suggestion(rows)["should_suggest"] is False


def test_adapter_fails_closed_on_missing_evidence():
    from running_coach.frontend_data import _progression_suggestion
    from datetime import date, timedelta
    today = date.today()
    rows = [{"local_date": (today - timedelta(days=3 * i)).isoformat(),
             "activity_type": "corrida", "distance_km": "8"} for i in range(8)]  # no PSE/Achilles
    assert _progression_suggestion(rows)["should_suggest"] is False


def test_recommendation_input_rejects_progression_field():
    import pytest
    from running_coach.models import RecommendationAction, SymptomSeverity
    from running_coach.recommendations import RecommendationInput
    with pytest.raises(Exception):
        RecommendationInput(
            bruna_pse=6, symptom_severity=SymptomSeverity.NONE,
            matheus_achilles_morning=0, matheus_achilles_after=0,
            volleyball_previous_day=False, poor_sleep=False, all_out_race=False,
            planned_action=RecommendationAction.MAINTAIN_NEXT_WORKOUT,
            phase="base", week_number=1, planned_workout_id="w1",
            progression_suggestion=True)  # type: ignore[call-arg]
