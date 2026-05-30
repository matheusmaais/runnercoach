"""Frequency progression suggestions (the coach's 'you're ready for more' voice).

This is ADVISORY ONLY and strictly separate from the safety envelope: it never
changes a recommendation/action. It proposes ADDING a 4th easy run only when
readiness has been sustained (green) for several weeks, following the 10%/ACWR
volume principle and Seiler easy-volume base building. Pure and deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass

from running_coach.accumulation import AccumulatedState

MIN_GREEN_WEEKS = 4          # sustained consistency before proposing more
MAX_RUN_DAYS = 4            # do not propose beyond a 4th day (Achilles-limited routine)
_ACHILLES_SAFE_MAX = 2      # recent Achilles must be quiet
_LOAD_RATIO_CEILING = 1.10  # not already ramping hard


@dataclass(frozen=True)
class ProgressionSuggestion:
    should_suggest: bool
    message: str                 # PT-BR coach voice
    science_refs: tuple[str, ...]


def suggest_fourth_day(
    state: AccumulatedState,
    run_days_per_week: int,
    consecutive_green_weeks: int,
) -> ProgressionSuggestion:
    """Propose a 4th easy run only when ALL readiness gates are green and
    sustained. Otherwise returns should_suggest=False (no nudge)."""
    blocked = (
        run_days_per_week >= MAX_RUN_DAYS
        or state.insufficient_history
        or state.achilles_is_rising
        or state.achilles_recent_max > _ACHILLES_SAFE_MAX
        or state.in_post_race_recovery
        or state.weekly_load_spike
        or (state.load_ratio is not None and state.load_ratio > _LOAD_RATIO_CEILING)
        or consecutive_green_weeks < MIN_GREEN_WEEKS
    )
    if blocked:
        return ProgressionSuggestion(False, "", ())
    return ProgressionSuggestion(
        True,
        (
            f"Você está absorvendo bem há {consecutive_green_weeks} semanas "
            "(sem dor no Aquiles, esforço controlado, carga estável). "
            "Considere adicionar um 4º dia de corrida LEVE para construir base "
            "aeróbica rumo à meia. Comece curto (~30-40 min fáceis) e mantenha "
            "os outros treinos iguais. Se a Bruna quiser, ela pode fazer esse dia "
            "sozinha caso o Aquiles do Matheus não permita."
        ),
        ("load-management-recovery", "seiler-intensity-distribution"),
    )
