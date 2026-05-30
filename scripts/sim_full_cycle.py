#!/usr/bin/env python3
"""Full-preparation simulation across 3 fitness shapes (V, inverted-U, perfect).
For each week we show the phase, the planned session per slot (specificity +
progression), the coach decision, and the actionable advice. Proves the plan
stays phase-specific and progressive while adapting to feedback."""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from running_coach.accumulation import WorkoutHistoryPoint, build_athlete_state
from running_coach.explain import explain_change
from running_coach.models import Phase, RecommendationAction, SymptomSeverity
from running_coach.periodization import BRUNA_HALF, generate_volume_plan, select_week_sessions
from running_coach.recommendations import RecommendationInput, recommend_next_action

START = date(2026, 6, 1)
WEEKS = 12
VOL = generate_volume_plan(BRUNA_HALF, weeks=WEEKS, baseline_km=20.0)

# Map week index to a phase to show specificity progression.
def phase_for(i):
    if i < 3: return Phase.BASE
    if i < 5: return Phase.FIVE_TEN_K_DEVELOPMENT
    if i < 9: return Phase.HALF_BASE
    if i < 11: return Phase.HALF_SPECIFIC
    return Phase.HALF_TAPER


def pse_shape(shape, i, n):
    """Return Sunday-long PSE by shape across n weeks (the feedback signal)."""
    mid = n / 2
    if shape == "V":            # good -> bad -> good
        return 6 if i < mid else 8 if i < mid + 2 else 6
    if shape == "U_inv":        # improving -> worsening
        return 6 if i < 3 else 7 if i < mid else 9
    return 6                    # perfect: steady


for shape in ("V", "U_inv", "perfeito"):
    print(f"\n################ SHAPE: {shape} ################")
    history = [pt for w in range(1, 5) for pt in
               [WorkoutHistoryPoint(START - timedelta(days=7 * w + d), 8, True, 6, 0, 0, False, False)
                for d in (0, 3)]]
    for i in range(WEEKS):
        ph = phase_for(i)
        week = VOL[i]
        ref = START + timedelta(days=7 * i + 6)  # Sunday long
        sessions = select_week_sessions(ph, week, allow_quality=True)
        long = next(s for s in sessions if s.day == "sunday")
        mid_quality = [s for s in sessions if s.day == "tuesday" and s.session.value not in ("easy",)]
        pse = pse_shape(shape, i, WEEKS)
        state = build_athlete_state(history, ref, planned_week_km=week.weekly_km)
        inp = RecommendationInput(
            bruna_pse=pse, symptom_severity=SymptomSeverity.NONE,
            matheus_achilles_morning=0, matheus_achilles_after=0,
            volleyball_previous_day=False, poor_sleep=False, all_out_race=False,
            planned_action=RecommendationAction.MAINTAIN_NEXT_WORKOUT,
            phase=ph.value, week_number=i + 1, planned_workout_id=f"w{i}", accumulated=state,
        )
        r = recommend_next_action(inp)
        q = mid_quality[0].session.value if mid_quality else "—"
        print(f"S{i+1:>2} {ph.value:<22} long {long.distance_km:>4}km/{long.session.value:<16} "
              f"qual:{q:<14} PSE{pse} -> {r.action.value:<22} ({(r.reasons[0] if r.reasons!=['within_guardrails'] else 'ok')})")
        history.append(WorkoutHistoryPoint(ref, week.long_km, True, pse, 0, 0, False, False))

print("\n=== Checagem de especificidade/progressao ===")
peak = max(w.long_km for w in VOL)
print(f"longao: inicio {VOL[0].long_km}km -> pico {peak}km (progressivo: {VOL[0].long_km < peak})")
print(f"fases percorridas: {sorted({phase_for(i).value for i in range(WEEKS)})}")
