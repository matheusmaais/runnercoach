"""Lock the dynamic goal-trajectory behavior: zones, verdict, and checkpoint
status must all move together as fitness changes across the cycle."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from sim_goal_trajectories import (  # noqa: E402
    GOAL, RACE, START, START_5K, TRAJECTORIES, run_trajectory,
)

from running_coach.feasibility import assess_goal, checkpoint_status  # noqa: E402
from running_coach.pacing import Benchmark, predict_time, zones_from_benchmark  # noqa: E402


def _pace_sec(s):
    mm, ss = s.replace("/km", "").split(":")
    return int(mm) * 60 + int(ss)


def test_faster_5k_tightens_all_zones_and_moves_verdict():
    slow = zones_from_benchmark(Benchmark(5.0, 1750))   # 29:10
    fast = zones_from_benchmark(Benchmark(5.0, 1521))   # 25:21 (sub-2h fitness)
    for k in ("long_easy", "tempo_hmp", "intervals_5_10k", "half_projection"):
        assert _pace_sec(fast[k]) < _pace_sec(slow[k]), k  # every zone faster
    eq_slow = int(predict_time(1750, 5.0, 5.0))
    eq_fast = int(predict_time(1521, 5.0, 5.0))
    assert assess_goal(eq_slow, GOAL, START, RACE).verdict == "agressivo"
    assert assess_goal(eq_fast, GOAL, START, RACE).verdict == "no_caminho"


def test_optimistic_reaches_goal_by_race():
    z, v = run_trajectory("otimista", TRAJECTORIES["otimista (chega)"])
    assert v.verdict == "no_caminho"


def test_stall_flips_to_out_of_reach_late():
    z, v = run_trajectory("estagna", TRAJECTORIES["estagna (nao chega)"])
    assert v.verdict == "fora_de_alcance"


def test_no_gain_stays_out_of_reach_and_checkpoint_degrades():
    fn = TRAJECTORIES["sem evolucao"]
    # checkpoint gap must worsen monotonically as the race approaches
    cps = [date(2026, 7, 4), date(2026, 9, 12), date(2026, 11, 21)]
    gaps = [checkpoint_status(fn(i, 6), START_5K, GOAL, START, RACE, cp)["gap_pct"]
            for i, cp in enumerate(cps)]
    assert gaps == sorted(gaps) and gaps[-1] > gaps[0]


def test_behind_then_recover_reopens_goal():
    fn = TRAJECTORIES["atras e recupera"]
    early = assess_goal(int(predict_time(fn(1, 6), 5.0, 5.0)), GOAL, date(2026, 8, 8), RACE)
    late = assess_goal(int(predict_time(fn(4, 6), 5.0, 5.0)), GOAL, date(2026, 11, 21), RACE)
    assert early.verdict == "fora_de_alcance"   # behind mid-cycle
    assert late.verdict == "no_caminho"          # recovered -> goal reopens


def test_regression_slows_paces_and_stays_out():
    fn = TRAJECTORIES["regride"]
    z_early = zones_from_benchmark(Benchmark(5.0, fn(0, 6)))
    z_late = zones_from_benchmark(Benchmark(5.0, fn(5, 6)))
    assert _pace_sec(z_late["tempo_hmp"]) > _pace_sec(z_early["tempo_hmp"])  # slower
    v = assess_goal(int(predict_time(fn(5, 6), 5.0, 5.0)), GOAL, date(2026, 12, 26), RACE)
    assert v.verdict == "fora_de_alcance"
