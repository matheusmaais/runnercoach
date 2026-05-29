# Running Coach V1.4 LLM Layer Plan

## Goal

Add an auditable LLM recommendation layer without weakening deterministic safety guardrails.

V1.4 must let Codex or a future API-backed LLM analyze the latest processed data through a repeatable command, while Git remains the source of truth and missing evidence remains explicit.

## Non-Negotiable Contracts

- Garmin physiology remains Matheus-only.
- Bruna recommendations must use shared pace only when `shared_run=true` and `bruna_present=true`.
- Red flags, high PSE, poor sleep, volleyball load, and Achilles thresholds stay deterministic guardrails.
- LLM output is advisory until it passes schema and safety validation.
- LLM output cannot invent HR, symptoms, zones, races, or medical conclusions.
- All cited science refs must exist in `data/knowledge/science_refs.yaml` and be `approved=true`.

## V1.4 Deliverables

- `src/running_coach/llm.py`: context package builder and LLM response validator.
- `scripts/generate_recommendation.py`: CLI for request generation and response validation.
- `reports/llm/latest-request.md`: prompt/context package for Codex/LLM.
- `reports/llm/latest-request.json`: machine-readable context package.
- `reports/llm/latest-recommendation.md`: generated only when a response is validated.
- `tests/test_llm.py`: contract tests.
- `Makefile`: `coach` command.
- Docs updated to explain the LLM workflow.

## Task 1: LLM Request Contract

**Files**

- Create: `src/running_coach/llm.py`
- Create: `tests/test_llm.py`

**Definition of Done**

- Request builder loads processed workouts, decisions, plan status, science registry, and docs/state.
- Latest shared workout and latest Matheus solo workout are separated.
- Prompt contains explicit forbidden claims.
- JSON context includes `schema_version`, `generated_at`, `athletes`, `data_contract`, `latest_shared_workout`, `latest_matheus_solo`, `next_planned_workouts`, `approved_science_refs`, `required_response_schema`.
- Tests prove Matheus solo 4:22 is not represented as Bruna evidence.

## Task 2: LLM Response Validation

**Files**

- Modify: `src/running_coach/llm.py`
- Modify: `tests/test_llm.py`

**Definition of Done**

- Validator accepts a strict structured response.
- Validator rejects unknown fields, missing required fields, unapproved science refs, invented evidence, and unsafe actions that violate deterministic guardrails.
- Valid response renders Markdown and CSV-safe data.

## Task 3: CLI And Reports

**Files**

- Create: `scripts/generate_recommendation.py`
- Modify: `Makefile`
- Generate: `reports/llm/latest-request.md`
- Generate: `reports/llm/latest-request.json`

**Definition of Done**

- `make coach` writes the latest LLM request artifacts.
- CLI can validate a local response JSON with `--response`.
- Command exits non-zero on invalid responses.
- Tests cover request generation and validation flow without external network calls.

## Task 4: Docs And Gate

**Files**

- Modify: `README.md`
- Modify: `docs/operating-manual.md`

**Definition of Done**

- Docs explain that V1.4 LLM is context-pack + validation, not blind automation.
- Docs explain how Codex can use `reports/llm/latest-request.md`.
- Gate passes:

```bash
PYTHON=.venv/bin/python make test
PYTHON=.venv/bin/python make pipeline GARMIN=data/raw/garmin/Activities.csv
PYTHON=.venv/bin/python make coach
```

## Stop Rule

Do not add live OpenAI API calls in V1.4. The next safe step is a validated prompt/response contract. API transport can be V1.5 once the response schema and safety gates are proven.
