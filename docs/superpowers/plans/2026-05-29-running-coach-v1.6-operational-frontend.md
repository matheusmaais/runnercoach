# Running Coach V1.6 Operational Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the GitHub Pages frontend operational for data entry, GitHub versioning, workflow dispatch, and secure LLM-backed recommendation generation.

**Architecture:** The browser commits versioned intake JSON files and dispatches GitHub Actions. GitHub Actions owns persistence, Python pipeline execution, LLM calls via repository secrets, validation, commits, and Pages rebuild.

**Tech Stack:** React/TypeScript, GitHub REST API, GitHub Actions, Python, PyYAML, pytest, Playwright, OpenAI Responses API via GitHub Actions secret.

---

## Task 1: Intake Processor

**Files:**
- Create: `src/running_coach/operational.py`
- Create: `scripts/process_frontend_intake.py`
- Create: `tests/test_operational_intake.py`

**DoD:** A frontend intake JSON can be validated and materialized into the existing check-in YAML schema.

## Task 2: Secure LLM Action Script

**Files:**
- Create: `scripts/call_openai_recommendation.py`
- Test: `tests/test_operational_intake.py`

**DoD:** The script reads `reports/llm/latest-request.json`, calls the OpenAI Responses API only when `OPENAI_API_KEY` is present, extracts JSON text, and validates it through the existing local LLM validator.

## Task 3: Operational Workflow

**Files:**
- Create: `.github/workflows/operational-intake.yml`

**DoD:** The workflow accepts an intake path, processes it, runs pipeline/coaching/dashboard/frontend generation, optionally calls LLM, commits results, and deploys Pages.

## Task 4: Frontend Operar View

**Files:**
- Modify: `web/src/App.tsx`
- Modify: `web/src/styles.css`
- Modify: `web/src/types.ts`
- Create: `web/src/github.ts`
- Create: `web/src/operational.ts`
- Modify: `web/tests/app.spec.ts`

**DoD:** The UI builds an intake payload, validates required fields, commits to GitHub, dispatches the workflow, and never asks for or stores an LLM key.

## Task 5: Documentation And QA

**Files:**
- Modify: `README.md`
- Modify: `web/tests/app.spec.ts`

**DoD:** README documents token permissions, secret setup, daily FE-only workflow, and all automated checks pass.
