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

# Offsets (sec/km) from predicted half-marathon pace (HMP) for each zone.
# Negative = faster than HMP. Bounded, conservative.
_ZONE_OFFSET = {
    "easy": +75,
    "long_easy": +75,
    "long_progressive_finish": 0,   # finishes at HMP
    "strong_sustainable": +10,
    "tempo_hmp": 0,
    "hmp_intervals": -5,
    "intervals_5_10k": None,        # uses recent race pace directly
}


@dataclass(frozen=True)
class Benchmark:
    distance_km: float
    time_seconds: int
    conditions: str = "normal"  # "heat" -> bands are effort-based, not pace-based


def predict_time(t1_s: float, d1_km: float, d2_km: float) -> float:
    return t1_s * (d2_km / d1_km) ** RIEGEL_EXPONENT


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
    hmp = predict_time(b.time_seconds, b.distance_km, HALF_KM) / HALF_KM
    zones: dict[str, str] = {}
    for name, off in _ZONE_OFFSET.items():
        pace = race_pace if off is None else hmp + off
        zones[name] = f"{_fmt(pace)}/km"
    zones["half_marathon"] = f"{_fmt(hmp)}/km"
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
