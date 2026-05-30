#!/usr/bin/env python3
"""Goal-trajectory simulator: proves the numbers are DYNAMIC and INTERACT.

A trajectory is a fitness curve giving the 5K time at each monthly benchmark.
At each benchmark we recalibrate (zones from the new 5K), re-assess the sub-2h
verdict, and run the checkpoint status against the goal trajectory — showing how
training paces, verdict, and on-track status all move together.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from running_coach.feasibility import assess_goal, checkpoint_status
from running_coach.pacing import HALF_KM, Benchmark, predict_time, zones_from_benchmark

START = date(2026, 5, 30)
RACE = date(2027, 1, 24)
GOAL = 7200          # sub-2h
START_5K = 1750      # 29:10
SUB2_5K = 1521       # 5K equivalent to a sub-2h half (~25:21)

# Monthly benchmark dates (a 5K/10K every ~5 weeks)
BENCHMARKS = [START + timedelta(days=35 * i) for i in range(1, 7)]


def _interp(frac, a, b):
    return int(round(a + (b - a) * frac))


# --- Trajectories: name -> fn(benchmark_index, total) -> 5K seconds ---
def optimistic(i, n):  # steady improvement to exactly sub-2h fitness
    return _interp((i + 1) / n, START_5K, SUB2_5K)


def stalls_short(i, n):  # improves but plateaus above goal (never reaches)
    return _interp(min((i + 1) / n, 0.6), START_5K, SUB2_5K)


def flat_no_gain(i, n):  # no improvement at all
    return START_5K


def behind_then_recover(i, n):  # slow start, then strong second half
    if i < n // 2:
        return _interp((i + 1) / n * 0.4, START_5K, SUB2_5K)  # behind early
    return _interp(min((i + 1) / n * 1.25, 1.0), START_5K, SUB2_5K)  # surges back


def overshoot(i, n):  # exceeds goal fitness (better than needed)
    return _interp(min((i + 1) / n * 1.3, 1.15), START_5K, SUB2_5K)


def regression(i, n):  # gets worse (injury/detraining)
    return _interp((i + 1) / n, START_5K, START_5K + 120)


TRAJECTORIES = {
    "otimista (chega)": optimistic,
    "estagna (nao chega)": stalls_short,
    "sem evolucao": flat_no_gain,
    "atras e recupera": behind_then_recover,
    "supera a meta": overshoot,
    "regride": regression,
}


def run_trajectory(name, fn):
    n = len(BENCHMARKS)
    print(f"\n################ {name} ################")
    print("data       5K     leve  tempo  tiros  projMeia  veredito       marco")
    for i, cp in enumerate(BENCHMARKS):
        t5k = fn(i, n)
        z = zones_from_benchmark(Benchmark(5.0, t5k))
        eq = int(predict_time(t5k, 5.0, 5.0))
        v = assess_goal(eq, GOAL, cp, RACE)
        cs = checkpoint_status(t5k, START_5K, GOAL, START, RACE, cp)
        mm, ss = t5k // 60, t5k % 60
        print(f"{cp}  {mm}:{ss:02d}  {z['long_easy']} {z['tempo_hmp']} {z['intervals_5_10k']} "
              f"{z['half_projection']:<8} {v.verdict:<14} {cs['status']}({cs['gap_pct']:+.0f}%)")
    return z, v


if __name__ == "__main__":
    for name, fn in TRAJECTORIES.items():
        run_trajectory(name, fn)
