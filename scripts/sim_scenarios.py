#!/usr/bin/env python3
"""25+ full-cycle scenarios to the January half, run through the REAL engine via
sim_harness. Each scenario asserts coaching invariants: progression/specificity,
reduce-when-needed, fail-closed safety, taper, post-injury return. Prints a
summary table; reused as the source of the permanent pytest lock (Task 5)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sim_harness import RACE_DATE, WeeklyFeedback, run_cycle  # noqa: E402

from running_coach.models import Phase, SymptomSeverity  # noqa: E402

S = SymptomSeverity


def _wk_span(phase: Phase, weeks_total=33):
    return None


# --- Scenario feedback functions: fn(i, phase) -> WeeklyFeedback ---
def perfect(i, ph):
    return WeeklyFeedback(pse=6)


def v_shape(i, ph):  # good -> bad middle -> good
    return WeeklyFeedback(pse=8 if 12 <= i <= 18 else 6)


def inverted_u(i, ph):  # improve then decline
    return WeeklyFeedback(pse=6 if i < 16 else 9)


def above_average(i, ph):  # thriving: low PSE, occasional strong effort
    return WeeklyFeedback(pse=4 if i % 3 else 5)


def below_average(i, ph):  # always struggling
    return WeeklyFeedback(pse=8)


def two_weeks_off_midcycle(i, ph):
    return WeeklyFeedback(pse=6, skipped=15 <= i <= 16)


def achilles_injury_block(i, ph):  # Matheus Achilles flares weeks 10-14
    if 10 <= i <= 14:
        return WeeklyFeedback(pse=6, achilles_morning=5, achilles_after=6)
    return WeeklyFeedback(pse=6)


def achilles_then_recover(i, ph):
    if 10 <= i <= 12:
        return WeeklyFeedback(pse=6, achilles_morning=6, achilles_after=7)
    return WeeklyFeedback(pse=6)  # returns to normal -> should resume progression


def illness_sustained(i, ph):  # PSE >= 9 for 3 weeks (sickness)
    return WeeklyFeedback(pse=9 if 8 <= i <= 10 else 6)


def red_flag_once(i, ph):
    if i == 20:
        return WeeklyFeedback(pse=7, symptom=S.RED_FLAG)
    return WeeklyFeedback(pse=6)


def chronic_poor_sleep(i, ph):
    return WeeklyFeedback(pse=7, poor_sleep=True)


def heavy_volleyball(i, ph):
    return WeeklyFeedback(pse=7, volleyball_prev=True)


def all_out_race_midcycle(i, ph):  # a tune-up race week 18
    if i == 18:
        return WeeklyFeedback(pse=9, all_out_race=True, symptom=S.MILD)
    return WeeklyFeedback(pse=6)


def flaky_skips(i, ph):  # skips every 4th week
    return WeeklyFeedback(pse=6, skipped=(i % 4 == 3))


def moderate_symptoms_spell(i, ph):
    return WeeklyFeedback(pse=7, symptom=S.MODERATE if 6 <= i <= 9 else S.NONE)


def late_injury_in_taper(i, ph):  # Achilles flare during taper
    if ph == Phase.HALF_TAPER:
        return WeeklyFeedback(pse=6, achilles_morning=5, achilles_after=5)
    return WeeklyFeedback(pse=6)


def early_struggle_then_thrive(i, ph):
    return WeeklyFeedback(pse=8 if i < 8 else 5)


def oscillating(i, ph):  # alternating good/bad weeks
    return WeeklyFeedback(pse=6 if i % 2 == 0 else 8)


def one_big_skip_block(i, ph):  # 3 weeks off (vacation/sick)
    return WeeklyFeedback(pse=6, skipped=20 <= i <= 22)


def deload_friendly(i, ph):  # consistently moderate
    return WeeklyFeedback(pse=7)


def pristine_then_redflag_taper(i, ph):
    if ph == Phase.HALF_TAPER and i % 2 == 0:
        return WeeklyFeedback(pse=7, symptom=S.RED_FLAG)
    return WeeklyFeedback(pse=6)


def achilles_creep(i, ph):  # slowly rising Achilles
    a = min(6, i // 6)
    return WeeklyFeedback(pse=6, achilles_morning=a, achilles_after=a)


def strong_with_volleyball(i, ph):
    return WeeklyFeedback(pse=5, volleyball_prev=(i % 2 == 0))


def sick_then_redflag(i, ph):
    if i == 9:
        return WeeklyFeedback(pse=9, symptom=S.RED_FLAG)
    if 7 <= i <= 11:
        return WeeklyFeedback(pse=9)
    return WeeklyFeedback(pse=6)


def perfect_cold(i, ph):  # ideal, cool weather (no heat)
    return WeeklyFeedback(pse=6)


def taper_perfect(i, ph):
    return WeeklyFeedback(pse=6 if ph != Phase.HALF_TAPER else 5)


SCENARIOS = {
    "perfeito": perfect,
    "V (bom-ruim-bom)": v_shape,
    "U-invertido": inverted_u,
    "acima da media": above_average,
    "abaixo da media": below_average,
    "2 semanas off (meio)": two_weeks_off_midcycle,
    "lesao aquiles (bloco)": achilles_injury_block,
    "aquiles e recupera": achilles_then_recover,
    "doenca sustentada": illness_sustained,
    "red flag pontual": red_flag_once,
    "sono ruim cronico": chronic_poor_sleep,
    "volei pesado": heavy_volleyball,
    "prova tune-up": all_out_race_midcycle,
    "faltas recorrentes": flaky_skips,
    "sintomas moderados": moderate_symptoms_spell,
    "lesao no taper": late_injury_in_taper,
    "sofre e melhora": early_struggle_then_thrive,
    "oscilante": oscillating,
    "3 semanas off": one_big_skip_block,
    "deload friendly": deload_friendly,
    "red flag no taper": pristine_then_redflag_taper,
    "aquiles crescente": achilles_creep,
    "forte com volei": strong_with_volleyball,
    "doente e red flag": sick_then_redflag,
    "perfeito frio": perfect_cold,
    "taper perfeito": taper_perfect,
}

# Decisions that mean "the coach pulled back" (Bruna's training). Note:
# bruna_without_matheus is NOT a pullback for Bruna — she still trains; Matheus
# sits out (his Achilles limits HIM, not her).
_REDUCED = {"reduce_next_workout", "replace_with_easy", "replace_with_off",
            "replace_with_cross_training", "defer_quality"}


def check_invariants(name, res):
    """Return (passed: bool, notes: list[str]) for a scenario result."""
    notes = []
    ok = True
    phases = {w.phase for w in res.weeks}
    longs = [w.long_km for w in res.weeks]

    # 1) full cycle reached: must include specific + taper phases
    if Phase.HALF_TAPER not in phases or Phase.HALF_SPECIFIC not in phases:
        ok = False; notes.append("FALTA fase especifica/taper")

    # 2) progression: peak long > first long (specificity is built)
    if max(longs) <= longs[0]:
        ok = False; notes.append("SEM progressao de longao")

    # 3) taper reduces: every taper long < peak long
    peak = max(longs)
    taper_longs = [w.long_km for w in res.weeks if w.phase == Phase.HALF_TAPER]
    if taper_longs and max(taper_longs) >= peak:
        ok = False; notes.append("TAPER nao reduz")

    # 4) safety: any RED_FLAG week must NOT maintain (must reduce/off)
    for w in res.weeks:
        if w.reason in {"red_flag_symptom"} and w.action == "maintain_next_workout":
            ok = False; notes.append(f"RED FLAG sem freio em S{w.week_number}")

    # 5) reduce-when-needed: high-PSE weeks (>=9) must pull back
    for w in res.weeks:
        if w.pse >= 9 and not w.skipped and w.action == "maintain_next_workout":
            ok = False; notes.append(f"PSE9 sem reducao em S{w.week_number}")

    # 6) Matheus Achilles high -> Bruna trains without Matheus (Achilles limits HIM)
    for w in res.weeks:
        if w.reason == "matheus_achilles_ge_5" and w.action not in {
                "bruna_without_matheus", "replace_with_off", "replace_with_easy"}:
            ok = False; notes.append(f"Aquiles alto mal tratado em S{w.week_number}")

    return ok, notes


def main():
    print(f"Rodando {len(SCENARIOS)} cenarios ate {RACE_DATE}\n")
    passed = 0
    for name, fb in SCENARIOS.items():
        res = run_cycle(fb)
        ok, notes = check_invariants(name, res)
        reduced = sum(1 for w in res.weeks if w.action in _REDUCED)
        peak = max(w.long_km for w in res.weeks)
        tag = "OK " if ok else "FALHA"
        print(f"[{tag}] {name:<24} sem={len(res.weeks)} pico_longao={peak:>5}km "
              f"reduziu={reduced:>2}x {' | '.join(notes)}")
        passed += ok
    print(f"\n{passed}/{len(SCENARIOS)} cenarios passaram em todos os invariantes")
    return 0 if passed == len(SCENARIOS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
