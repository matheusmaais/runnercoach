## Persistent Dashboard

The persistent Google Sheets dashboard for this project is:

- Name: Projeto Meia Forte Janeiro 2027 — Matheus & Bruna
- Spreadsheet ID: `1NYrPxauwysUgE4Hm0Kt-F7Kc9OkziGablhC6zHXDM4o`
- URL: https://docs.google.com/spreadsheets/d/1NYrPxauwysUgE4Hm0Kt-F7Kc9OkziGablhC6zHXDM4o

It was created by importing the generated workbook `reports/dashboard.xlsx` as a native Google Sheets file.

## Update Workflow

1. Run the local pipeline:

```bash
PYTHON=.venv/bin/python make pipeline GARMIN=data/raw/garmin/Activities.csv
PYTHON=.venv/bin/python make dashboard
```

2. Import or replace the Google Sheets dashboard from `reports/dashboard.xlsx`.
3. Keep this file updated if the Google Sheets ID changes.

## Source Of Truth

Git remains the source of truth. Google Sheets is the operational interface.

If Google Sheets and Git disagree, regenerate `reports/dashboard.xlsx` from the repo and re-sync the Sheet.

## Current Limitation

V1 creates the persistent native Google Sheets dashboard, but automated in-place Sheet replacement is still a manual connector step. The stable artifact for repeatable sync is `reports/dashboard.xlsx`.
