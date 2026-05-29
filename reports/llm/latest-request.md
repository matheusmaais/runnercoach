# Running Coach LLM Recommendation Request

## Data Contract

Garmin physiology is Matheus-only. Shared pace/distance/time can be used for Bruna only when shared_run=true and bruna_present=true.

## Forbidden Claims

- Do not use Matheus solo pace as Bruna evolution
- Do not infer Bruna heart rate from Garmin heart rate
- Do not prescribe all-out speed when evidence is missing
- Do not cite science outside approved_science_refs
- Do not diagnose injury or medical conditions

## Current State

# Running Coach State

## Last Update

- Mode: after-workout
- Latest Garmin activity: 2026-05-28 garmin-20260528T171417-1p33km-349s-245ee321 1.33km @4:22
- Latest shared coaching evidence: 2026-05-28 garmin-20260528T161736-7p47km-3039s-17b463bc 7.47km @6:47
- Activities processed: 20
- Workouts modeled: 20
- Missing check-in evidence: 19
- Approved science refs available: 9

## Current Phase

- Phase: ten_k_polish
- Week number: 1
- Weekly rhythm: run Tuesday, Thursday, Sunday; strength Monday/Friday and sometimes Saturday; volleyball Wednesday.

## Current Paces

- Bruna easy/long run estimate: 6:40-7:00/km.
- Bruna strong sustainable estimate: 6:10-6:20/km.
- Bruna threshold estimate: around 6:00/km when recovered.
- Bruna short all-out ceiling from recent rustic race: around 5:50/km; not continuous training pace.
- Matheus recent solo residual speed: 1.33 km at 4:22/km; not used as Bruna evolution evidence.

## Current Risks

- Missing check-ins: 19.
- Matheus Achilles remains the strategic limiter.
- Volleyball counts as neuromuscular load before Thursday sessions.
- Poor sleep, high PSE, strong symptoms, or heavy legs reduce the next workout.

## Next Milestones

- 2026-05-31: diagnostic_race_10k (ten_k_polish) -> planned
- 2026-06-02: easy_run (post_ten_k_recovery) -> planned

## Active Decisions

- Do not compensate missed workouts with volume.
- Keep long runs easy.
- Treat Matheus Garmin physiology as Matheus-only.
- Use shared pace for Bruna only when check-in confirms shared run and Bruna presence.


## Latest Shared Workout

```json
{
  "workout_id": "workout-garmin-20260528T161736-7p47km-3039s-17b463bc",
  "activity_id": "garmin-20260528T161736-7p47km-3039s-17b463bc",
  "local_date": "2026-05-28",
  "local_datetime": "2026-05-28 16:17:36",
  "athlete_context": "shared_run_with_manual_checkin",
  "participants": [
    "matheus",
    "bruna"
  ],
  "shared_run": "true",
  "bruna_present": "true",
  "distance_km": "7.47",
  "avg_pace": "6:47",
  "bruna_pse": "7",
  "bruna_symptoms": [],
  "matheus_achilles_after": "0",
  "volleyball_previous_day": "true",
  "missing_evidence": [
    "bruna_hr_screenshot",
    "bruna_avg_hr",
    "bruna_max_hr"
  ],
  "bruna_evidence": "available"
}
```

## Latest Matheus Solo Workout

```json
{
  "workout_id": "workout-garmin-20260528T171417-1p33km-349s-245ee321",
  "activity_id": "garmin-20260528T171417-1p33km-349s-245ee321",
  "local_date": "2026-05-28",
  "local_datetime": "2026-05-28 17:14:17",
  "athlete_context": "matheus_garmin_only",
  "participants": [
    "matheus"
  ],
  "shared_run": "false",
  "bruna_present": "false",
  "distance_km": "1.33",
  "avg_pace": "4:22",
  "bruna_pse": "",
  "bruna_symptoms": [],
  "matheus_achilles_after": "",
  "volleyball_previous_day": "",
  "missing_evidence": [
    "checkin"
  ],
  "bruna_evidence": "not_applicable"
}
```

## Next Planned Workouts

```json
[
  {
    "planned_workout_id": "plan-20260531-10k",
    "week_number": "1",
    "date": "2026-05-31",
    "phase": "ten_k_polish",
    "intended_category": "diagnostic_race_10k",
    "planned_status": "planned",
    "derived_status": "planned",
    "matched_workout_id": "",
    "related_decision": "",
    "evidence": "future_or_pending",
    "missing_evidence": "[]"
  },
  {
    "planned_workout_id": "plan-20260602-recovery",
    "week_number": "2",
    "date": "2026-06-02",
    "phase": "post_ten_k_recovery",
    "intended_category": "easy_run",
    "planned_status": "planned",
    "derived_status": "planned",
    "matched_workout_id": "",
    "related_decision": "",
    "evidence": "future_or_pending",
    "missing_evidence": "[]"
  }
]
```

## Approved Science Refs

- `achilles-tendinopathy-load`
- `load-management-recovery`
- `safety-red-flag-conservative`
- `seiler-intensity-distribution`
- `sleep-fatigue-load-management`
- `strength-running-economy`
- `threshold-training-lactate`
- `training-consistency-principle`
- `volleyball-neuromuscular-load`

## Required Response Schema

Return only JSON with these fields:

```json
{
  "athlete_scope": "shared_run|bruna|matheus|both",
  "confidence": "high|medium|low",
  "decision_type": "DecisionType enum value",
  "evidence_used": "workout_id or document ids used",
  "missing_evidence": "missing evidence list",
  "next_workout": "specific next workout recommendation",
  "next_workout_action": "RecommendationAction enum value",
  "recommendation_id": "stable string id",
  "risk_assessment": "risk and fatigue assessment",
  "schema_version": "integer, must be 1",
  "science_refs": "approved science_ref_id list",
  "summary": "short coaching summary",
  "what_workout_showed": "evidence-based interpretation"
}
```

Allowed next_workout_action values include:

- `maintain_next_workout`
- `reduce_next_workout`
- `replace_with_easy`
- `replace_with_off`
- `replace_with_cross_training`
- `defer_quality`
- `bruna_without_matheus`
- `request_manual_resolution`
