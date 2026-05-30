"""Accumulated athlete state (P0): turns workout history into the signals the
recommendation engine needs to be adaptive (feedback from workout 1 shaping
workouts 2, 3 and the week). Pure, deterministic, no clock, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

# Reconciled with periodization.py / spec 3.4.
LOAD_RATIO_CAP = 1.15
LOAD_ABS_FLOOR_KM = 5.0
RECOVERY_DAYS = 6          # post all-out race recovery window (10k default)
ACHILLES_TREND_DELTA = 1   # after-morning >= this blocks escalation
MIN_HISTORY_DAYS = 21      # below this, load ratios are not trustworthy


@dataclass(frozen=True)
class WorkoutHistoryPoint:
    local_date: date
    distance_km: float | None
    is_running: bool
    bruna_pse: int | None
    matheus_achilles_morning: int | None
    matheus_achilles_after: int | None
    poor_sleep: bool
    all_out_race: bool


@dataclass(frozen=True)
class AccumulatedState:
    last_7d_distance_km: float
    prior_28d_mean_7d_distance_km: float
    load_ratio: float | None
    achilles_recent_max: int
    achilles_is_rising: bool
    days_since_all_out_race: int | None
    in_post_race_recovery: bool
    history_days: int
    insufficient_history: bool

    @property
    def weekly_load_spike(self) -> bool:
        if self.load_ratio is None:
            return False
        return (
            self.load_ratio > LOAD_RATIO_CAP
            and (self.last_7d_distance_km - self.prior_28d_mean_7d_distance_km)
            > LOAD_ABS_FLOOR_KM
        )


def _running_km(points: list[WorkoutHistoryPoint], lo: date, hi: date) -> float:
    # km on running points with lo <= date < hi
    return sum(
        p.distance_km or 0.0
        for p in points
        if p.is_running and lo <= p.local_date < hi
    )


def build_athlete_state(
    history: list[WorkoutHistoryPoint], reference_date: date
) -> AccumulatedState:
    past = [p for p in history if p.local_date < reference_date]
    if not past:
        return AccumulatedState(
            last_7d_distance_km=0.0,
            prior_28d_mean_7d_distance_km=0.0,
            load_ratio=None,
            achilles_recent_max=0,
            achilles_is_rising=False,
            days_since_all_out_race=None,
            in_post_race_recovery=False,
            history_days=0,
            insufficient_history=True,
        )

    earliest = min(p.local_date for p in past)
    history_days = (reference_date - earliest).days
    insufficient = history_days < MIN_HISTORY_DAYS

    last_7d = _running_km(past, reference_date - timedelta(days=7), reference_date)
    prior_points = [
        p
        for p in past
        if reference_date - timedelta(days=35) <= p.local_date < reference_date - timedelta(days=7)
        and p.is_running
    ]
    prior_total = sum(p.distance_km or 0.0 for p in prior_points)
    prior_mean = prior_total / 4.0
    # Require real coverage in the prior 28-day window: at least one running
    # data point in each of >=3 of the 4 prior weeks. Otherwise a single old
    # run averaged over 4 weeks would look like rest and fake a spike.
    prior_weeks_covered = len(
        {
            (reference_date - p.local_date).days // 7
            for p in prior_points
        }
    )
    enough_coverage = prior_weeks_covered >= 3
    load_ratio = (
        round(last_7d / prior_mean, 3)
        if (not insufficient and prior_mean > 0 and enough_coverage)
        else None
    )

    # Achilles trend over the lookback window (distinct dates only).
    by_date: dict[date, int] = {}
    for p in past:
        if (
            p.matheus_achilles_after is not None
            and p.local_date >= reference_date - timedelta(days=28)
        ):
            # Last value on a given day wins (deterministic by date order below).
            by_date[p.local_date] = p.matheus_achilles_after
    achilles_pts = sorted(by_date.items())
    achilles_recent_max = max((v for _, v in achilles_pts), default=0)
    rising = False
    if len(achilles_pts) >= 3:
        vals = [v for _, v in achilles_pts[-3:]]
        rising = all(b > a for a, b in zip(vals, vals[1:]))

    race_dates = [p.local_date for p in past if p.all_out_race]
    days_since_race = (
        (reference_date - max(race_dates)).days if race_dates else None
    )
    in_recovery = days_since_race is not None and days_since_race <= RECOVERY_DAYS

    return AccumulatedState(
        last_7d_distance_km=round(last_7d, 2),
        prior_28d_mean_7d_distance_km=round(prior_mean, 2),
        load_ratio=load_ratio,
        achilles_recent_max=achilles_recent_max,
        achilles_is_rising=rising,
        days_since_all_out_race=days_since_race,
        in_post_race_recovery=in_recovery,
        history_days=history_days,
        insufficient_history=insufficient,
    )


def accumulated_reasons(state: AccumulatedState) -> list[str]:
    """Reasons that LOWER the training envelope. Never raise it."""
    reasons: list[str] = []
    if state.weekly_load_spike:
        reasons.append("weekly_load_spike")
    if state.achilles_is_rising or state.achilles_recent_max >= ACHILLES_TREND_DELTA + 2:
        reasons.append("achilles_trend_rising")
    if state.in_post_race_recovery:
        reasons.append("post_race_recovery")
    if state.insufficient_history:
        reasons.append("insufficient_history")
    return reasons
