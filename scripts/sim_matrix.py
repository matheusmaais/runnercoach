#!/usr/bin/env python3
"""E2E simulation matrix: run real edge cases through recommend_next_action and
report what the coach decides + which signals fired. Reveals coverage gaps."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from running_coach.models import RecommendationAction, SymptomSeverity
from running_coach.recommendations import RecommendationInput, recommend_next_action

PLANNED = RecommendationAction.MAINTAIN_NEXT_WORKOUT


def inp(**ov):
    base = dict(
        bruna_pse=6, symptom_severity=SymptomSeverity.NONE,
        matheus_achilles_morning=0, matheus_achilles_after=0,
        volleyball_previous_day=False, poor_sleep=False, all_out_race=False,
        planned_action=PLANNED, phase="half_base", week_number=5, planned_workout_id="p5",
    )
    base.update(ov)
    return RecommendationInput(**base)


SCENARIOS = [
    ("Treino perfeito", inp(bruna_pse=5)),
    ("Treino perfeito mas cansado (PSE 8)", inp(bruna_pse=8)),
    ("PSE muito alto (9)", inp(bruna_pse=9)),
    ("Vôlei no dia anterior", inp(volleyball_previous_day=True)),
    ("Academia/pernas no dia anterior", inp(gym_previous_day=True)),
    ("Sono ruim", inp(poor_sleep=True)),
    ("Sintoma forte (moderate)", inp(symptom_severity=SymptomSeverity.MODERATE)),
    ("Red flag (tontura)", inp(symptom_severity=SymptomSeverity.RED_FLAG)),
    ("Aquiles 3 (Matheus)", inp(matheus_achilles_after=3)),
    ("Aquiles 5 (Matheus)", inp(matheus_achilles_after=5)),
    ("Prova all-out", inp(all_out_race=True)),
    ("Combo: vôlei + sono ruim", inp(volleyball_previous_day=True, poor_sleep=True)),
    ("Longão quebrado (encurtado)", inp(workout_truncated=True)),
    ("Longão rápido demais", inp(overpaced=True)),
    ("Longão lento demais", inp(underpaced=True)),
]

print(f"{'Cenário':<38}{'Ação':<26}{'Confiança':<10}Razões")
print("-" * 110)
for name, i in SCENARIOS:
    r = recommend_next_action(i)
    reasons = ",".join(x for x in r.reasons if x != "within_guardrails") or "-"
    print(f"{name:<38}{r.action.value:<26}{r.confidence.value:<10}{reasons}")
