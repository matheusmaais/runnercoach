# Running Coach System

Sistema pessoal de acompanhamento, analise e recomendacao conservadora de treinos de corrida para Matheus e Bruna, com Git como fonte oficial, frontend GitHub Pages como interface principal e dashboard operacional em planilha como apoio.

O V1 foca em contratos confiaveis: importar Garmin, preservar a verdade de propriedade dos dados, capturar feedback manual, gerar dados processados, registrar decisoes auditaveis, atualizar relatorios e construir `reports/dashboard.xlsx`.

Dashboard Google Sheets persistente:

- [Projeto Meia Forte Janeiro 2027 — Matheus & Bruna](https://docs.google.com/spreadsheets/d/1NYrPxauwysUgE4Hm0Kt-F7Kc9OkziGablhC6zHXDM4o)
- Detalhes de sync: `docs/google-sheets.md`

Frontend principal:

- `web/`: Performance Lab estatico para GitHub Pages.
- `web/public/data/app-data.json`: payload versionado gerado pelo pipeline.

## V1 Workflow

1. Export Garmin activities CSV.
   - Na pratica: exporte o CSV de atividades do Garmin.
2. Salve o arquivo localmente como `data/raw/garmin/Activities.csv`.
3. Adicione ou atualize o check-in YAML em `data/manual/checkins/`.
4. Rode:

```bash
make pipeline GARMIN=data/raw/garmin/Activities.csv
make coach
make dashboard
make frontend
```

5. Revise:

- `reports/latest-summary.md`
- `reports/dashboard.xlsx`
- `web/public/data/app-data.json`
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
make coach
make dashboard
make frontend-data
make frontend-build
make test
```

Direct script equivalents:

```bash
python scripts/run_pipeline.py --garmin data/raw/garmin/Activities.csv --after-workout
python scripts/generate_recommendation.py
python scripts/build_dashboard.py
python scripts/build_frontend_data.py
```

If the system Python does not have the dependencies from `pyproject.toml`, create a local venv and run the same commands through it:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
PYTHON=.venv/bin/python make test
PYTHON=.venv/bin/python make pipeline GARMIN=data/raw/garmin/Activities.csv
PYTHON=.venv/bin/python make coach
PYTHON=.venv/bin/python make dashboard
PYTHON=.venv/bin/python make frontend-data
```

## Frontend Workflow

V1.5 adiciona o Performance Lab, uma interface estatica moderna para consultar o sistema sem abrir a planilha.

Gerar apenas os dados do frontend:

```bash
PYTHON=.venv/bin/python make frontend-data
```

Instalar dependencias web e gerar build local:

```bash
cd web
npm install
npm run build
```

Ou rode tudo pelo Makefile:

```bash
PYTHON=.venv/bin/python make frontend
```

Rodar localmente:

```bash
cd web
npm run dev
```

O frontend le apenas `web/public/data/app-data.json`. Toda regra de seguranca, separacao Matheus/Bruna e normalizacao de evidencia deve vir do Python antes da UI renderizar.

Contrato V1.5:

- O frontend e a interface principal de leitura.
- Ele nao edita dados, nao faz upload de Garmin, nao chama LLM direto do browser e nao comita no repo.
- A chave de LLM nunca deve ficar no GitHub Pages.

Proximo passo recomendado:

- V1.6 deve transformar o frontend em interface operacional usando GitHub Actions como backend seguro.
- O browser coleta check-in/upload, dispara workflow, o Actions roda Python + LLM com secrets, valida a resposta, commita os artefatos e republica o Pages.

Publicacao:

- `.github/workflows/pages.yml` gera o payload, compila `web/` e publica `web/dist` no GitHub Pages.
- Em GitHub Pages, configure a origem como "GitHub Actions".

## LLM Coach Workflow

V1.4 adds an auditable LLM context package. It does not blindly call an API or let an LLM override safety guardrails.

Run:

```bash
PYTHON=.venv/bin/python make coach
```

Review:

- `reports/llm/latest-request.md`
- `reports/llm/latest-request.json`

Use `latest-request.md` as the prompt/context for Codex or another LLM. If an LLM returns structured JSON, validate it with:

```bash
PYTHON=.venv/bin/python scripts/generate_recommendation.py --response path/to/response.json
```

Only validated responses produce `reports/llm/latest-recommendation.md`.

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
- `reports/llm/`: auditable LLM request and validated recommendation artifacts.
- `docs/google-sheets.md`: persistent Google Sheets dashboard ID and sync notes.
- `web/`: GitHub Pages frontend.
- `scripts/`: re-runnable command entrypoints.
- `src/running_coach/`: typed models, Garmin ingestion, pipeline, science registry, recommendations, and dashboard generation.
