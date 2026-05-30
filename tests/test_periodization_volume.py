from running_coach.periodization import (
    BRUNA_HALF,
    LOAD_RATIO_CAP,
    generate_volume_plan,
)

LOAD_ABS_FLOOR_KM = 5.0  # spike requires BOTH ratio>cap AND abs jump>floor (v1.7 3.4)


def _plan():
    return generate_volume_plan(BRUNA_HALF, weeks=34, baseline_km=20.0)


def test_share_never_exceeds_cap():
    for w in _plan():
        assert w.long_share <= BRUNA_HALF.share_cap + 1e-9, (w.week, w.long_share)


def test_volume_never_exceeds_ceiling():
    for w in _plan():
        assert w.weekly_km <= BRUNA_HALF.volume_ceiling_km + 1e-9, (w.week, w.weekly_km)


def test_no_weekly_load_spike_vs_rolling_mean():
    # Replays the exact guardrail: spike iff ratio>cap AND abs jump>floor.
    plan = _plan()
    chronic = [20.0] * 4
    for w in plan:
        mean = sum(chronic[-4:]) / 4
        ratio = w.weekly_km / mean
        spike = (ratio > LOAD_RATIO_CAP + 1e-9) and (w.weekly_km - mean > LOAD_ABS_FLOOR_KM)
        assert not spike, (w.week, round(ratio, 3), round(w.weekly_km - mean, 2))
        chronic.append(w.weekly_km)


def test_long_run_reaches_half_specific_endurance():
    peak = max(w.long_peak_km for w in _plan())
    assert peak >= 18.0, peak


def test_long_peak_is_monotonic():
    plan = _plan()
    peaks = [w.long_peak_km for w in plan]
    assert peaks == sorted(peaks), peaks


def test_deload_every_fourth_week_reduces_volume():
    plan = _plan()
    for w in plan:
        if w.is_deload:
            assert w.week % 4 == 0
            # deload volume is clearly below the build peak around it
            assert w.weekly_km < BRUNA_HALF.volume_ceiling_km


def test_golden_anchor_points():
    # Pin a few representative weeks so an accidental model change is caught.
    plan = {w.week: w for w in _plan()}
    assert plan[1].weekly_km == 22.5 and plan[1].long_km == 10.0
    assert plan[27].long_peak_km >= 18.0
    assert plan[27].weekly_km == BRUNA_HALF.volume_ceiling_km
    assert plan[32].is_deload is True


# --- Codex adversarial review regressions: input-domain validation ---

import pytest

from running_coach.periodization import VolumePlanParams


def test_baseline_above_ceiling_raises():
    with pytest.raises(ValueError):
        generate_volume_plan(BRUNA_HALF, weeks=4, baseline_km=43.0)


def test_nonpositive_baseline_raises():
    with pytest.raises(ValueError):
        generate_volume_plan(BRUNA_HALF, weeks=4, baseline_km=-5.0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"share_cap": -0.1},
        {"share_cap": 1.5},
        {"abs_step_km": 0.0},
        {"volume_ceiling_km": 0.0},
        {"runs_per_week": 0},
    ],
)
def test_degenerate_params_raise(kwargs):
    base = dict(runs_per_week=4, share_cap=0.45, volume_ceiling_km=42.0, abs_step_km=2.5)
    base.update(kwargs)
    with pytest.raises(ValueError):
        VolumePlanParams(**base)


def test_weeks_zero_returns_empty():
    assert generate_volume_plan(BRUNA_HALF, weeks=0, baseline_km=20.0) == []
