## Overview

Este manual descreve como operar o V1 do sistema de corrida de Matheus e Bruna. O repositorio e a fonte oficial; a planilha gerada em `reports/dashboard.xlsx` e o painel visual para leitura rapida.

O sistema e conservador por desenho. Quando falta contexto subjetivo, ele registra baixa confianca e pede resolucao manual em vez de inventar uma recomendacao. Isso e especialmente importante porque o Garmin esta no pulso do Matheus, enquanto Bruna precisa ser interpretada por pace compartilhado, PSE, sintomas, recuperacao e HR manual quando existir.

## After Each Workout

Depois de cada corrida, faca tres coisas:

1. Exporte ou atualize `data/raw/garmin/Activities.csv`.
2. Crie ou edite um YAML em `data/manual/checkins/` para a atividade relevante.
3. Rode o pipeline e o dashboard.

O check-in deve registrar o `activity_match.activity_id` do Garmin quando houver correspondencia. Para treino conjunto, use `session.shared_run: true`, preencha a secao `bruna`, e mantenha `matheus.role: pacer` quando Matheus correu para guiar Bruna.

Campos essenciais para decisao:

- Bruna: `pse`, `symptoms`, `sleep_quality`, `volleyball_previous_day`, `gym_previous_day`, `could_repeat_last_block`.
- Matheus: `achilles_morning`, `achilles_after`, `role`.
- Evidencia ausente: mantenha em `missing_evidence` tudo que ainda nao foi capturado.
- Notas de treinador: use `coach_notes.decision_after_workout` para registrar a decisao humana do dia.

## Adding Bruna HR Screenshot Evidence

Quando Bruna enviar screenshot do Galaxy Watch, salve o arquivo em um caminho versionado de evidencia manual, preferencialmente junto do check-in ou em uma subpasta dedicada de anexos manuais.

No YAML do check-in:

- Preencha `attachments.bruna_hr_screenshot` com o caminho do arquivo.
- Preencha `attachments.bruna_hr_screenshot_sha256` com o hash do arquivo.
- Preencha `bruna.avg_hr` e `bruna.max_hr` apenas se o screenshot mostrar esses valores com clareza.
- Remova `bruna_hr_screenshot`, `bruna_avg_hr` e `bruna_max_hr` de `missing_evidence` somente depois da conferencia.

Se o screenshot estiver cortado, ilegivel ou ambivalente, preserve a pendencia. O sistema deve preferir baixa confianca a uma frequencia cardiaca inventada.

## Running The Pipeline

Fluxo padrao:

```bash
make pipeline GARMIN=data/raw/garmin/Activities.csv
make dashboard
```

Fluxo direto equivalente:

```bash
python scripts/run_pipeline.py --garmin data/raw/garmin/Activities.csv --after-workout
python scripts/build_dashboard.py
```

O pipeline gera ou atualiza:

- `data/processed/activities.csv`
- `data/processed/workouts.csv`
- `data/processed/decisions.csv`
- `data/processed/science_refs.csv`
- `docs/state.md`
- `docs/decisions.md`
- `reports/latest-summary.md`

O dashboard local gera:

- `reports/dashboard.xlsx`

O dashboard Google Sheets persistente esta registrado em `docs/google-sheets.md`:

- https://docs.google.com/spreadsheets/d/1NYrPxauwysUgE4Hm0Kt-F7Kc9OkziGablhC6zHXDM4o

Git continua sendo a fonte oficial; Google Sheets e a interface operacional.

## Reviewing Recommendations

No V1, a recomendacao automatica e deliberadamente conservadora. Quando falta check-in, PSE, sintomas, HR manual de Bruna ou contexto de recuperacao, a saida esperada e baixa confianca ou resolucao manual.

Revise nesta ordem:

1. `reports/latest-summary.md` para resumo rapido.
2. `docs/state.md` para estado operacional atual.
3. `docs/decisions.md` para decisoes registradas.
4. `reports/dashboard.xlsx` para painel visual.
5. `data/processed/workouts.csv` quando precisar auditar uma linha especifica.

Uma decisao so deve ser tratada como acionavel quando a evidencia do treino estiver coerente com o contrato de dados. Treino Garmin solo do Matheus nao deve virar sinal positivo de evolucao da Bruna.

## LLM Coach Workflow

V1.4 adiciona uma camada LLM auditavel por pacote de contexto. O sistema nao chama uma API automaticamente e nao permite que a LLM substitua os guardrails deterministas.

Gere o pacote:

```bash
PYTHON=.venv/bin/python make coach
```

Arquivos gerados:

- `reports/llm/latest-request.md`
- `reports/llm/latest-request.json`

Use `latest-request.md` como prompt para Codex ou outra LLM. A resposta precisa ser JSON estruturado e passar pela validacao:

```bash
PYTHON=.venv/bin/python scripts/generate_recommendation.py --response path/to/response.json
```

O validador rejeita:

- campos desconhecidos;
- fontes cientificas fora de `data/knowledge/science_refs.yaml`;
- uso de treino solo de Matheus como evidencia de Bruna;
- resposta sem campos obrigatorios;
- valores fora dos enums de acao, decisao e confianca.

## Monthly Report

A cada 30 dias, gere pipeline e dashboard, depois revise:

- Consistencia semanal: numero de corridas, longoes e treinos de qualidade.
- Tendencia dos treinos compartilhados com check-in.
- Volume semanal e sinais de fadiga.
- Decisoes de reducao, recuperacao ou adiamento.
- Sintomas de Bruna e qualquer sinal do Aquiles de Matheus.
- Aderencia ao roadmap ate a meia de janeiro de 2027.

Para gerar o relatorio mensal narrativo:

```bash
python scripts/run_pipeline.py --garmin data/raw/garmin/Activities.csv --after-workout --monthly-report
```

Saidas:

- `reports/monthly/latest.md`
- `reports/monthly/YYYY-MM.md`

O relatorio mensal deve ser lido junto com `reports/dashboard.xlsx`, `docs/state.md`, `docs/decisions.md` e CSVs processados.

## Failure Modes

- Garmin CSV ausente: copie a exportacao para `data/raw/garmin/Activities.csv` e rode novamente.
- Check-in duplicado para o mesmo `activity_id`: remova ou consolide um dos YAMLs. O pipeline deve falhar fechado.
- YAML invalido: corrija o arquivo citado no erro.
- Screenshot de HR ausente: mantenha evidencia ausente especifica; nao substitua por HR do Garmin.
- Treino compartilhado sem `bruna_present=true`: nao use pace como evidencia da Bruna ate corrigir o check-in.
- Sono ruim, PSE alto, sintomas fortes, volei no dia anterior ou Aquiles acima do limite: reduza, recupere ou adie qualidade.
- Dashboard sujo apos rebuild: rode novamente com o runtime do projeto e verifique `git status --short`; o workbook deve ser deterministico.
