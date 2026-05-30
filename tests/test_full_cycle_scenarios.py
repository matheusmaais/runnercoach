"""Permanent lock for the 26 full-cycle scenarios (real engine to the Jan race).
Guards the coaching invariants against regression: progression/specificity,
taper reduction, fail-closed safety, and post-injury resumption."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from sim_harness import run_cycle  # noqa: E402
from sim_scenarios import (  # noqa: E402
    SCENARIOS,
    achilles_then_recover,
    check_invariants,
    illness_sustained,
    red_flag_once,
)

from running_coach.models import Phase  # noqa: E402


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_scenario_invariants_hold(name):
    res = run_cycle(SCENARIOS[name])
    ok, notes = check_invariants(name, res)
    assert ok, f"{name}: {notes}"


def test_every_scenario_reaches_race_with_full_specificity():
    for name, fb in SCENARIOS.items():
        res = run_cycle(fb)
        phases = {w.phase for w in res.weeks}
        assert Phase.HALF_SPECIFIC in phases and Phase.HALF_TAPER in phases, name


def test_red_flag_forces_off_then_resumes():
    res = run_cycle(red_flag_once)
    s21 = next(w for w in res.weeks if w.week_number == 21)
    s22 = next(w for w in res.weeks if w.week_number == 22)
    assert s21.action == "replace_with_off" and s21.reason == "red_flag_symptom"
    assert s22.action == "maintain_next_workout"


def test_sustained_illness_pulls_back_then_resumes():
    res = run_cycle(illness_sustained)
    for wk in (9, 10, 11):
        w = next(x for x in res.weeks if x.week_number == wk)
        assert w.action == "replace_with_easy" and w.reason == "bruna_pse_ge_9"
    s12 = next(w for w in res.weeks if w.week_number == 12)
    assert s12.action == "maintain_next_workout"


def test_post_injury_long_run_keeps_progressing():
    res = run_cycle(achilles_then_recover)
    # after the Achilles block, the long run must keep climbing (no permanent stall)
    longs_after = [w.long_km for w in res.weeks if 13 <= w.index <= 18]
    assert max(longs_after) > min(longs_after)


def test_taper_always_reduces_below_peak():
    for name, fb in SCENARIOS.items():
        res = run_cycle(fb)
        longs = [w.long_km for w in res.weeks]
        peak = max(longs)
        taper = [w.long_km for w in res.weeks if w.phase == Phase.HALF_TAPER]
        assert taper and max(taper) < peak, name


def test_interruptions_reduce_executed_load():
    """Faithful simulation: declining/interrupted cycles must accumulate LESS
    executed long-run load than a perfect cycle (proves feedback actually bites)."""
    from sim_harness import _executed_km
    from sim_scenarios import inverted_u, one_big_skip_block, perfect

    def total(fb):
        return sum(_executed_km(w.action, w.long_km) for w in run_cycle(fb).weeks if not w.skipped)

    base = total(perfect)
    assert total(inverted_u) < base      # sustained decline -> much less load
    assert total(one_big_skip_block) < base  # 3 weeks off -> less load


def test_expected_triggers_are_not_vacuous():
    """Each safety scenario must actually exercise its intended trigger."""
    from sim_scenarios import _EXPECTED_TRIGGER

    for name, expected in _EXPECTED_TRIGGER.items():
        res = run_cycle(SCENARIOS[name])
        seen = {w.action for w in res.weeks} | {w.reason for w in res.weeks}
        assert expected in seen, f"{name}: trigger {expected} never fired"
