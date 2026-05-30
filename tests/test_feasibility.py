from datetime import date

from running_coach.feasibility import assess_goal, checkpoint_status

START = date(2026, 5, 30)
RACE = date(2027, 1, 24)


def test_sub2h_from_5k_550_is_aggressive():
    v = assess_goal(1750, 7200, START, RACE)  # 5K 29:10 -> sub-2h
    assert v.verdict == "agressivo"
    assert v.target_pace_per_km == "5:41/km"
    assert v.current_projection_pace == "6:33/km"
    assert 0.01 < v.required_monthly_pct <= 0.02
    assert v.science_refs


def test_already_fit_is_on_track():
    # a 5K of 25:00 already projects under a sub-2h half
    v = assess_goal(1500, 7200, START, RACE)
    assert v.verdict == "no_caminho"


def test_impossible_goal_is_out_of_reach():
    # sub-1:30 half from a 29:10 5K in 8 months is out of reach
    v = assess_goal(1750, 5400, START, RACE)
    assert v.verdict == "fora_de_alcance"


def test_checkpoint_on_track_vs_behind():
    cp = date(2026, 8, 30)
    on = checkpoint_status(1620, 1750, 7200, START, RACE, cp)   # improved
    behind = checkpoint_status(1750, 1750, 7200, START, RACE, cp)  # no gain
    assert on["status"] == "no_caminho"
    assert behind["status"] in {"atras", "fora"}


def test_checkpoint_sharpens_near_race():
    # same 'no gain' reads worse as the race approaches
    aug = checkpoint_status(1750, 1750, 7200, START, RACE, date(2026, 8, 30))["status"]
    nov = checkpoint_status(1750, 1750, 7200, START, RACE, date(2026, 11, 30))["status"]
    assert aug == "atras" and nov == "fora"
