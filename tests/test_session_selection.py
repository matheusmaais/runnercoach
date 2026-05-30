from running_coach.models import Phase
from running_coach.periodization import (
    BRUNA_HALF,
    SessionType,
    generate_volume_plan,
    select_week_sessions,
)

# A representative build week and a deload week from the real generated plan.
PLAN = generate_volume_plan(BRUNA_HALF, weeks=34, baseline_km=20.0)
BUILD_WEEK = next(w for w in PLAN if not w.is_deload and w.week > 4)
DELOAD_WEEK = next(w for w in PLAN if w.is_deload)


def _by_day(sessions):
    return {s.day: s for s in sessions}


def test_long_run_is_always_sunday_with_distance():
    s = _by_day(select_week_sessions(Phase.HALF_BASE, BUILD_WEEK, allow_quality=True))
    assert s["sunday"].session in {SessionType.LONG_EASY, SessionType.LONG_PROGRESSIVE}
    assert s["sunday"].distance_km == BUILD_WEEK.long_km


def test_quality_is_on_tuesday_not_after_volleyball():
    s = _by_day(select_week_sessions(Phase.HALF_BASE, BUILD_WEEK, allow_quality=True))
    assert s["tuesday"].session == SessionType.TEMPO_HMP
    assert s["thursday"].session == SessionType.EASY  # day after Wed volleyball stays easy


def test_base_phase_maintains_velocity_with_one_quality():
    # Base is no longer all-easy: it keeps ONE light interval slot to maintain the
    # velocity/limiar the athletes already built (per real-fitness coaching).
    s = select_week_sessions(Phase.BASE, BUILD_WEEK, allow_quality=True)
    quality = {SessionType.TEMPO_HMP, SessionType.HMP_INTERVALS, SessionType.INTERVALS_5_10K}
    quality_slots = [x for x in s if x.session in quality]
    assert len(quality_slots) == 1
    assert quality_slots[0].session == SessionType.INTERVALS_5_10K
    # easy must still be the MAJORITY (Seiler by session count)
    easy = [x for x in s if x.session in {SessionType.EASY, SessionType.LONG_EASY}]
    assert len(easy) > len(quality_slots)


def test_base_quality_is_gated_off_on_deload_and_when_disabled():
    quality = {SessionType.TEMPO_HMP, SessionType.HMP_INTERVALS, SessionType.INTERVALS_5_10K}
    # safety/adaptive layer disables quality -> base has NO intervals
    s_off = select_week_sessions(Phase.BASE, BUILD_WEEK, allow_quality=False)
    assert all(x.session not in quality for x in s_off)
    # deload week -> no quality either
    s_deload = select_week_sessions(Phase.BASE, DELOAD_WEEK, allow_quality=True)
    assert all(x.session not in quality for x in s_deload)


def test_most_runs_are_easy():
    s = select_week_sessions(Phase.HALF_BASE, BUILD_WEEK, allow_quality=True)
    easy_like = sum(
        x.session in {SessionType.EASY, SessionType.LONG_EASY} for x in s
    )
    assert easy_like >= 2  # at most one quality session in a 3-run week


def test_deload_week_has_no_quality():
    s = select_week_sessions(Phase.HALF_BASE, DELOAD_WEEK, allow_quality=True)
    quality = {SessionType.TEMPO_HMP, SessionType.HMP_INTERVALS, SessionType.INTERVALS_5_10K}
    assert all(x.session not in quality for x in s)


def test_blocked_quality_falls_back_to_easy():
    # allow_quality=False mimics an active reduce/Achilles block from the engine.
    s = _by_day(select_week_sessions(Phase.HALF_BASE, BUILD_WEEK, allow_quality=False))
    assert s["tuesday"].session == SessionType.EASY


def test_half_specific_uses_progressive_long_not_extra_quality():
    s = _by_day(select_week_sessions(Phase.HALF_SPECIFIC, BUILD_WEEK, allow_quality=True))
    assert s["sunday"].session == SessionType.LONG_PROGRESSIVE
    # No separate mid-week HMP interval session: quality lives in the long run.
    assert s["tuesday"].session == SessionType.EASY


def test_taper_keeps_short_intensity():
    s = _by_day(select_week_sessions(Phase.HALF_TAPER, BUILD_WEEK, allow_quality=True))
    assert s["tuesday"].session == SessionType.HMP_INTERVALS


def test_every_session_cites_science():
    for phase in Phase:
        for x in select_week_sessions(phase, BUILD_WEEK, allow_quality=True):
            assert x.science_refs, (phase, x.session)


def test_phase_quality_map_is_exhaustive():
    # Every Phase must be explicitly mapped (no silent all-easy fallback).
    from running_coach.periodization import _PHASE_QUALITY

    assert set(_PHASE_QUALITY) == set(Phase)
