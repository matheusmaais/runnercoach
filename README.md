# Running Coach System

Sistema pessoal de acompanhamento, analise e recomendacao conservadora de treinos de corrida para Matheus e Bruna, com Git como fonte oficial e dashboard operacional em planilha.

O V1 foca em contratos confiaveis: importar Garmin, preservar a verdade de propriedade dos dados, capturar feedback manual, gerar dados processados, registrar decisoes auditaveis, atualizar relatorios e construir `reports/dashboard.xlsx`.

Dashboard Google Sheets persistente:

- [Projeto Meia Forte Janeiro 2027 — Matheus & Bruna](https://docs.google.com/spreadsheets/d/1NYrPxauwysUgE4Hm0Kt-F7Kc9OkziGablhC6zHXDM4o)
- Detalhes de sync: `docs/google-sheets.md`

## V1 Workflow

1. Export Garmin activities CSV.
   - Na pratica: exporte o CSV de atividades do Garmin.
2. Salve o arquivo localmente como `data/raw/garmin/Activities.csv`.
3. Adicione ou atualize o check-in YAML em `data/manual/checkins/`.
4. Rode:

```bash
make pipeline GARMIN=data/raw/garmin/Activities.csv
make dashboard
```

5. Revise:

- `reports/latest-summary.md`
- `reports/dashboard.xlsx`
- `docs/state.md`
- `docs/decisions.md`

## Data Truth

Garmin HR, cadence, power, ground contact, vertical oscillation, and stride length belong to Matheus only.

Shared pace, distance, and time can apply to Bruna only when `shared_run=true` and `bruna_present=true`.

If a workout has only Garmin data and no matched check-in, the system must treat Bruna evidence as missing. It must not infer Bruna HR, PSE, symptoms, readiness, or performance from Matheus-only Garmin fields.

## Key Commands

```bash
make ingest GARMIN=data/raw/garmin/Activities.csv
make pipeline GARMIN=data/raw/garmin/Activities.csv
python scripts/run_pipeline.py --garmin data/raw/garmin/Activities.csv --after-workout --monthly-report
make dashboard
make test
```

Direct script equivalents:

```bash
python scripts/run_pipeline.py --garmin data/raw/garmin/Activities.csv --after-workout
python scripts/build_dashboard.py
```

If the system Python does not have the dependencies from `pyproject.toml`, create a local venv and run the same commands through it:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
PYTHON=.venv/bin/python make test
PYTHON=.venv/bin/python make pipeline GARMIN=data/raw/garmin/Activities.csv
PYTHON=.venv/bin/python make dashboard
```

## Current Operating Model

- Running pattern: Tuesday, Thursday, Sunday.
- Strength pattern: Monday, Friday, sometimes Saturday.
- Volleyball: usually Wednesday, and it counts as neuromuscular load.
- Long run remains easy.
- Quality work remains controlled.
- Missed workouts are not compensated with extra volume.
- Matheus is primarily a healthy pacer; Achilles risk overrides pace ambition.
- Bruna is evaluated from shared pace/distance/time plus manual PSE, symptoms, recovery, sleep, volleyball/gym context, and HR only when manually provided.

## Repository Layout

- `data/raw/garmin/`: local Garmin exports. Raw CSV files are intentionally ignored.
- `data/manual/checkins/`: manual after-workout context and screenshot evidence pointers.
- `data/knowledge/science_refs.yaml`: canonical approved science registry.
- `data/processed/`: generated CSV outputs.
- `docs/`: state, decisions, roadmap, operating manual, principles, athlete profiles, science basis.
- `reports/`: latest summary, charts, and generated dashboard workbook.
- `docs/google-sheets.md`: persistent Google Sheets dashboard ID and sync notes.
- `scripts/`: re-runnable command entrypoints.
- `src/running_coach/`: typed models, Garmin ingestion, pipeline, science registry, recommendations, and dashboard generation.
