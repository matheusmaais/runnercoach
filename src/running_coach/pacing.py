"""Race-calibrated pacing (closes the 'pace prescription' + 'calibration' gap).

From a recent race result, derive training pace zones via the Riegel model and
map each session type to a concrete pace. Pure, deterministic, science-cited
(riegel-race-prediction, daniels-vdot-pacing). Zones are conservative for a
recreational athlete (Riegel exponent 1.08)."""

from __future__ import annotations

from dataclasses import dataclass

from running_coach.periodization import SessionType

RIEGEL_EXPONENT = 1.08  # conservative for recreational, Achilles-limited athletes
HALF_KM = 21.0975

# Offsets (sec/km) from the EQUIVALENT 5K race pace (the most reliable measured
# max). Tuned for a recreational endurance profile whose easy pace sits close to
# race pace (aerobic base ahead of top speed). A 5:50/km 5K yields easy ~6:40,
# threshold ~6:00, half ~6:10 — matching demonstrated zones, not generic tables.
_ZONE_OFFSET = {
    "intervals_5_10k": 0,           # at 5K race pace (reps down to best split)
    "strong_sustainable": 15,
    "hmp_intervals": 18,
    "tempo_hmp": 20,                # threshold / half-marathon pace work
    "half_marathon": 20,
    "long_progressive_finish": 20,  # long run finishing at HMP
    "easy": 48,
    "long_easy": 50,
}


@dataclass(frozen=True)
class Benchmark:
    distance_km: float
    time_seconds: int
    conditions: str = "normal"  # "heat" -> bands are effort-based, not pace-based


def predict_time(t1_s: float, d1_km: float, d2_km: float) -> float:
    return t1_s * (d2_km / d1_km) ** RIEGEL_EXPONENT


def classify_effort(pace_sec: float, zones: dict[str, str], pse: int | None = None) -> str:
    """Label a run from measured pace vs calibrated zones (+ optional PSE).
    Returns one of: 'race', 'threshold', 'quality', 'easy'. Used to auto-detect a
    strong effort so it can calibrate zones without a manual race entry.
    A run qualifies as hard only if pace is at/below threshold OR PSE>=8 with
    pace at least at HMP — never on easy days."""
    if not zones or pace_sec <= 0:
        return "easy"
    race = _pace_sec(zones.get("intervals_5_10k"))
    thr = _pace_sec(zones.get("tempo_hmp"))
    if race and pace_sec <= race + 8:        # at/near 5K pace
        return "race"
    if thr and pace_sec <= thr + 10:          # threshold / HMP band
        return "threshold" if (pse is None or pse >= 7) else "quality"
    if pse is not None and pse >= 8 and thr and pace_sec <= thr + 30:
        return "quality"                      # felt very hard at a quick-ish pace
    return "easy"


def _pace_sec(value: str | None) -> float | None:
    if not value:
        return None
    try:
        mm, ss = value.replace("/km", "").split(":")
        return int(mm) * 60 + int(ss)
    except (ValueError, AttributeError):
        return None


def select_best(benchmarks: list[Benchmark]) -> Benchmark | None:
    """Pick the strongest effort: fastest performance normalized to 5K via Riegel.
    Heat/invalid efforts are ignored. This is how fitness gains auto-tighten zones:
    a faster recent race or tempo wins; easy runs never qualify (filtered upstream)."""
    valid = [b for b in benchmarks if b.distance_km > 0 and b.time_seconds > 0 and b.conditions != "heat"]
    if not valid:
        return None
    return min(valid, key=lambda b: predict_time(b.time_seconds, b.distance_km, 5.0))


def _fmt(sec: float) -> str:
    sec = int(round(sec))
    return f"{sec // 60}:{sec % 60:02d}"


def zones_from_benchmark(b: Benchmark) -> dict[str, str]:
    """Return PT-BR pace zones (min/km) calibrated from a race result.
    Invalid benchmarks or heat conditions yield effort-based guidance."""
    if b.distance_km <= 0 or b.time_seconds <= 0:
        return {"calibrated_from": "prova inválida — use esforço/PSE"}
    if b.conditions == "heat":
        return {"calibrated_from": "prova no calor — zonas por esforço/PSE"}
    race_pace = b.time_seconds / b.distance_km
    half_proj = predict_time(b.time_seconds, b.distance_km, HALF_KM) / HALF_KM
    zones: dict[str, str] = {}
    for name, off in _ZONE_OFFSET.items():
        zones[name] = f"{_fmt(race_pace + off)}/km"
    zones["half_projection"] = f"{_fmt(half_proj)}/km"
    zones["calibrated_from"] = f"{b.distance_km:.0f}K em {_fmt(race_pace)}/km"
    return zones


_SESSION_ZONE = {
    SessionType.EASY: "easy",
    SessionType.LONG_EASY: "long_easy",
    SessionType.LONG_PROGRESSIVE: "long_progressive_finish",
    SessionType.TEMPO_HMP: "tempo_hmp",
    SessionType.HMP_INTERVALS: "hmp_intervals",
    SessionType.INTERVALS_5_10K: "intervals_5_10k",
    SessionType.OFF: None,
}


def heat_adjusted_pace(pace_sec: float, temp_c: float) -> float:
    """Slow target pace in heat: ~+3s/km per °C above 15°C (endurance heuristic,
    bounded). Below 15°C no change. Keeps efforts iso-effort, not iso-pace."""
    if temp_c <= 15 or pace_sec <= 0:
        return pace_sec
    add = min((temp_c - 15) * 3.0, 90.0)  # cap at +90s/km in extreme heat
    return pace_sec + add


def prescribe_pace(session: SessionType, zones: dict[str, str], heat: bool = False) -> str:
    """Concrete PT-BR pace for a session. In heat, switch to effort-based."""
    zone = _SESSION_ZONE.get(session)
    if zone is None:
        return "—"
    if heat:
        return "por esforço/PSE (calor)"
    if session == SessionType.LONG_PROGRESSIVE:
        return f"leve, finalizando em {zones.get('long_progressive_finish', '—')}"
    return zones.get(zone, "—")
