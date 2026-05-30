from datetime import date, timedelta

from running_coach.accumulation import WorkoutHistoryPoint, build_athlete_state
from running_coach.models import RecommendationAction, SymptomSeverity
from running_coach.recommendations import RecommendationInput, recommend_next_action

REF = date(2026, 8, 1)


def _pt(d, km, *, race=False, ach=0):
    return WorkoutHistoryPoint(
        local_date=d,
        distance_km=km,
        is_running=True,
        bruna_pse=6,
        matheus_achilles_morning=0,
        matheus_achilles_after=ach,
        poor_sleep=False,
        all_out_race=race,
    )


def _history(weekly_km_by_week):
    # weekly_km_by_week: list of (weeks_ago, total_km); split into 2 runs per week
    # so the prior 28-day window has real weekly coverage (>=3 weeks).
    pts = []
    for weeks_ago, km in weekly_km_by_week:
        d = REF - timedelta(days=7 * weeks_ago)
        pts.append(_pt(d, km / 2))
        pts.append(_pt(d + timedelta(days=2), km / 2))
    return pts


def _input(accumulated):
    return RecommendationInput(
        bruna_pse=6,
        symptom_severity=SymptomSeverity.NONE,
        matheus_achilles_morning=0,
        matheus_achilles_after=0,
        volleyball_previous_day=False,
        poor_sleep=False,
        all_out_race=False,
        planned_action=RecommendationAction.MAINTAIN_NEXT_WORKOUT,
        phase="half_base",
        week_number=5,
        planned_workout_id="plan-5",
        accumulated=accumulated,
    )


def test_adaptation_heavy_vs_light_week_differ():
    # Light: steady ~10km/week -> no spike. Heavy: last 7d spikes vs prior weeks.
    light = build_athlete_state(
        _history([(1, 10), (2, 10), (3, 10), (4, 10), (5, 10)]), REF
    )
    heavy = build_athlete_state(
        _history([(1, 45), (2, 12), (3, 12), (4, 12), (5, 12)]), REF
    )

    light_action = recommend_next_action(_input(light)).action
    heavy_result = recommend_next_action(_input(heavy))

    assert light_action == RecommendationAction.MAINTAIN_NEXT_WORKOUT
    assert heavy_result.action == RecommendationAction.REDUCE_NEXT_WORKOUT
    assert "weekly_load_spike" in heavy_result.reasons
    assert "load-management-recovery" in heavy_result.science_refs


def test_accumulated_never_raises_a_more_conservative_planned_action():
    # Codex #1: a load spike must NOT downgrade an already-conservative plan.
    heavy = build_athlete_state(
        _history([(1, 45), (2, 12), (3, 12), (4, 12), (5, 12)]), REF
    )
    inp = _input(heavy)
    inp = inp.model_copy(update={"planned_action": RecommendationAction.REPLACE_WITH_OFF})
    assert recommend_next_action(inp).action == RecommendationAction.REPLACE_WITH_OFF


def test_sparse_prior_history_does_not_fake_a_spike():
    # Codex #2: one old run + a recent block must NOT compute a load ratio.
    pts = [_pt(REF - timedelta(days=30), 10)]
    pts += [_pt(REF - timedelta(days=2), 13)]
    state = build_athlete_state(pts, REF)
    assert state.load_ratio is None
    assert state.weekly_load_spike is False


def test_achilles_trend_needs_three_distinct_dates():
    # Codex #3: two points (even rising) must not declare a trend.
    two = [
        _pt(REF - timedelta(days=27), 10, ach=1),
        _pt(REF - timedelta(days=3), 10, ach=3),
    ]
    assert build_athlete_state(two, REF).achilles_is_rising is False
    three = [
        _pt(REF - timedelta(days=20), 10, ach=1),
        _pt(REF - timedelta(days=12), 10, ach=2),
        _pt(REF - timedelta(days=4), 10, ach=3),
    ]
    assert build_athlete_state(three, REF).achilles_is_rising is True


def test_backward_compatible_no_accumulated():
    # Without accumulated state, behaviour is unchanged (maintain on clean input).
    assert recommend_next_action(_input(None)).action == RecommendationAction.MAINTAIN_NEXT_WORKOUT


def test_post_race_recovery_lowers_envelope():
    pts = _history([(2, 12), (3, 12), (4, 12), (5, 12)])
    pts.append(_pt(REF - timedelta(days=3), 10, race=True))
    state = build_athlete_state(pts, REF)
    assert state.in_post_race_recovery is True
    result = recommend_next_action(_input(state))
    assert result.action == RecommendationAction.REDUCE_NEXT_WORKOUT


def test_insufficient_history_no_spike_but_no_crash():
    state = build_athlete_state(_history([(1, 40)]), REF)
    assert state.insufficient_history is True
    assert state.load_ratio is None
    # Must not fabricate a spike from one week of data.
    assert recommend_next_action(_input(state)).action == RecommendationAction.MAINTAIN_NEXT_WORKOUT


def test_empty_history_is_insufficient():
    state = build_athlete_state([], REF)
    assert state.insufficient_history is True
    assert state.load_ratio is None


def test_insufficient_history_is_not_high_confidence():
    state = build_athlete_state([], REF)
    res = recommend_next_action(_input(state))
    # Maintain is acceptable on week 1, but confidence must not be HIGH (fail-closed).
    assert res.confidence.value != "high"
    assert "insufficient_history" in res.reasons


def test_oversized_plan_cannot_suppress_real_overload():
    from running_coach.accumulation import AccumulatedState
    # prior 20, last 40, aspirational plan 80 -> must STILL be a spike (capped).
    s = AccumulatedState(
        last_7d_distance_km=40.0, prior_28d_mean_7d_distance_km=20.0, load_ratio=2.0,
        achilles_recent_max=0, achilles_is_rising=False, days_since_all_out_race=None,
        in_post_race_recovery=False, history_days=40, insufficient_history=False,
        planned_week_km=80.0,
    )
    assert s.weekly_load_spike is True


def test_moderate_planned_progression_not_flagged():
    from running_coach.accumulation import AccumulatedState
    # prior 30, planned 33 (~10% ramp), ran 33 -> not a spike.
    s = AccumulatedState(
        last_7d_distance_km=33.0, prior_28d_mean_7d_distance_km=30.0, load_ratio=1.1,
        achilles_recent_max=0, achilles_is_rising=False, days_since_all_out_race=None,
        in_post_race_recovery=False, history_days=40, insufficient_history=False,
        planned_week_km=33.0,
    )
    assert s.weekly_load_spike is False
