# Running Coach V1.5 Frontend Design

Date: 2026-05-29
Status: Approved direction, ready for implementation planning

## Objective

Build a premium GitHub Pages interface for the Matheus and Bruna running coach system. The frontend must feel like a personal training platform, not a generic spreadsheet skin, while preserving the repository as the source of truth and keeping all recommendations auditable.

V1.5 does not replace the Python pipeline, Google Sheets dashboard, or LLM package. It becomes a polished read-only product surface over the same versioned data.

V1.5 is the primary human interface for reading the system. It is not yet the write interface for adding new Garmin CSVs, Bruna screenshots, manual check-ins, or LLM approvals. Those workflows remain CLI/Git for this version.

The intended next product step is V1.6 Operational Frontend:

1. GitHub Pages presents forms and upload controls.
2. The browser dispatches GitHub Actions through the GitHub API.
3. GitHub Actions runs the Python pipeline.
4. LLM calls run only inside GitHub Actions using repository secrets.
5. Generated recommendations are validated, committed back to the repository, and GitHub Pages rebuilds.

This preserves Git as source of truth while letting Matheus use the frontend as the daily product surface.

## Product Direction

The product concept is a Performance Lab for the January 2027 half marathon mission.

The first screen is an operational cockpit, not a landing page. Within seconds it must answer:

- Are Matheus and Bruna improving?
- Are they carrying too much fatigue?
- What is the current risk level?
- What is the next coherent workout?
- Are they still on track for a strong half marathon in late January 2027?

The design must be modern, dense enough for repeated use, and specific to the athletes. It must explicitly show when evidence is complete, partial, missing, or athlete-specific.

## Non-Negotiable Data Contracts

Garmin biometric and running dynamics data always belongs to Matheus:

- Garmin heart rate
- Garmin cadence
- Garmin power
- Garmin ground contact
- Garmin vertical oscillation
- Garmin stride length

Shared pace, distance, and elapsed time may apply to both athletes when they run together.

Bruna must be evaluated from:

- Shared pace, distance, and time
- Bruna manual heart rate when provided
- Bruna PSE
- Symptoms and subjective report
- Sleep, soreness, volleyball, gym, menstrual context when voluntarily provided
- Recovery context and whether she felt she could repeat the effort

The frontend must never imply that Matheus-only speed or heart rate is Bruna evidence. Matheus solo performance may be shown as residual speed for pacer context only.

## Recommended Architecture

Use a static React/Vite application deployed to GitHub Pages.

Data flow:

1. Existing CSV, Markdown, report, and LLM artifacts remain versioned inputs.
2. A Python exporter builds one derived frontend payload at `web/public/data/app-data.json`.
3. The frontend consumes only that JSON file at runtime.
4. GitHub Actions builds the frontend and deploys the static site to GitHub Pages.

This keeps parsing, evidence normalization, and athlete-specific safety logic in Python, where tests already exist. The browser layer focuses on presentation and interaction.

## Frontend Sections

### 1. Cockpit

The cockpit is the default view.

It contains:

- Mission header: "Meia Forte Janeiro 2027".
- Current phase and week.
- Training status card: on track, cautious, or reduce.
- Next workout card with decision: maintain, reduce, alter, or recover.
- Bruna performance state with current pace ranges and evidence confidence.
- Matheus pacer health state with Achilles status and intensity restrictions.
- Risk and fatigue strip using conservative language.
- Quick links to Coach Room, Timeline, Plan, and Science.

### 2. Timeline

The timeline shows workouts and races as evidence objects.

Each item includes:

- Date, type, distance, duration, average pace.
- Athlete context: shared, Matheus solo, Bruna manual evidence, race, check-in.
- Badges such as `garmin_matheus`, `shared_pace`, `bruna_hr_manual`, `all_out`, `volleyball_load`, `sleep_risk`, `achilles_watch`.
- Decision after workout.
- Evidence confidence.

Matheus solo efforts must be visually separated from Bruna progression.

### 3. Plan

The plan view explains coherence.

It contains:

- Current roadmap phase.
- Next planned workouts.
- Why each workout exists.
- What would cause reduction or alteration.
- 30-day review checkpoint.
- Path toward 10K improvement and January 2027 half marathon specificity.

The plan must avoid random workout suggestions. Each upcoming session needs a visible link to current state, prior workout, phase, and safety rules.

### 4. Coach Room

The Coach Room exposes the LLM decision package without pretending the LLM is the source of truth.

It contains:

- Latest generated coaching request summary.
- Guardrails and forbidden inferences.
- Evidence gaps.
- Approved science references used by the recommendation layer.
- Human-review status.

The UI must make it obvious that Codex or another LLM can analyze the package, but deterministic pipeline rules own the safety contract.

### 5. Science & Decisions

This view contains:

- Approved science references with source, topic, and practical interpretation.
- Decision log with date, event, evidence, decision, and impact.
- Safety principles that affect Matheus and Bruna.

It must separate scientific basis from manual feedback and subjective check-ins.

## Visual System

The frontend should feel premium and athletic, but not loud.

Palette:

- Charcoal and near-black foundations.
- Deep navy accents used sparingly.
- Teal and green for progress and readiness.
- Amber for caution.
- Red only for real risk.
- Light gray and off-white for readable surfaces.

Layout:

- Full-screen app shell, no marketing hero.
- Compact top navigation.
- Dense but calm cockpit cards.
- Clear state badges.
- Strong typographic hierarchy without oversized decorative headings inside panels.
- No nested cards.
- No generic gradient blobs or ornamental backgrounds.

Charts:

- Pace trend.
- Long run progression.
- Weekly volume.
- Quality sessions per week.
- Strong sustainable pace trend.
- Risk/fatigue trend.
- Projection cards for 10K and half marathon where evidence permits conservative display.

## Data Payload Shape

The frontend payload should include:

- `generated_at`
- `mission`
- `athletes`
- `current_state`
- `next_workouts`
- `recent_workouts`
- `races`
- `weekly_summary`
- `trends`
- `decisions`
- `science_refs`
- `llm_context`
- `evidence_contracts`
- `presentation_warnings`

The payload should be deterministic for the same input files except for explicitly versioned generated timestamps already present in source artifacts.

## Error Handling

If the JSON payload is missing or invalid, the app must show a clear empty state explaining that the frontend data needs to be rebuilt.

If sections are missing data, the UI must show partial evidence states rather than invent values.

If Bruna manual evidence is absent for a shared workout, the UI may show shared pace but must show Bruna HR/PSE as missing.

## Testing And Verification

Python tests must cover:

- Payload generation from current fixture data.
- Required top-level keys.
- Matheus-only data is not exposed as Bruna biometric evidence.
- Latest shared workout and latest Matheus solo workout remain distinct.
- Science references are included with source links.
- Next workouts are present and tied to decisions.

Frontend checks must cover:

- TypeScript build.
- Static production build.
- Desktop browser rendering.
- Mobile browser rendering.
- No blank screen when `app-data.json` exists.
- Visible cockpit, timeline, plan, coach, and science navigation.

Visual QA must inspect desktop and mobile screenshots before completion.

## Out Of Scope For V1.5

- Editing workouts in the browser.
- Uploading screenshots in the browser.
- Authentication.
- Backend database.
- Automatic Garmin API sync.
- Automatic LLM API calls from the frontend.

The frontend must not expose an LLM API key or call an LLM directly from the browser. Future LLM calls must run from GitHub Actions, local CLI, or another trusted backend.

Those belong to later versions after the read-only product surface is stable.

## Definition Of Done

V1.5 is complete when:

- `web/` contains a production-ready GitHub Pages frontend.
- A Python command generates `web/public/data/app-data.json`.
- A single make target can build frontend data and the web app.
- GitHub Pages workflow exists.
- Tests prove the athlete evidence boundaries.
- Frontend build passes.
- Browser QA verifies desktop and mobile rendering.
- README documents the local and publish workflow.
- The repository has no accidental generated noise staged.
