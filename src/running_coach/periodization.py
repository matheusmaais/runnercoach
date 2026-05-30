"""Deterministic volume/long-run periodization (spec v1.7 Appendix C.2).

Pure, no clock, no I/O. Replaces the broken long-run prose with a single-state
generator whose output is pinned by a golden table. Key correction over the
earlier model: after a deload week the build resumes at the pre-deload
``build_peak`` (chronic load barely drops in one easy week), instead of the
depressed 4-week mean which made the long run decay.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from running_coach.models import Phase


def _floor2(value: float) -> float:
    # Truncate to 2 decimals so a ramp capped at mean*LOAD_RATIO_CAP is never
    # pushed ABOVE the cap by rounding up.
    return math.floor(value * 100) / 100

# Acute:chronic ramp cap vs the trailing 4-week mean (conservative; <1.3 safe zone).
LOAD_RATIO_CAP = 1.15
DELOAD_EVERY = 4          # every 4th week is a deload
DELOAD_FRACTION = 0.70    # deload volume = 70% of current build peak
TAPER_LONG_FRACTION = 0.55    # taper long run <= 55% of planned peak long
LONG_RUN_START_KM = 9.0   # current real ceiling


@dataclass(frozen=True)
class WeekPlan:
    week: int
    weekly_km: float
    long_km: float            # actual long run this week (dips on deload)
    long_peak_km: float       # progression peak reached so far
    is_deload: bool

    @property
    def long_share(self) -> float:
        return round(self.long_km / self.weekly_km, 3) if self.weekly_km else 0.0


@dataclass(frozen=True)
class VolumePlanParams:
    runs_per_week: int
    share_cap: float          # long run as a fraction of weekly volume
    volume_ceiling_km: float  # realistic peak weekly volume for the routine
    abs_step_km: float        # max absolute weekly volume increase on a build week
    long_step_km: float = 1.0
    long_peak_km: float = 20.0

    def __post_init__(self) -> None:
        if self.runs_per_week < 1:
            raise ValueError("runs_per_week must be >= 1")
        if not 0.0 < self.share_cap <= 1.0:
            raise ValueError("share_cap must be in (0, 1]")
        if self.volume_ceiling_km <= 0:
            raise ValueError("volume_ceiling_km must be > 0")
        if self.abs_step_km <= 0:
            raise ValueError("abs_step_km must be > 0 (else the plan never progresses)")
        if self.long_step_km < 0:
            raise ValueError("long_step_km must be >= 0")
        if self.long_peak_km <= 0:
            raise ValueError("long_peak_km must be > 0")


# Default profiles. Bruna is the performance target; her plan is NOT limited by
# Matheus's Achilles. A 4th easy run lowers the long-run share (~45% vs >=50% on
# 3 runs), distributing the same peak load more safely.
BRUNA_HALF = VolumePlanParams(
    runs_per_week=4, share_cap=0.45, volume_ceiling_km=42.0, abs_step_km=2.5
)


def generate_volume_plan(
    params: VolumePlanParams,
    weeks: int,
    baseline_km: float,
) -> list[WeekPlan]:
    """Generate a deterministic weekly volume + long-run progression.

    Invariants (asserted by the golden test):
      * long_km <= share_cap * weekly_km every week,
      * the weekly ramp never exceeds LOAD_RATIO_CAP vs the trailing 4-week mean
        (so the load guardrail would not flag a spike),
      * weekly volume never exceeds volume_ceiling_km,
      * long_peak rises monotonically toward params.long_peak_km.
    """
    if weeks < 1:
        return []
    if baseline_km <= 0:
        raise ValueError("baseline_km must be > 0")
    if baseline_km > params.volume_ceiling_km:
        raise ValueError(
            f"baseline_km ({baseline_km}) exceeds volume_ceiling_km "
            f"({params.volume_ceiling_km}); raise the ceiling or lower the baseline"
        )

    weekly = baseline_km
    build_peak = baseline_km
    long_peak = LONG_RUN_START_KM
    chronic: list[float] = [baseline_km] * 4
    plan: list[WeekPlan] = []

    for wk in range(1, weeks + 1):
        mean = sum(chronic[-4:]) / 4
        is_deload = wk % DELOAD_EVERY == 0
        if is_deload:
            weekly = _floor2(build_peak * DELOAD_FRACTION)
            long_now = _floor2(min(long_peak * DELOAD_FRACTION, params.share_cap * weekly))
        else:
            ramp_cap = mean * LOAD_RATIO_CAP
            weekly = _floor2(
                min(build_peak + params.abs_step_km, ramp_cap, params.volume_ceiling_km)
            )
            weekly = max(weekly, build_peak)
            build_peak = max(build_peak, weekly)
            long_peak = _floor2(
                min(
                    long_peak + params.long_step_km,
                    params.share_cap * weekly,
                    params.long_peak_km,
                )
            )
            long_now = long_peak
        plan.append(
            WeekPlan(
                week=wk,
                weekly_km=weekly,
                long_km=long_now,
                long_peak_km=long_peak,
                is_deload=is_deload,
            )
        )
        chronic.append(weekly)

    return plan


# --- Session selection: the right workout per slot for the active phase ---


class SessionType(StrEnum):
    EASY = "easy"
    LONG_EASY = "long_easy"
    LONG_PROGRESSIVE = "long_progressive"   # easy then HMP finish (half-specific)
    TEMPO_HMP = "tempo_hmp"                  # continuous at half-marathon pace
    HMP_INTERVALS = "hmp_intervals"          # reps at HMP
    INTERVALS_5_10K = "intervals_5_10k"      # faster reps, sharpening only
    OFF = "off"


# The quality session a phase is allowed to use (besides easy/long). One entry =
# the phase's intended weekly quality stimulus. None = aerobic only (all easy).
_PHASE_QUALITY: dict[Phase, SessionType | None] = {
    Phase.BASE: SessionType.INTERVALS_5_10K,  # maintain built velocity (1 light quality/wk)
    Phase.TEN_K_POLISH: SessionType.INTERVALS_5_10K,
    Phase.POST_TEN_K_RECOVERY: None,
    Phase.FIVE_TEN_K_DEVELOPMENT: SessionType.INTERVALS_5_10K,
    Phase.HALF_BASE: SessionType.TEMPO_HMP,
    Phase.HALF_SPECIFIC: SessionType.HMP_INTERVALS,
    Phase.HALF_TAPER: SessionType.HMP_INTERVALS,
}

# Long run becomes progressive (HMP finish) only in half-specific work.
_PROGRESSIVE_LONG_PHASES = {Phase.HALF_SPECIFIC}

# Quality is never scheduled the day after volleyball (Wed) -> avoid Thursday;
# prefer the non-volleyball running day for quality. With Tue/Thu/Sun runs and
# volleyball on Wed, quality goes on Tuesday, long on Sunday, Thursday easy.
QUALITY_DAY = "tuesday"
LONG_DAY = "sunday"
RUN_DAYS = ("tuesday", "thursday", "sunday")


@dataclass(frozen=True)
class SessionPlan:
    day: str
    session: SessionType
    distance_km: float | None       # set for long run; None = duration-based easy/quality
    science_refs: tuple[str, ...]


def select_week_sessions(
    phase: Phase,
    week: WeekPlan,
    *,
    allow_quality: bool,
) -> list[SessionPlan]:
    """Deterministically pick the right session for each run slot of the week.

    Rules (so workouts come out 'right'):
      * Sunday is always the long run (distance from generate_volume_plan).
      * Most running is easy (Seiler intensity distribution).
      * Exactly one quality slot (Tuesday), only if the phase prescribes quality,
        it is NOT a deload week, and ``allow_quality`` (no active reduce/Achilles
        block from the adaptive layer).
      * In half_specific the long run is progressive (HMP finish) and counts as
        the quality stimulus, so no extra mid-week quality is added.
    """
    if phase not in _PHASE_QUALITY:
        raise ValueError(f"phase {phase!r} has no session-quality mapping")
    phase_quality = _PHASE_QUALITY[phase]
    long_is_progressive = phase in _PROGRESSIVE_LONG_PHASES
    quality_enabled = (
        allow_quality and not week.is_deload and phase_quality is not None
    )
    # Taper safety: during HALF_TAPER the long run must REDUCE into the race,
    # never sit at peak. Cap it to a taper fraction of the planned long run
    # regardless of where the build/deload volume cycle happens to be.
    long_km = week.long_km
    if phase == Phase.HALF_TAPER:
        long_km = round(min(long_km, week.long_km * TAPER_LONG_FRACTION), 2)

    sessions: list[SessionPlan] = []
    for day in RUN_DAYS:
        if day == LONG_DAY:
            if long_is_progressive and quality_enabled:
                sessions.append(
                    SessionPlan(
                        day,
                        SessionType.LONG_PROGRESSIVE,
                        long_km,
                        ("seiler-intensity-distribution", "threshold-training-lactate"),
                    )
                )
            else:
                sessions.append(
                    SessionPlan(
                        day,
                        SessionType.LONG_EASY,
                        long_km,
                        ("seiler-intensity-distribution",),
                    )
                )
        elif (
            day == QUALITY_DAY
            and quality_enabled
            and not long_is_progressive  # half_specific quality lives in the long run
        ):
            sessions.append(
                SessionPlan(
                    day,
                    phase_quality,
                    None,
                    ("threshold-training-lactate",),
                )
            )
        else:
            sessions.append(
                SessionPlan(day, SessionType.EASY, None, ("seiler-intensity-distribution",))
            )
    return sessions


# --- Living plan: reverse-anchored phase schedule + horizon generation ---

from datetime import date as _date, timedelta as _timedelta  # noqa: E402

# Ordered toward the A-race, with target durations (weeks). Reverse-anchored:
# the taper ends on race week; earlier phases are compressed if time is short.
_PHASE_LADDER: list[tuple[Phase, int]] = [
    (Phase.BASE, 6),
    (Phase.FIVE_TEN_K_DEVELOPMENT, 5),
    (Phase.HALF_BASE, 8),
    (Phase.HALF_SPECIFIC, 6),
    (Phase.HALF_TAPER, 2),
]


@dataclass(frozen=True)
class PhaseBlock:
    phase: Phase
    start: _date   # inclusive (Monday of the first week)
    end: _date     # exclusive
    weeks: int


def _monday(d: _date) -> _date:
    return d - _timedelta(days=d.weekday())


def derive_phase_schedule(today: _date, race_date: _date) -> list[PhaseBlock]:
    """Reverse-anchor the phase ladder from the A-race back to today.

    The taper abuts the race; earlier phases fill the remaining weeks. If there
    is less time than the ladder's total, the earliest phases are dropped/
    truncated (you taper and do specific work no matter what). Deterministic.
    """
    start_week = _monday(today)
    race_week = _monday(race_date)
    total_weeks = max(1, (race_week - start_week).days // 7)

    # Allocate from the end (taper) backward until weeks run out, but guarantee
    # the terminal phases that actually matter for the race: taper, then
    # specific. With >=2 weeks we always keep at least 1 taper + 1 specific;
    # early phases (base, development, half_base) are dropped first.
    allocated: list[tuple[Phase, int]] = []
    remaining = total_weeks
    ladder_rev = list(reversed(_PHASE_LADDER))
    mandatory_suffix = [Phase.HALF_TAPER, Phase.HALF_SPECIFIC]
    for idx, (phase, want) in enumerate(ladder_rev):
        if remaining <= 0:
            break
        # Reserve 1 week for each not-yet-allocated mandatory phase that should
        # still come after this one in chronological terms (i.e. earlier in this
        # reversed loop), so taper never starves specific.
        reserve = sum(
            1
            for mp in mandatory_suffix
            if mp not in [p for p, _ in allocated] and mp != phase
        )
        take = min(want, max(0, remaining - reserve))
        if take == 0 and phase in mandatory_suffix and remaining > 0:
            take = 1  # ensure mandatory phase gets at least 1 week
        if take > 0:
            allocated.append((phase, take))
            remaining -= take
    # If time remains after the full ladder, spread the extra weeks across the
    # quality-bearing phases (half_base gets most, development next) so a longer
    # runway adds varied SHARPENING, not endless easy base or one monotonous block.
    if remaining > 0 and allocated:
        weights = {Phase.HALF_BASE: 2, Phase.FIVE_TEN_K_DEVELOPMENT: 1}
        targets = [(i, weights[ph]) for i, (ph, _) in enumerate(allocated) if ph in weights]
        if not targets:
            targets = [(len(allocated) - 1, 1)]  # fallback: earliest phase
        total_w = sum(w for _, w in targets)
        # proportional split, remainder to the first (highest-weight) target
        assigned = 0
        for idx, w in targets:
            add = remaining * w // total_w
            ph, weeks = allocated[idx]
            allocated[idx] = (ph, weeks + add)
            assigned += add
        if assigned < remaining:
            idx = targets[0][0]
            ph, weeks = allocated[idx]
            allocated[idx] = (ph, weeks + (remaining - assigned))
    allocated.reverse()  # back to chronological order

    blocks: list[PhaseBlock] = []
    cursor = start_week
    for phase, weeks in allocated:
        end = cursor + _timedelta(weeks=weeks)
        blocks.append(PhaseBlock(phase=phase, start=cursor, end=end, weeks=weeks))
        cursor = end
    return blocks


def _phase_on(blocks: list[PhaseBlock], d: _date) -> Phase | None:
    for b in blocks:
        if b.start <= d < b.end:
            return b.phase
    return None


@dataclass(frozen=True)
class PlannedSession:
    date: _date
    phase: Phase
    day: str
    session: SessionType
    distance_km: float | None
    science_refs: tuple[str, ...]


def plan_horizon(
    today: _date,
    race_date: _date,
    params: VolumePlanParams,
    baseline_km: float,
    *,
    horizon_weeks: int = 8,
    allow_quality: bool = True,
) -> list[PlannedSession]:
    """Generate the next ``horizon_weeks`` of dated sessions: the right session,
    in the right phase, at the right volume. Future-facing only."""
    blocks = derive_phase_schedule(today, race_date)
    if today >= race_date:
        return []  # cycle finished; no new training rows until a new target is set
    total_weeks = max(1, (_monday(race_date) - _monday(today)).days // 7)
    volume = generate_volume_plan(params, weeks=total_weeks, baseline_km=baseline_km)

    start_week = _monday(today)
    out: list[PlannedSession] = []
    for i in range(min(horizon_weeks, len(volume))):
        week_start = start_week + _timedelta(weeks=i)
        phase = _phase_on(blocks, week_start)
        if phase is None:
            continue
        week_plan = volume[i]
        day_offsets = {"tuesday": 1, "thursday": 3, "sunday": 6}
        for sp in select_week_sessions(phase, week_plan, allow_quality=allow_quality):
            d = week_start + _timedelta(days=day_offsets[sp.day])
            if d <= today:
                continue  # never schedule today/past (living plan = future only)
            if d == race_date:
                continue  # the A-race is not a generated training session
            out.append(
                PlannedSession(
                    date=d,
                    phase=phase,
                    day=sp.day,
                    session=sp.session,
                    distance_km=sp.distance_km,
                    science_refs=sp.science_refs,
                )
            )
    return out


def merge_future_only(
    existing_rows: list[dict],
    new_future_rows: list[dict],
    today: _date,
    owned_prefix: str = "plan-20",
) -> list[dict]:
    """Append-only guard. Keep every existing row dated <= today byte-identical.
    For the future, replace ONLY rows the living-plan generator owns (id starting
    with ``owned_prefix`` and matching the generated date+slot scheme); preserve
    future rows it does not own (e.g. anchored races / diagnostics) so they are
    never silently deleted."""
    def _row_date(row: dict) -> _date:
        return _date.fromisoformat(row["date"])

    def _is_generated(row: dict) -> bool:
        rid = row.get("planned_workout_id", "")
        # generated ids look like 'plan-YYYY-MM-DD-<slot>'
        return rid.startswith(owned_prefix) and rid.count("-") >= 4

    import copy

    kept_past = [copy.deepcopy(r) for r in existing_rows if _row_date(r) <= today]
    preserved_future = [
        copy.deepcopy(r)
        for r in existing_rows
        if _row_date(r) > today and not _is_generated(r)
    ]
    new_dates = {r["date"] for r in new_future_rows}
    # Avoid duplicate dates: a preserved (non-generated) future row wins its date.
    preserved_dates = {r["date"] for r in preserved_future}
    future = [
        copy.deepcopy(r)
        for r in new_future_rows
        if _row_date(r) > today and r["date"] not in preserved_dates
    ]
    merged = kept_past + preserved_future + future
    merged.sort(key=lambda r: r["date"])
    return merged


# CSV schema for data/plan/planned_workouts.csv
PLANNED_CSV_FIELDS = [
    "planned_workout_id",
    "week_number",
    "date",
    "phase",
    "slot",
    "intended_category",
    "purpose",
    "primary_athlete",
    "planned_distance_or_duration",
    "planned_intensity_range",
    "allowed_fallbacks",
    "contraindications",
    "status",
]

_SESSION_CATEGORY = {
    SessionType.EASY: "easy_run",
    SessionType.LONG_EASY: "long_run",
    SessionType.LONG_PROGRESSIVE: "long_progressive",
    SessionType.TEMPO_HMP: "tempo_hmp",
    SessionType.HMP_INTERVALS: "hmp_intervals",
    SessionType.INTERVALS_5_10K: "intervals_5_10k",
    SessionType.OFF: "off",
}


def planned_session_to_row(s: "PlannedSession") -> dict:
    """Map a generated PlannedSession to a planned_workouts.csv row (EN tokens;
    the PT-BR labels live in the frontend layer)."""
    import json as _json

    is_quality = s.session in {
        SessionType.TEMPO_HMP,
        SessionType.HMP_INTERVALS,
        SessionType.INTERVALS_5_10K,
        SessionType.LONG_PROGRESSIVE,
    }
    return {
        "planned_workout_id": f"plan-{s.date.isoformat()}-{s.day}",
        "week_number": str(s.date.isocalendar().week),
        "date": s.date.isoformat(),
        "phase": s.phase.value,
        "slot": s.day,
        "intended_category": _SESSION_CATEGORY.get(s.session, s.session.value),
        "purpose": s.session.value,
        "primary_athlete": "bruna",
        "planned_distance_or_duration": (
            f"{s.distance_km:.1f} km" if s.distance_km is not None else "by_feel"
        ),
        "planned_intensity_range": "easy" if not is_quality else "controlled",
        "allowed_fallbacks": _json.dumps(["replace_with_easy", "replace_with_off"]),
        "contraindications": _json.dumps(["red_flag"]),
        "status": "planned",
    }

