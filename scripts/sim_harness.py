#!/usr/bin/env python3
"""Reusable full-cycle simulation harness driving the REAL coaching engine.

Runs week-by-week from a start date to the A-race, using the real periodization
(phase schedule + volume plan + session selection), the real adaptive engine
(build_athlete_state + recommend_next_action), and the real pacing calibration.

A scenario is a callable feedback(week_index, phase) -> WeeklyFeedback that
supplies the subjective/objective signals for that week. Tasks 4/5 reuse this.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from running_coach.accumulation import WorkoutHistoryPoint, build_athlete_state
from running_coach.models import Phase, RecommendationAction, SymptomSeverity
from running_coach.pacing import Benchmark, prescribe_pace, zones_from_benchmark
from running_coach.periodization import (
    BRUNA_HALF,
    derive_phase_schedule,
    generate_volume_plan,
    select_week_sessions,
)
from running_coach.recommendations import RecommendationInput, recommend_next_action

RACE_DATE = date(2027, 1, 24)
DEFAULT_START = date(2026, 6, 1)
DEFAULT_BENCHMARK = Benchmark(5.0, 29 * 60 + 10)  # Bruna's real 5K (5:50/km)


@dataclass
class WeeklyFeedback:
    pse: int = 6
    symptom: SymptomSeverity = SymptomSeverity.NONE
    achilles_morning: int = 0
    achilles_after: int = 0
    volleyball_prev: bool = False
    poor_sleep: bool = False
    all_out_race: bool = False
    skipped: bool = False  # athlete did not run this week


@dataclass
class WeekResult:
    index: int
    week_number: int
    phase: Phase
    long_km: float
    long_session: str
    long_pace: str
    quality_session: str
    quality_pace: str
    action: str
    reason: str
    pse: int
    skipped: bool


@dataclass
class CycleResult:
    weeks: list[WeekResult] = field(default_factory=list)

    @property
    def actions(self) -> list[str]:
        return [w.action for w in self.weeks]

    @property
    def phases(self) -> list[Phase]:
        return [w.phase for w in self.weeks]


def run_cycle(
    feedback,
    start: date = DEFAULT_START,
    race_date: date = RACE_DATE,
    benchmark: Benchmark = DEFAULT_BENCHMARK,
) -> CycleResult:
    """Drive the real engine week-by-week from start to race_date."""
    blocks = derive_phase_schedule(start, race_date)
    # Include the race week itself (the final partial week up to race day) so the
    # taper's last week is covered; the race day is not a training session.
    total_weeks = max(1, (_monday(race_date) - _monday(start)).days // 7) + 1
    volume = generate_volume_plan(BRUNA_HALF, weeks=total_weeks, baseline_km=20.0)
    zones = zones_from_benchmark(benchmark)

    history: list[WorkoutHistoryPoint] = [
        WorkoutHistoryPoint(start - timedelta(days=7 * w + d), 8.0, True, 6, 0, 0, False, False)
        for w in range(1, 5)
        for d in (0, 3)
    ]
    result = CycleResult()
    for i in range(total_weeks):
        ref = _monday(start) + timedelta(days=7 * i + 6)  # Sunday
        phase = _phase_on(blocks, ref) or Phase.BASE
        week = volume[min(i, len(volume) - 1)]
        fb = feedback(i, phase)

        # adaptive state must gate quality (Achilles/PSE/spike -> no quality)
        state = build_athlete_state(history, ref, planned_week_km=week.weekly_km)
        inp = RecommendationInput(
            bruna_pse=fb.pse,
            symptom_severity=fb.symptom,
            matheus_achilles_morning=fb.achilles_morning,
            matheus_achilles_after=fb.achilles_after,
            volleyball_previous_day=fb.volleyball_prev,
            poor_sleep=fb.poor_sleep,
            all_out_race=fb.all_out_race,
            planned_action=RecommendationAction.MAINTAIN_NEXT_WORKOUT,
            phase=phase.value,
            week_number=i + 1,
            planned_workout_id=f"w{i}",
            accumulated=state,
        )
        rec = recommend_next_action(inp)
        allow_quality = rec.action == RecommendationAction.MAINTAIN_NEXT_WORKOUT
        sessions = select_week_sessions(phase, week, allow_quality=allow_quality)
        long = next(s for s in sessions if s.day == "sunday")
        quality = next((s for s in sessions if s.day == "tuesday"
                        and s.session.value != "easy"), None)

        result.weeks.append(WeekResult(
            index=i, week_number=i + 1, phase=phase,
            long_km=long.distance_km or 0.0,
            long_session=long.session.value,
            long_pace=prescribe_pace(long.session, zones),
            quality_session=quality.session.value if quality else "—",
            quality_pace=prescribe_pace(quality.session, zones) if quality else "—",
            action=rec.action.value,
            reason=(rec.reasons[0] if rec.reasons != ["within_guardrails"] else "ok"),
            pse=fb.pse, skipped=fb.skipped,
        ))

        # Feed the ACTUAL executed load (per the decision) back into history, so
        # off/easy/reduced weeks genuinely lower future load — not the planned one.
        executed_km = _executed_km(rec.action.value, long.distance_km or 0.0)
        ran = not fb.skipped and executed_km > 0
        if ran:
            history.append(WorkoutHistoryPoint(
                ref, executed_km, True, fb.pse,
                fb.achilles_morning, fb.achilles_after, fb.poor_sleep, fb.all_out_race))
        elif not fb.skipped:
            # off day with no run: record a non-running point so trend/recovery see it
            history.append(WorkoutHistoryPoint(
                ref, 0.0, False, fb.pse,
                fb.achilles_morning, fb.achilles_after, fb.poor_sleep, fb.all_out_race))
    return result


# Executed long-run km by decision: off=0, easy/reduce shrink it, defer keeps the
# long (only quality is deferred), bruna_without_matheus keeps Bruna's full run.
_EXECUTED_FRACTION = {
    "replace_with_off": 0.0,
    "replace_with_cross_training": 0.0,
    "replace_with_easy": 0.5,
    "reduce_next_workout": 0.7,
    "defer_quality": 1.0,
    "bruna_without_matheus": 1.0,
    "maintain_next_workout": 1.0,
    "request_manual_resolution": 0.0,
}


def _executed_km(action: str, planned_long: float) -> float:
    return round(planned_long * _EXECUTED_FRACTION.get(action, 1.0), 2)


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _phase_on(blocks, d: date):
    for b in blocks:
        if b.start <= d < b.end:
            return b.phase
    return None


if __name__ == "__main__":
    # smoke: perfect cycle
    res = run_cycle(lambda i, ph: WeeklyFeedback(pse=6))
    print(f"weeks={len(res.weeks)} phases={sorted({p.value for p in res.phases})}")
    print(f"long: {res.weeks[0].long_km} -> peak {max(w.long_km for w in res.weeks)}")
    for w in res.weeks[:6] + res.weeks[-4:]:
        print(f"S{w.week_number:>2} {w.phase.value:<22} long {w.long_km:>5}km @{w.long_pace:<8} "
              f"qual {w.quality_session:<14}@{w.quality_pace:<8} -> {w.action} ({w.reason})")
