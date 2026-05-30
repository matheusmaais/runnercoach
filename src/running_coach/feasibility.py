"""Goal feasibility methodology — turns a time goal (e.g. sub-2h half) into an
objective, checkpoint-based verdict instead of vibes.

Two questions answered deterministically:
1. Is the goal realistic from TODAY? -> required monthly pace improvement vs
   evidence-based ceilings for a consistent recreational runner.
2. Are we ON TRACK at each checkpoint? -> a benchmark race must hit the pace the
   goal-trajectory predicts for that date (within tolerance).

Ceilings (sec/km improvement as % of current pace, per month):
- REALISTIC_CEILING 1.0%/mo: typical sustained improvement.
- AGGRESSIVE_CEILING 2.0%/mo: upper bound, everything going right.
Above the aggressive ceiling -> out of reach. Pure, deterministic, cited
(training-consistency-principle, riegel-race-prediction).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from running_coach.pacing import HALF_KM, RIEGEL_EXPONENT, _fmt, predict_time

REALISTIC_CEILING = 0.010   # 1.0%/month pace improvement
AGGRESSIVE_CEILING = 0.020  # 2.0%/month
ON_TRACK_TOLERANCE = 0.03   # checkpoint pace within 3% of predicted trajectory
_MONTH_DAYS = 30.44


@dataclass(frozen=True)
class FeasibilityVerdict:
    verdict: str                 # "no_caminho" | "agressivo" | "fora_de_alcance"
    required_monthly_pct: float  # required monthly improvement
    target_pace_per_km: str      # PT-BR pace string for the goal
    current_projection_pace: str
    message: str                 # PT-BR coach explanation
    science_refs: tuple[str, ...]


def _race_pace_for_half_goal(goal_seconds: int) -> float:
    return goal_seconds / HALF_KM


def assess_goal(
    current_5k_seconds: int,
    goal_half_seconds: int,
    today: date,
    race_date: date,
) -> FeasibilityVerdict:
    """Judge a half-marathon time goal from the current 5K fitness."""
    cur_half = predict_time(current_5k_seconds, 5.0, HALF_KM) / HALF_KM
    tgt = _race_pace_for_half_goal(goal_half_seconds)
    months = max((race_date - today).days / _MONTH_DAYS, 0.1)
    refs = ("training-consistency-principle", "riegel-race-prediction")

    if tgt >= cur_half:  # already at/under goal pace
        return FeasibilityVerdict(
            "no_caminho", 0.0, f"{_fmt(tgt)}/km", f"{_fmt(cur_half)}/km",
            "Projeção atual já atinge o objetivo. Manter consistência.", refs)

    required_monthly = 1 - (tgt / cur_half) ** (1 / months)
    if required_monthly <= REALISTIC_CEILING:
        v = "no_caminho"
        msg = (f"No caminho: precisa melhorar ~{required_monthly*100:.1f}%/mês, "
               "dentro do ritmo de evolução típico. Mantenha o plano.")
    elif required_monthly <= AGGRESSIVE_CEILING:
        v = "agressivo"
        msg = (f"Agressivo mas possível: precisa ~{required_monthly*100:.1f}%/mês "
               "(limite superior). Exige tudo dando certo — consistência total, "
               "talvez um 4º dia, zero lesão. O sistema vai reavaliar a cada prova.")
    else:
        v = "fora_de_alcance"
        msg = (f"Fora de alcance neste prazo: exigiria ~{required_monthly*100:.1f}%/mês, "
               "acima do que é seguro/realista. Trate como aspiração e mire um tempo "
               "intermediário; reavalie se a evolução surpreender.")
    return FeasibilityVerdict(
        v, required_monthly, f"{_fmt(tgt)}/km", f"{_fmt(cur_half)}/km", msg, refs)


def predicted_pace_on(
    start_5k_seconds: int,
    goal_half_seconds: int,
    start: date,
    race_date: date,
    checkpoint: date,
) -> float:
    """Half pace the goal-trajectory expects by `checkpoint` (linear-in-log ramp
    from start fitness to goal pace at the race)."""
    cur_half = predict_time(start_5k_seconds, 5.0, HALF_KM) / HALF_KM
    tgt = goal_half_seconds / HALF_KM
    total = max((race_date - start).days, 1)
    frac = min(max((checkpoint - start).days / total, 0.0), 1.0)
    return cur_half * (tgt / cur_half) ** frac


def checkpoint_status(
    benchmark_5k_seconds: int,
    start_5k_seconds: int,
    goal_half_seconds: int,
    start: date,
    race_date: date,
    checkpoint: date,
) -> dict:
    """At a benchmark race, is the athlete on the goal trajectory? Compares the
    benchmark's projected half pace to what the trajectory predicted for today."""
    actual_half = predict_time(benchmark_5k_seconds, 5.0, HALF_KM) / HALF_KM
    predicted = predicted_pace_on(start_5k_seconds, goal_half_seconds, start, race_date, checkpoint)
    delta_pct = (actual_half - predicted) / predicted  # >0 = slower than needed
    if delta_pct <= ON_TRACK_TOLERANCE:
        status, msg = "no_caminho", "No caminho do objetivo neste checkpoint."
    elif delta_pct <= 2 * ON_TRACK_TOLERANCE:
        status, msg = "atras", "Um pouco atrás do ritmo necessário; ainda recuperável."
    else:
        status, msg = "fora", "Bem atrás da trajetória; ajustar a meta ou o prazo."
    return {
        "status": status,
        "actual_half_pace": f"{_fmt(actual_half)}/km",
        "needed_half_pace": f"{_fmt(predicted)}/km",
        "gap_pct": round(delta_pct * 100, 1),
        "message": msg,
    }
