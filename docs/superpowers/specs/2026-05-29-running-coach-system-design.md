# Running Coach System Design

Date: 2026-05-29

Project: Projeto Meia Forte Janeiro 2027 -- Matheus & Bruna

## Purpose

Build a lightweight, versioned running coaching platform for Matheus and Bruna that replaces a simple spreadsheet with an auditable data, science, feedback, and recommendation system.

The system is personal, not generic. It must use Garmin data, subjective feedback, injury history, weekly routine, training goals, and scientific evidence to guide safe performance development toward a strong half marathon at the end of January 2027.

The product should be fully designed now, but implemented incrementally. This is not waterfall. It is a complete north-star design with stable data contracts and vertical releases that remain useful at each stage.

## Non-Negotiable Product Principles

1. Consistency beats heroics.
2. Long easy runs are protected.
3. Intensity must be intentional and controlled.
4. True limit efforts happen only in races or rare tests.
5. Volume must not increase aggressively.
6. Missed training is not compensated with extra load.
7. Volleyball counts as neuromuscular load.
8. Lower-body strength training counts as running-relevant load.
9. Poor sleep changes the training decision.
10. Matheus's left Achilles is a strategic limiter.
11. The system adapts the plan; it does not blindly follow a static sheet.
12. Pace is prescribed by ranges, not exact seconds.
13. Garmin instant pace is not treated as ground truth.
14. Lap pace, splits, PSE/RPE, and context are preferred for decisions.

## Athletes And Data Truth

### Matheus

- 39 years old.
- 1.64 m.
- Former fast runner; prior 5K close to 18 minutes.
- Has run half marathons, Mizuno Uphill, and other events.
- Chronic history of left Achilles tendinopathy.
- Current role is primarily Bruna's pacer.
- Main priority is health and avoiding Achilles recurrence.
- Recent test: 1.33 km at 4:22/km, average HR 189, max HR 192, Achilles silent.
- Interpretation: high residual speed exists, but the system must not encourage frequent maximal speed work.

### Bruna

- 32 years old.
- Strong athletic background, volleyball player, lean, conditioned, does strength training.
- Excellent early response to run training.
- Current focus: improve 5K/10K, then convert to a strong half marathon.
- Recent rustic race: 5.24 km at 5:50/km, average HR 185, max HR 199, blurry vision, real all-out.
- Interpretation: 5:50/km is current short-race ceiling, not continuous training pace.
- Recent controlled 3x10 min: 6:13 / 6:04 / 6:00, tired from volleyball the prior day, but controlled.
- Current working estimate: 6:00/km is around threshold/strong; 6:10-6:15/km is strong sustainable.

### Garmin Contract

The Garmin watch is on Matheus's wrist.

- Garmin pace, distance, and elapsed time are valid shared-run observations when Matheus and Bruna run together.
- Garmin HR, cadence, power, ground contact time, vertical oscillation, and stride length belong to Matheus only.
- Bruna is evaluated through shared pace, PSE/RPE, manual HR when provided, symptoms, subjective feedback, recovery, volleyball, strength training, sleep, menstrual/cólica context when voluntarily provided, and whether she felt she could repeat the block.
- Missing Bruna feedback does not block recommendations, but lowers confidence and must be recorded as missing evidence.

## Current Training Context

Weekly baseline:

- Monday: strength training.
- Tuesday: run.
- Wednesday: volleyball.
- Thursday: run.
- Friday: strength training.
- Saturday: optional strength training.
- Sunday: run, long run, or race.

Implications:

- Tuesday is often after strength work.
- Thursday is after volleyball and should not automatically be maximal.
- Sunday is protected for long run or race.
- Saturday strength must be controlled if Sunday has long run or race.
- Bruna's performance goal takes priority, with Matheus pacing as long as Achilles risk remains acceptable.

## Roadmap To January 2027

The full product and coaching roadmap covers:

1. 10K polishing and diagnostic race.
2. Post-10K recovery.
3. 5K/10K development.
4. Half-marathon base.
5. Half-marathon specific phase.
6. Half-marathon taper.

The Sunday 10K on 2026-05-31 is a diagnostic race, not the final goal. Strategy:

- Plan A: controlled aggressive.
- Km 1-3: 6:15-6:20/km.
- Km 4-7: sustain by lap pace and PSE, without chasing exact seconds.
- Km 8-10: progress only if no symptoms and control remains.
- Recede to conservative mode if blurry vision, dizziness, PSE 9 too early, disorganized breathing before km 5, unusual pain, heat stress, or other concerning symptom appears.

The January 2027 half-marathon target is a provisional range, not an official fixed time. It should appear in the dashboard as a hypothesis and be recalibrated from races, key workouts, consistency, recovery, and risk.

## Architecture

The selected architecture is a versioned local coaching core with derived interfaces.

The spreadsheet is not the brain. Google Sheets, Excel, CLI, GitHub Pages, and LLM outputs are interfaces over the same core model.

### Data Flow

```text
Garmin raw CSV, local and gitignored
        +
manual check-ins as YAML per workout
        +
approved science registry
        +
deterministic coaching rules
        |
        v
processed CSVs, state docs, decisions, recommendations, dashboard, reports
```

### Repository Shape

```text
running-coach-system/
├── README.md
├── pyproject.toml
├── Makefile
├── .gitignore
├── .env.example
├── data/
│   ├── raw/
│   │   └── garmin/              # local input, ignored except .gitkeep
│   ├── manual/
│   │   ├── checkins/            # canonical human input
│   │   └── screenshots/         # optional local/reference screenshots
│   └── processed/
│       ├── activities.csv
│       ├── workouts.csv
│       ├── races.csv
│       ├── wellness.csv
│       ├── decisions.csv
│       ├── zones.csv
│       └── science_refs.csv
├── docs/
│   ├── state.md
│   ├── roadmap.md
│   ├── decisions.md
│   ├── coaching-principles.md
│   ├── scientific-basis.md
│   ├── athlete-profiles.md
│   └── operating-manual.md
├── reports/
│   ├── dashboard.xlsx
│   ├── latest-summary.md
│   ├── monthly/
│   └── charts/
├── scripts/
│   ├── run_pipeline.py
│   ├── ingest_garmin.py
│   ├── normalize_activities.py
│   ├── calculate_metrics.py
│   ├── update_state.py
│   ├── generate_recommendation.py
│   ├── build_dashboard.py
│   ├── sync_google_sheets.py
│   └── research_science.py
├── src/
│   └── running_coach/
│       ├── models.py
│       ├── garmin.py
│       ├── checkins.py
│       ├── metrics.py
│       ├── zones.py
│       ├── fatigue.py
│       ├── injury_risk.py
│       ├── projections.py
│       ├── recommendations.py
│       ├── science.py
│       ├── reports.py
│       └── sheets.py
└── tests/
```

## Privacy And Versioning Policy

The repo uses a hybrid privacy model.

- `data/raw/garmin/` is local and gitignored by default.
- `data/manual/checkins/`, docs, processed CSVs, reports, and decision logs are versioned.
- The raw CSV can be re-imported locally at any time.
- Tests use small anonymized fixtures, not the full raw Garmin export.
- Screenshots are optional references and should be local/ignored unless explicitly curated.

The provided generated workbook is a visual and semantic reference only. It must not be used as a source of truth, because formulas and decisions inside it are not the product contract.

## Manual Check-In Contract

Manual feedback is canonical as one YAML file per workout.

Example:

```yaml
schema_version: 1
date: 2026-05-28
activity_match:
  garmin_title: "Santo Ângelo - 3x10min"
  garmin_datetime: "2026-05-28 16:17:36"
session:
  planned_type: quality_controlled
  actual_type: cruise_intervals
  shared_run: true
bruna:
  avg_hr: 168
  max_hr: 186
  pse: 7
  symptoms: []
  sleep_quality: regular
  volleyball_previous_day: true
  gym_previous_day: false
  lower_body_load_previous_day: none
  subjective: "Cansada pelo vôlei, mas controlou bem."
  could_repeat_last_block: false
matheus:
  achilles_morning: 0
  achilles_after: 0
  role: pacemaker
  subjective: "Aquiles silencioso."
attachments:
  bruna_hr_screenshot: null
coach_notes:
  decision_after_workout: "Manter polimento, evitar buscar 5:50/km como treino contínuo."
```

The future CLI, GitHub Pages form, screenshot workflow, or chat-assisted entry must all write this same YAML shape. CSVs remain derived artifacts.

## Processed Data Contracts

### activities.csv

Garmin facts, normalized from Portuguese Garmin CSV.

Required fields include date/time, title, activity type, distance, duration, average pace, best pace, elevation, training effect, and Matheus-only physiological/running dynamics fields.

### workouts.csv

Unified coaching view of shared runs and other relevant training events.

Required fields include:

- date
- athlete_context
- activity_type
- category
- distance_km
- duration
- avg_pace
- best_pace
- matheus_avg_hr
- matheus_max_hr
- matheus_cadence
- matheus_power
- matheus_ground_contact
- matheus_stride_length
- bruna_avg_hr
- bruna_max_hr
- bruna_pse
- bruna_symptoms
- matheus_achilles_morning
- matheus_achilles_after
- sleep_quality
- volleyball_previous_day
- gym_previous_day
- notes
- decision_after_workout
- confidence
- missing_evidence

### races.csv

Race and benchmark events.

Fields:

- date
- race_name
- distance_km
- time
- avg_pace
- elevation_gain
- bruna_avg_hr
- bruna_max_hr
- bruna_pse
- symptoms
- interpretation
- new_training_zones
- next_decision

### wellness.csv

Daily or workout-adjacent wellness context.

Fields:

- date
- matheus_sleep
- bruna_sleep
- matheus_achilles_morning
- matheus_achilles_after
- soreness
- stress
- alcohol
- hydration
- menstrual_colica_context_when_voluntarily_provided
- notes

### decisions.csv

Auditable decision log.

Fields:

- date
- event
- decision
- reason
- impact
- related_workout_id
- evidence
- confidence
- science_refs

## Recommendation Engine

The engine has two layers.

### Deterministic Guardrails

These rules define the allowed decision envelope:

- If Bruna PSE >= 9 in training, next run is easy/off.
- If Bruna had strong symptoms, reduce intensity.
- If Matheus Achilles is 3-4/10, remove intervals, descending, fast progressions, and speed focus.
- If Matheus Achilles is >= 5/10, recommend off/cross-training and revisit plan.
- If Achilles worsens for two consecutive days, raise alert level.
- If Achilles after workout is worse than morning, raise alert level.
- If volleyball was the previous day, avoid maximal sessions.
- If sleep was poor, reduce volume or intensity.
- If a workout was missed, do not compensate.
- If a race was all-out, treat the next 2-4 days as recovery.
- If high fatigue persists for two weeks, insert a down week.

### LLM Coach Layer

The LLM layer is allowed to choose and phrase recommendations only inside deterministic guardrails.

Every recommendation must include:

- what the workout showed
- what changed in current state
- what is working
- what is not working
- current risk
- whether next workout is maintained, reduced, or changed
- whether the cycle phase changed
- whether zones changed
- whether 10K or half-marathon projections changed
- decision recorded
- confidence
- missing evidence
- assumptions
- science references used

The LLM cannot cite unaudited popular advice. It can only cite the approved science registry.

## Science Registry

V1 uses curated and versioned science, with automation only as an assistant.

Artifacts:

- `docs/scientific-basis.md`: practical interpretation for Matheus and Bruna.
- `data/processed/science_refs.csv`: structured registry of approved sources.
- `scripts/research_science.py`: assists with future research, but never overwrites approved science automatically.

Required science topics:

- polarized training
- threshold training and cruise intervals
- VO2max intervals
- easy runs and long runs
- 5K/10K/half-marathon periodization
- running injury prevention
- Achilles tendinopathy
- acute/chronic load concepts and limitations
- strength training for runners
- sleep, fatigue, and recovery
- volleyball/jumping sports as neuromuscular load

Preferred source families:

- Stephen Seiler
- Jack Daniels
- Pfitzinger
- Hansons Running
- Matt Fitzgerald
- World Athletics
- ACSM
- NSCA
- British Journal of Sports Medicine
- Sports Medicine
- Journal of Applied Physiology
- Scandinavian Journal of Medicine & Science in Sports
- PubMed-indexed peer-reviewed studies

## Dashboard Design

V1 produces `reports/dashboard.xlsx`, designed as the future Google Sheets structure.

Required tabs:

1. Dashboard
2. Estado Atual
3. Próximos Treinos
4. Treinos Garmin
5. Semanas
6. Provas e Marcos
7. Decisões
8. Roadmap
9. Ciência & Prompt
10. Dados Gráficos

The first tab must be a modern cockpit, not a decorated data dump.

Dashboard requirements:

- 5 top cards: evolution, fatigue, risk, next workout, half-marathon path.
- Clear status language: ON TRACK, ATENÇÃO, REDUZIR, RECUPERAR.
- Decision block: evidence -> decision -> next step.
- Minimal gridlines and restrained visual density.
- Navy/dark header, teal for progress, light gray background, amber for caution, red for real risk.
- Tables, filters, freeze panes, and conditional formatting on operational tabs.

Required charts:

- average pace evolution
- long-run evolution
- weekly volume
- runs per week
- quality workouts per week
- best races
- 10K projection
- half-marathon projection
- sustainable strong-pace trend
- risk/fatigue trend

## Reports And Operating Cadence

The system runs after each workout.

Primary command:

```bash
python scripts/run_pipeline.py --garmin "data/raw/garmin/Activities.csv" --after-workout
```

The pipeline updates processed data, state, recommendations, decisions, latest summary, and dashboard.

Weekly summaries are derived automatically and shown in processed data/dashboard. There is no separate weekly ritual.

Formal monthly reports are generated every 30 days or by command:

```bash
python scripts/run_pipeline.py --monthly-report
```

## V1 Definition Of Done

V1 is complete when:

1. Repository structure exists.
2. Garmin CSV can be copied/imported into ignored raw storage.
3. Garmin PT-BR parser handles the provided `Activities (2).csv`.
4. Check-in YAML files exist for known key workouts.
5. Processed CSVs are generated.
6. Core docs are written:
   - `docs/state.md`
   - `docs/roadmap.md`
   - `docs/decisions.md`
   - `docs/coaching-principles.md`
   - `docs/scientific-basis.md`
   - `docs/athlete-profiles.md`
   - `docs/operating-manual.md`
7. Deterministic recommendation guardrails are implemented.
8. Initial curated science registry exists.
9. Modern local dashboard is generated.
10. A single pipeline command updates the system.
11. Tests cover parsing, data ownership, safety rules, recommendation confidence, and dashboard generation.

## Testing Strategy

Minimum tests:

- Garmin PT-BR parsing of dates, decimal numbers, duration, pace, and `--` values.
- Garmin physiological fields map only to Matheus.
- Shared run pace/distance/time can apply to both athletes.
- Check-in YAML validation rejects invalid PSE, invalid Achilles scores, and impossible dates.
- PSE >= 9 forces easy/off recommendation.
- Achilles >= 3 removes intensity for Matheus.
- Achilles >= 5 recommends off/cross-training.
- Volleyball previous day blocks maximal training.
- Poor sleep reduces volume or intensity.
- Missed workouts are not compensated.
- All-out race creates recovery window.
- Recommendation output includes confidence, missing evidence, assumptions, decision, and science refs.
- Dashboard generation creates all required tabs.

## Release Roadmap

### V1: Core Local

Pipeline, models, data contracts, check-ins YAML, docs, dashboard local, deterministic recommendation, and science registry.

### V2: Google Sheets

Import or sync the local dashboard to a persistent Google Sheets workbook named `Projeto Meia Forte Janeiro 2027 -- Matheus & Bruna`.

### V3: Input UX

Mobile-friendly GitHub Pages or local form that creates the same check-in YAML contract.

### V4: Screenshot/OCR

Extract Bruna HR from Galaxy watch screenshots, attach source image, and record extracted values with confidence.

### V5: Guardrailed LLM Coach

Use LLM for narrative recommendation, but only inside deterministic guardrails and approved science references.

### V6: Automation

Automate monthly reports, reminders, race calibration summaries, and possibly Google Sheets refresh.

## Open Implementation Choices

These are intentionally deferred to implementation planning:

- Exact Python validation library.
- Exact dashboard authoring library.
- Whether `Makefile` wraps the Python commands or remains optional.
- Whether screenshots are committed, ignored, or selectively curated.
- Whether Google Sheets sync starts as import-only or API update.

## Approval Status

Approved design decisions from brainstorming:

- V1 is local core plus full coach/science plan.
- Existing generated workbook is reference only.
- Privacy model is hybrid.
- Manual feedback is YAML per workout, CSVs are derived.
- Missing feedback allows best-effort recommendations with explicit confidence/missing evidence.
- Sunday 2026-05-31 10K uses controlled aggressive strategy.
- System updates after each workout.
- Weekly summaries are derived automatically.
- Formal reports every 30 days.
- Weekly baseline is Monday strength, Tuesday run, Wednesday volleyball, Thursday run, Friday strength, Saturday optional strength, Sunday run/race/long run.
- Bruna performance is prioritized, with Matheus pacing only within Achilles safety.
- Achilles policy is moderate: 3/10 removes intensity, 5/10 recommends off/cross-training.
- Strength training is tracked as running-relevant load, not full gym programming.
- LLM recommendations are guardrailed and must cite approved science.
- Projections use conservative, realistic, and aggressive scenarios.
- Half-marathon target starts as a hypothesis, not an official fixed goal.
- Normal decisions use concise logs; major decisions use RCA format.
