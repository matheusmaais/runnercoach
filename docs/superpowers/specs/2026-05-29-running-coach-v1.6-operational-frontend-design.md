# Running Coach V1.6 Operational Frontend Design

Date: 2026-05-29
Status: Approved by goal

## Objective

Turn the GitHub Pages frontend into the daily operating surface for the running coach system. Matheus should be able to add new workout context, upload Garmin CSV data, request analysis, and receive updated recommendations without using Google Sheets or this chat in normal use.

## Architecture

GitHub Pages remains a static frontend. It must not store private API secrets or call the LLM provider directly.

Operational flow:

1. The frontend collects an intake form and optional Garmin CSV file.
2. Matheus provides a fine-grained GitHub token in the browser for repository writes and workflow dispatch.
3. The frontend commits an intake JSON file under `data/manual/frontend_intake/`.
4. The frontend dispatches `.github/workflows/operational-intake.yml` with the intake path.
5. GitHub Actions materializes versioned check-in YAML and a temporary Garmin CSV file.
6. GitHub Actions runs the Python pipeline, generates the LLM request, optionally calls OpenAI using `OPENAI_API_KEY`, validates the response, rebuilds frontend data, commits generated artifacts, and republishes GitHub Pages.

## Security Boundary

- `OPENAI_API_KEY` must only exist as a GitHub Actions secret.
- The browser must never send data directly to OpenAI.
- The GitHub token is a user-provided local browser credential, not committed or embedded.
- The token should be fine-grained and limited to the runnercoach repository with Contents write and Actions write permissions.
- Intake files are auditable repository inputs.
- Generated recommendations are auditable repository outputs.

## Frontend Experience

Add an `Operar` view to the existing Performance Lab.

The view contains:

- GitHub connection panel:
  - owner
  - repo
  - branch
  - token
  - save locally toggle/action
- Workout intake form:
  - date
  - Garmin activity ID/title/datetime
  - planned type
  - actual type
  - shared run
  - Bruna avg/max HR
  - Bruna PSE
  - symptoms
  - sleep
  - volleyball previous day
  - gym previous day
  - lower-body load
  - subjective note
  - could repeat last block
  - Matheus Achilles morning/after
  - Matheus role/note
  - coach note
- Garmin CSV upload:
  - read locally
  - base64 encode in intake JSON
  - do not display full raw CSV in the UI
  - required for operational analysis because raw Garmin files are intentionally not versioned
- Action buttons:
  - validate draft
  - commit intake
  - dispatch analysis workflow

## Workflow Behavior

The workflow accepts:

- `intake_path`
- `run_llm`
- `commit_results`

If `run_llm=true` and `OPENAI_API_KEY` exists, the workflow calls the Responses API and validates the returned JSON against the local LLM schema.

If `OPENAI_API_KEY` is missing, the workflow still commits deterministic pipeline outputs and LLM request artifacts, then records that recommendation generation is pending.

## Data Contracts

The intake JSON schema is versioned:

- `schema_version: 1`
- `created_at`
- `source: github_pages`
- `checkin`
- `garmin_csv`
- `workflow`

The processor writes check-ins using the existing `data/manual/checkins/*.yaml` schema so the rest of the pipeline remains unchanged.

Garmin CSV contents are temporary workflow inputs. Raw Garmin CSV remains ignored by git.

## Definition Of Done

V1.6 is complete when:

- The frontend has an `Operar` view that builds a valid intake payload.
- The frontend can commit the intake JSON through the GitHub Contents API.
- The frontend can dispatch the operational workflow.
- The operational workflow exists and runs the pipeline.
- A Python script materializes intake JSON into existing check-in YAML.
- LLM calls are implemented only in GitHub Actions/local CLI, never in the browser.
- Tests cover intake validation and materialization.
- Playwright covers the operational form and payload validation path.
- README documents required GitHub token permissions and `OPENAI_API_KEY`.
