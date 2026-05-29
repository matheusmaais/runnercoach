# Running Coach V1.5 Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a premium GitHub Pages frontend that becomes the primary read-only interface for the Matheus and Bruna running coach system.

**Architecture:** Python remains responsible for data normalization, evidence boundaries, safety contracts, and generation of a deterministic frontend payload. React/Vite renders that payload as a static app deployable to GitHub Pages. Tests and browser QA must prove the UI does not blur Matheus-only Garmin evidence into Bruna analysis.

**Tech Stack:** Python 3.14 project modules, pytest, React, TypeScript, Vite, Recharts, Playwright, GitHub Actions Pages.

**Product Boundary:** V1.5 is the primary read interface. It does not write check-ins, upload Garmin CSVs, call LLM APIs from the browser, or commit data. V1.6 should add an operational frontend backed by GitHub Actions so secrets and repository writes stay outside GitHub Pages.

---

## File Map

- Create `src/running_coach/frontend_data.py`: build the `app-data.json` payload from processed CSVs, LLM request, science refs, and reports.
- Create `scripts/build_frontend_data.py`: CLI wrapper for payload generation.
- Create `tests/test_frontend_data.py`: payload contract tests.
- Modify `Makefile`: add `frontend-data`, `frontend-build`, and `frontend` targets.
- Modify `README.md`: document frontend workflow and GitHub Pages usage.
- Create `web/`: React/Vite application and Playwright tests.
- Create `.github/workflows/pages.yml`: GitHub Pages build and deploy workflow.

## Task 1: Frontend Payload Contract

**Files:**
- Create: `src/running_coach/frontend_data.py`
- Create: `scripts/build_frontend_data.py`
- Create: `tests/test_frontend_data.py`

- [ ] **Step 1: Write payload tests**

Tests must assert:

- Required top-level keys exist.
- Latest shared workout and latest Matheus solo workout are distinct.
- Matheus solo pace is not exposed as Bruna progress evidence.
- Bruna biometric fields are marked missing when no manual check-in exists.
- Science references and next planned workouts are included.

- [ ] **Step 2: Run the new tests and confirm they fail before implementation**

Run: `PYTHON=.venv/bin/python .venv/bin/python -m pytest tests/test_frontend_data.py -q`

Expected: fail because `running_coach.frontend_data` does not exist.

- [ ] **Step 3: Implement the payload builder**

Implementation must read:

- `data/processed/workouts.csv`
- `data/processed/decisions.csv`
- `data/processed/science_refs.csv`
- `data/processed/plan_status.csv`
- `reports/llm/latest-request.json`
- `docs/state.md`
- `docs/roadmap.md`

The exported JSON must contain:

- `generated_at`
- `mission`
- `athletes`
- `current_state`
- `next_workouts`
- `recent_workouts`
- `weekly_summary`
- `trends`
- `decisions`
- `science_refs`
- `llm_context`
- `evidence_contracts`
- `presentation_warnings`

- [ ] **Step 4: Add CLI wrapper**

Run: `PYTHON=.venv/bin/python python scripts/build_frontend_data.py`

Expected: writes `web/public/data/app-data.json` and prints the output path.

- [ ] **Step 5: Run tests**

Run: `PYTHON=.venv/bin/python .venv/bin/python -m pytest tests/test_frontend_data.py -q`

Expected: pass.

**Definition of Done:** Payload exists, tests prove athlete evidence boundaries, and the CLI can regenerate the JSON.

## Task 2: Static Web App Scaffold

**Files:**
- Create: `web/package.json`
- Create: `web/index.html`
- Create: `web/vite.config.ts`
- Create: `web/tsconfig.json`
- Create: `web/tsconfig.node.json`
- Create: `web/src/main.tsx`
- Create: `web/src/App.tsx`
- Create: `web/src/types.ts`
- Create: `web/src/data.ts`
- Create: `web/src/styles.css`

- [ ] **Step 1: Create Vite React TypeScript scaffold**

Use dependencies:

- `@vitejs/plugin-react`
- `vite`
- `typescript`
- `react`
- `react-dom`
- `recharts`
- `lucide-react`
- `@playwright/test`

- [ ] **Step 2: Build data loader**

The app must fetch `${import.meta.env.BASE_URL}data/app-data.json`.

If fetch fails, render a clear rebuild-data empty state.

- [ ] **Step 3: Build production bundle**

Run: `cd web && npm install && npm run build`

Expected: Vite production build succeeds.

**Definition of Done:** A static React app builds and can load the generated payload from `web/public/data/app-data.json`.

## Task 3: Premium Product UI

**Files:**
- Modify: `web/src/App.tsx`
- Modify: `web/src/styles.css`
- Modify: `web/src/types.ts`

- [ ] **Step 1: Implement app shell**

Sections:

- Cockpit
- Timeline
- Plano
- Coach Room
- Ciencia & Decisoes

- [ ] **Step 2: Implement cockpit**

Cockpit must show:

- Mission status.
- Next workout.
- Bruna pace state and evidence confidence.
- Matheus Achilles/pacer state.
- Risk/fatigue.
- 10K and half marathon projection placeholders only when evidence allows conservative display.

- [ ] **Step 3: Implement timeline**

Timeline must show athlete context badges and explicitly label Matheus-only efforts.

- [ ] **Step 4: Implement plan and coach room**

Plan must link next workouts to phase, reason, and safety triggers. Coach Room must expose LLM guardrails, forbidden claims, evidence gaps, and science-backed constraints.

- [ ] **Step 5: Implement science and decisions**

Show approved references and decision log separately from manual feedback.

**Definition of Done:** The UI is visually premium, coherent, domain-specific, and makes evidence confidence visible.

## Task 4: GitHub Pages And Workflow

**Files:**
- Modify: `Makefile`
- Create: `.github/workflows/pages.yml`
- Modify: `README.md`

- [ ] **Step 1: Add make targets**

Targets:

- `frontend-data`
- `frontend-build`
- `frontend`

- [ ] **Step 2: Add GitHub Pages workflow**

Workflow must:

- Check out the repo.
- Set up Python.
- Install the package.
- Generate frontend data.
- Set up Node.
- Install web dependencies.
- Build web.
- Upload `web/dist`.
- Deploy to GitHub Pages.

- [ ] **Step 3: Document local and publish workflow**

README must include:

- `make frontend-data`
- `make frontend-build`
- `make frontend`
- GitHub Pages publishing note.

**Definition of Done:** Local and CI publish paths are documented and executable.

## Task 5: Browser QA And Completion Audit

**Files:**
- Create: `web/tests/app.spec.ts`
- Modify: `web/package.json`

- [ ] **Step 1: Add Playwright smoke tests**

Tests must assert:

- Cockpit renders.
- Timeline renders.
- Plano renders.
- Coach Room renders.
- Ciencia & Decisoes renders.
- Matheus solo warning is visible.
- Bruna evidence confidence is visible.

- [ ] **Step 2: Run full verification**

Commands:

- `PYTHON=.venv/bin/python .venv/bin/python -m pytest -q`
- `PYTHON=.venv/bin/python python scripts/build_frontend_data.py`
- `cd web && npm run build`
- `cd web && npx playwright install chromium`
- `cd web && npm run test:e2e`

- [ ] **Step 3: Inspect desktop and mobile render**

Use browser or Playwright screenshots for:

- Desktop 1440px wide.
- Mobile 390px wide.

Check:

- No blank screen.
- No overlapping text.
- Navigation usable.
- Cards do not imply wrong athlete ownership.
- Main cockpit answers the operational questions quickly.

**Definition of Done:** All automated checks pass, visual/browser QA is inspected, and repo status contains only intentional V1.5 files.

## V1.6 Follow-Up Contract

The next implementation plan should add:

- A GitHub-authenticated frontend flow for manual check-ins.
- A Garmin CSV upload flow that opens a GitHub Actions workflow dispatch.
- Screenshot metadata capture for Bruna HR evidence without storing secrets in the browser.
- A GitHub Actions workflow that runs pipeline, LLM recommendation, validation, commit, and Pages rebuild.
- A human approval state for recommendations before they become official training decisions.
