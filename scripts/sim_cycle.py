#!/usr/bin/env python3
"""Chained 4-week simulation: feed workouts sequentially, build accumulated
state from real prior history, and show how each feedback adapts the NEXT
recommendation + the coach's PT-BR explanation. Proves feedback propagation."""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from running_coach.accumulation import WorkoutHistoryPoint, build_athlete_state
from running_coach.explain import explain_change
from running_coach.models import RecommendationAction, SymptomSeverity
from running_coach.recommendations import RecommendationInput, recommend_next_action

START = date(2026, 8, 3)  # a Monday, deep enough for sufficient history


def pt(d, km, *, pse=6, sev=SymptomSeverity.NONE, ach_m=0, ach_a=0, sleep=False, race=False, run=True):
    return WorkoutHistoryPoint(
        local_date=d, distance_km=km, is_running=run, bruna_pse=pse,
        matheus_achilles_morning=ach_m, matheus_achilles_after=ach_a,
        poor_sleep=sleep, all_out_race=race,
    )


# A 4-week narrative. Each tuple: (label, day-offset, scenario kwargs for the
# CURRENT workout's check-in). We seed 4 prior weeks of steady easy running so
# accumulated load is well-defined from week 1 of the narrative.
SEED = [pt(START - timedelta(days=7 * w + d), 8) for w in range(1, 5) for d in (0, 3)]

NARRATIVE = [
    # (week, label, day, km, kwargs)
    (1, "A: treino leve perfeito",          0, 8,  dict(pse=5)),
    (1, "B: qualidade, mas exausto (PSE 9)", 3, 9,  dict(pse=9)),
    (1, "C: longo apos B ruim",             6, 14, dict(pse=7)),
    (2, "A: voltou bem",                    7, 8,  dict(pse=6)),
    (2, "B: sono ruim",                     10, 9, dict(pse=7, sleep=True)),
    (2, "C: longo",                         13, 15, dict(pse=6)),
    (3, "A: Aquiles incomodando (3)",       14, 8, dict(ach_a=3)),
    (3, "B: Aquiles subindo (4)",           17, 9, dict(ach_a=4)),
    (3, "C: longo",                         20, 16, dict(pse=6)),
    (4, "A: tudo verde",                    21, 8, dict(pse=5)),
    (4, "B: prova all-out",                 24, 10, dict(pse=9, race=True)),
    (4, "C: longo pos-prova",               27, 16, dict(pse=6)),
]

history = list(SEED)
print(f"{'Sem':<4}{'Treino':<32}{'-> Proximo':<24}{'Confianca':<10}Razao principal")
print("-" * 108)
cur_week = 0
for week, label, day, km, kw in NARRATIVE:
    ref = START + timedelta(days=day)
    state = build_athlete_state(history, ref)
    inp = RecommendationInput(
        bruna_pse=kw.get("pse", 6),
        symptom_severity=kw.get("sev", SymptomSeverity.NONE),
        matheus_achilles_morning=kw.get("ach_m", 0),
        matheus_achilles_after=kw.get("ach_a", 0),
        volleyball_previous_day=False,
        poor_sleep=kw.get("sleep", False),
        all_out_race=kw.get("race", False),
        planned_action=RecommendationAction.MAINTAIN_NEXT_WORKOUT,
        phase="half_specific", week_number=week, planned_workout_id=f"w{week}-{day}",
        accumulated=state,
    )
    r = recommend_next_action(inp)
    exp = explain_change(r, planned_action="maintain_next_workout")
    primary = (exp.triggers[0] if exp.triggers else "dentro das margens")
    if week != cur_week:
        print(f"--- Semana {week} ---")
        cur_week = week
    print(f"{week:<4}{label:<32}{r.action.value:<24}{r.confidence.value:<10}{primary}")
    # feed this workout into history for the next decision
    history.append(pt(ref, km, pse=kw.get("pse", 6),
                      ach_m=kw.get("ach_m", 0), ach_a=kw.get("ach_a", 0),
                      sleep=kw.get("sleep", False), race=kw.get("race", False)))

# Show one full coach explanation (week 4 post-race long run) to inspect voice.
print("\n=== Exemplo de explicacao do coach (Semana 4, longo pos-prova) ===")
ref = START + timedelta(days=27)
state = build_athlete_state(history[:-1], ref)
inp = RecommendationInput(
    bruna_pse=6, symptom_severity=SymptomSeverity.NONE, matheus_achilles_morning=0,
    matheus_achilles_after=0, volleyball_previous_day=False, poor_sleep=False,
    all_out_race=False, planned_action=RecommendationAction.MAINTAIN_NEXT_WORKOUT,
    phase="half_specific", week_number=4, planned_workout_id="w4-27", accumulated=state,
)
exp = explain_change(recommend_next_action(inp), planned_action="maintain_next_workout")
print("O que muda :", exp.what_changed)
print("Por que    :", exp.why)
print("Gatilhos   :", ", ".join(exp.triggers) or "-")
print("Micro      :", exp.micro_objective)
print("Macro      :", exp.macro_objective)
print("Fontes     :", ", ".join(exp.sources))
