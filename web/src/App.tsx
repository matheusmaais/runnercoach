import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  BadgeCheck,
  BookOpen,
  Brain,
  CalendarDays,
  Gauge,
  History,
  HeartPulse,
  LineChart as LineChartIcon,
  Rocket,
  Trophy,
  TrendingUp,
  ShieldAlert,
  TimerReset,
  UploadCloud,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { loadPayload } from "./data";
import {
  WorkflowRunFailedError,
  WorkflowRunTimeoutError,
  commitFileToGithub,
  dispatchOperationalWorkflow,
  pollOperationalWorkflow,
} from "./github";
import {
  buildIntakePayload,
  buildRaceIntakePayload,
  validateRaceForm,
  defaultGithubSettings,
  defaultOperationalForm,
  defaultOperationalSteps,
  deriveGarminActivityFromCsv,
  intakePath,
  updateOperationalStep,
  validateOperationalForm,
  type GithubSettings,
  type OperationalFormState,
  type OperationalStep,
} from "./operational";
import type { FrontendPayload, PlannedWorkout, ScienceRef, Workout } from "./types";

type View = "cockpit" | "operate" | "timeline" | "plan" | "coach" | "science";

const nav: { id: View; label: string }[] = [
  { id: "cockpit", label: "Painel" },
  { id: "operate", label: "Operar" },
  { id: "timeline", label: "Histórico" },
  { id: "plan", label: "Plano" },
  { id: "coach", label: "Sala do coach" },
  { id: "science", label: "Ciência" },
];

export function App() {
  const [payload, setPayload] = useState<FrontendPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<View>("cockpit");

  useEffect(() => {
    loadPayload().then(setPayload).catch((err: Error) => setError(err.message));
  }, []);

  async function reloadPayload() {
    const nextPayload = await loadPayload({ cacheBust: true });
    setPayload(nextPayload);
  }

  if (error) {
    return <EmptyState message={error} />;
  }

  if (!payload) {
    return <div className="loading">Carregando Performance Lab...</div>;
  }

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <p className="eyebrow">Performance Lab</p>
          <h1>{payload.mission.name}</h1>
        </div>
        <nav aria-label="Navegação principal">
          {nav.map((item) => (
            <button
              key={item.id}
              className={activeView === item.id ? "active" : ""}
              onClick={() => setActiveView(item.id)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </nav>
      </header>

      <main>
        {activeView === "cockpit" && <Cockpit payload={payload} />}
        {activeView === "operate" && (
          <OperateView onOpenCoach={() => setActiveView("coach")} onOpenPlan={() => setActiveView("plan")} onPayloadReloaded={reloadPayload} />
        )}
        {activeView === "timeline" && <Timeline payload={payload} />}
        {activeView === "plan" && <PlanView payload={payload} />}
        {activeView === "coach" && <CoachRoom payload={payload} />}
        {activeView === "science" && <ScienceDecisions payload={payload} />}
      </main>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="empty-state">
      <ShieldAlert />
      <h1>Dados do frontend indisponíveis</h1>
      <p>{message}</p>
      <p>Rode `make frontend-data` para reconstruir `web/public/data/app-data.json`.</p>
    </div>
  );
}

function Cockpit({ payload }: { payload: FrontendPayload }) {
  const bruna = payload.athletes.bruna.current_training_state;
  const matheus = payload.athletes.matheus.current_training_state;
  const next = payload.next_workouts[0];
  const latestShared = payload.current_state.latest_shared_workout;
  const latestSolo = payload.current_state.latest_matheus_solo;
  const riskTone = riskSignalTone(payload.current_state.risk_level);
  const riskDrivers = extractRiskDrivers(payload);

  return (
    <section className="view cockpit" aria-label="Cockpit">
      <article className="today-card">
        <p className="eyebrow">O que fazer hoje</p>
        <h2>{payload.today.headline}</h2>
        <p className="today-why">{payload.today.why}</p>
        {payload.readiness && (
          <p className={`readiness readiness-${payload.readiness.level}`}>
            Prontidão: <strong>{payload.readiness.level}</strong> — {payload.readiness.message}
          </p>
        )}
        {payload.progression_suggestion?.should_suggest && (
          <p className="progression-nudge">
            <TrendingUp size={16} /> {payload.progression_suggestion.message}
          </p>
        )}
        <div className="badge-row">
          {payload.today.next_planned && (
            <span className="badge teal">Próximo: {formatToken(payload.today.next_planned)}</span>
          )}
          {payload.today.confidence && (
            <span className="badge neutral">Confiança {formatToken(payload.today.confidence)}</span>
          )}
          {payload.today.science_refs.slice(0, 3).map((ref) => (
            <span className="badge amber" key={ref}>{formatToken(ref)}</span>
          ))}
        </div>
      </article>
      {payload.goal_feasibility?.verdict && (
        <article className={`goal-radar goal-${payload.goal_feasibility.verdict}`}>
          <div className="panel-title"><Gauge /><h3>Radar da meta (sub-2h)</h3></div>
          <div className="goal-row">
            <span>Alvo <strong>{payload.goal_feasibility.target_pace}</strong></span>
            <span>Projeção hoje <strong>{payload.goal_feasibility.current_projection}</strong></span>
            <span>Precisa <strong>{payload.goal_feasibility.required_monthly_pct}%/mês</strong></span>
          </div>
          <p className="goal-message">{payload.goal_feasibility.message}</p>
        </article>
      )}
      <div className="mission-grid">
        <div className="mission-copy">
          <p className="eyebrow">Missão ativa</p>
          <h2>No caminho da meia forte, com freio de segurança ligado.</h2>
          <p>{payload.mission.primary_objective}</p>
          <div className="signal-row">
            <Signal label="Status" value="Evoluindo" tone="good" />
            <Signal label="Risco" value={riskLabel(payload.current_state.risk_level)} tone={riskTone} />
            <Signal label="Fase" value={formatToken(payload.current_state.phase)} tone="neutral" />
          </div>
          <div className={`risk-card ${riskTone}`} aria-label="Drivers de risco do cockpit">
            <div>
              <p className="eyebrow">Risco atual</p>
              <h3>{riskLabel(payload.current_state.risk_level)}</h3>
            </div>
            <ul>
              {riskDrivers.map((driver) => (
                <li key={driver}>{driver}</li>
              ))}
            </ul>
          </div>
        </div>
        <NextWorkoutCard workout={next} />
      </div>

      <div className="dashboard-grid">
        <MetricCard
          icon={<HeartPulse />}
          label="Bruna"
          value={bruna.strong_sustainable}
          detail={`Limiar estimado ${bruna.estimated_threshold}. Max curto ${bruna.short_max_current}.`}
          tone="teal"
        />
        <MetricCard
          icon={<Gauge />}
          label="Matheus"
          value={matheus.latest_speed_signal}
          detail="Sinal isolado de velocidade residual. Não entra na evolução da Bruna."
          tone="amber"
        />
        <MetricCard
          icon={<Activity />}
          label="Último compartilhado"
          value={`${latestShared.distance_km} km @ ${latestShared.avg_pace}`}
          detail={`Evidência Bruna: ${formatToken(latestShared.bruna_evidence ?? "missing")}. PSE ${latestShared.bruna_pse || "não informado"}.`}
          tone="green"
        />
        <MetricCard
          icon={<AlertTriangle />}
          label="Solo Matheus"
          value={`${latestSolo.distance_km} km @ ${latestSolo.avg_pace}`}
          detail="Quarentenado: dado Garmin/Matheus, não prova evolução da Bruna."
          tone="red"
        />
      </div>

      <div className="chart-grid">
        <ChartPanel title="Pace médio (min/km)" subtitle="Ritmo médio em minutos por quilômetro." icon={<LineChartIcon />}>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={payload.trends.pace} margin={{ left: 10, right: 10 }}>
              <CartesianGrid stroke="#213047" strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fill: "#9aa8bc", fontSize: 11 }} />
              <YAxis
                tickFormatter={formatSeconds}
                tick={{ fill: "#9aa8bc", fontSize: 11 }}
                domain={["dataMin - 20", "dataMax + 20"]}
                label={{ value: "min/km", angle: -90, position: "insideLeft", fill: "#9aa8bc", fontSize: 11 }}
              />
              <Tooltip content={<PaceTooltip />} />
              <Line type="monotone" dataKey="pace_seconds" stroke="#2dd4bf" strokeWidth={3} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartPanel>
        <ChartPanel title="Volume semanal (km)" subtitle="Distância semanal em km." icon={<CalendarDays />}>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={payload.weekly_summary} margin={{ left: 10, right: 10 }}>
              <CartesianGrid stroke="#213047" strokeDasharray="3 3" />
              <XAxis dataKey="week" tick={{ fill: "#9aa8bc", fontSize: 11 }} />
              <YAxis
                tick={{ fill: "#9aa8bc", fontSize: 11 }}
                label={{ value: "km", angle: -90, position: "insideLeft", fill: "#9aa8bc", fontSize: 11 }}
              />
              <Tooltip formatter={(value: number) => [`${value.toFixed(1)} km`, "Distância"]} />
              <Bar dataKey="distance_km" fill="#22c55e" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartPanel>
        <ChartPanel title="Qualidade semanal (treinos)" subtitle="Treinos de qualidade por semana." icon={<BadgeCheck />}>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={payload.weekly_summary} margin={{ left: 10, right: 10 }}>
              <CartesianGrid stroke="#213047" strokeDasharray="3 3" />
              <XAxis dataKey="week" tick={{ fill: "#9aa8bc", fontSize: 11 }} />
              <YAxis
                allowDecimals={false}
                tick={{ fill: "#9aa8bc", fontSize: 11 }}
                label={{ value: "treinos", angle: -90, position: "insideLeft", fill: "#9aa8bc", fontSize: 11 }}
              />
              <Tooltip formatter={(value: number) => [`${value}`, "Treinos de qualidade"]} />
              <Bar dataKey="quality_runs" fill="#f59e0b" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartPanel>
      </div>

      <div className="chart-grid">
        <ChartPanel title="Longões" icon={<TimerReset />}>
          <ResponsiveContainer width="100%" height={230}>
            <AreaChart data={payload.trends.long_runs}>
              <CartesianGrid stroke="#213047" strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fill: "#9aa8bc", fontSize: 11 }} />
              <YAxis tick={{ fill: "#9aa8bc", fontSize: 11 }} />
              <Tooltip />
              <Area type="monotone" dataKey="distance_km" stroke="#38bdf8" fill="#0ea5e9" fillOpacity={0.22} />
            </AreaChart>
          </ResponsiveContainer>
        </ChartPanel>
        <ChartPanel title="Risco e fadiga" icon={<ShieldAlert />}>
          <ResponsiveContainer width="100%" height={230}>
            <AreaChart data={payload.trends.risk}>
              <CartesianGrid stroke="#213047" strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fill: "#9aa8bc", fontSize: 11 }} />
              <YAxis domain={[0, 5]} tick={{ fill: "#9aa8bc", fontSize: 11 }} />
              <Tooltip />
              <Area type="stepAfter" dataKey="score" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.22} />
            </AreaChart>
          </ResponsiveContainer>
        </ChartPanel>
      </div>
    </section>
  );
}

function NextWorkoutCard({ workout }: { workout?: PlannedWorkout }) {
  if (!workout) {
    return (
      <div className="next-card">
        <p className="eyebrow">Próximo treino</p>
        <h3>Aguardando plano</h3>
        <p>Sem treino planejado no payload atual.</p>
      </div>
    );
  }

  return (
    <div className="next-card">
      <p className="eyebrow">Próximo treino</p>
      <h3>{formatToken(workout.intended_category)}</h3>
      <p className="date-line">{workout.date} · Semana {workout.week_number}</p>
      <p>{workout.decision_basis}</p>
      <div className="badge-row">
        {workout.safety_triggers.slice(0, 3).map((trigger) => (
          <span className="badge amber" key={trigger}>
            {formatToken(trigger)}
          </span>
        ))}
      </div>
    </div>
  );
}

function OperateView({
  onOpenCoach,
  onOpenPlan,
  onPayloadReloaded,
}: {
  onOpenCoach: () => void;
  onOpenPlan: () => void;
  onPayloadReloaded: () => Promise<void>;
}) {
  const [form, setForm] = useState<OperationalFormState>(() => defaultOperationalForm());
  const [settings, setSettings] = useState<GithubSettings>(() => defaultGithubSettings());
  const [status, setStatus] = useState<string>("Pronto para montar intake.");
  const [steps, setSteps] = useState<OperationalStep[]>(() => defaultOperationalSteps());
  const [workflowUrl, setWorkflowUrl] = useState<string>("");
  const [coachReady, setCoachReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const errors = validateOperationalForm(form);
  const payload = buildIntakePayload(form);
  const path = intakePath(payload);
  const raceErrors = validateRaceForm(form);
  const racePayload = buildRaceIntakePayload(form);
  const racePath = intakePath(racePayload);

  useEffect(() => {
    window.localStorage.removeItem("runnercoach.github");
  }, []);

  function update<K extends keyof OperationalFormState>(key: K, value: OperationalFormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function updateSettings<K extends keyof GithubSettings>(key: K, value: GithubSettings[K]) {
    setSettings((current) => ({ ...current, [key]: value }));
  }

  async function onCsv(file: File | null) {
    if (!file) return;
    try {
      const activity = await deriveGarminActivityFromCsv(file);
      setForm((current) => ({
        ...current,
        garminCsvName: file.name,
        garminActivity: activity,
        activityId: current.activityId || activity.activity_id || "",
        garminTitle: current.garminTitle || activity.title || "",
        garminDatetime: current.garminDatetime || activity.local_datetime || "",
        date: current.date || activity.local_date,
      }));
      setStatus("CSV lido localmente; o intake inclui apenas resumo sanitizado.");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Falha ao derivar resumo Garmin.");
    }
  }

  async function commitAndDispatch() {
    if (errors.length) {
      setStatus(`Corrija antes de enviar: ${errors.join(" ")}`);
      return;
    }
    await runIntake(payload, path, `chore: add frontend intake ${form.date}`);
  }

  async function submitRace() {
    if (raceErrors.length) {
      setStatus(`Corrija a prova antes de enviar: ${raceErrors.join(" ")}`);
      return;
    }
    await runIntake(racePayload, racePath, `chore: add race ${form.raceDate}`);
  }

  async function runIntake(intakePayload: object, intakeFilePath: string, commitMessage: string) {
    if (!settings.token.trim()) {
      setStatus("Informe um GitHub token com Contents write e Actions write.");
      return;
    }
    setBusy(true);
    setWorkflowUrl("");
    setCoachReady(false);
    setSteps(updateOperationalStep(defaultOperationalSteps(), "commit", "active", `Commitando intake em ${intakeFilePath}.`));
    const startedAfter = new Date(Date.now() - 60_000).toISOString();
    try {
      await commitFileToGithub({
        settings,
        path: intakeFilePath,
        content: JSON.stringify(intakePayload, null, 2) + "\n",
        message: commitMessage,
      });
      setSteps((current) =>
        updateOperationalStep(
          updateOperationalStep(current, "commit", "done", `Payload commitado em ${intakeFilePath}.`),
          "workflow",
          "active",
          "Dispatch enviado; aguardando run aparecer no GitHub Actions.",
        ),
      );
      await dispatchOperationalWorkflow(settings, intakeFilePath);

      const run = await pollOperationalWorkflow(settings, {
        startedAfter,
        intervalMs: 1_000,
        onWaiting: () => {
          setStatus("Workflow dispatch recebido; aguardando run do Actions aparecer.");
        },
        onUpdate: (run) => {
          setWorkflowUrl(run.html_url);
          if (run.status === "queued") {
            setStatus("Workflow em fila no GitHub Actions.");
            setSteps((current) =>
              updateOperationalStep(current, "workflow", "active", "Workflow em fila no GitHub Actions."),
            );
          } else if (run.status === "in_progress") {
            setStatus("Workflow rodando: LLM, validação e publicação em andamento.");
            setSteps((current) =>
              updateOperationalStep(
                updateOperationalStep(current, "workflow", "done", "Workflow iniciado."),
                "llm",
                "active",
                "LLM e validações determinísticas rodando no Actions.",
              ),
            );
          }
        },
      });

      setWorkflowUrl(run.html_url);
      setSteps((current) =>
        updateOperationalStep(
          updateOperationalStep(
            updateOperationalStep(current, "workflow", "done", "Workflow concluído pelo GitHub Actions."),
            "llm",
            "done",
            "LLM e validações concluídas com sucesso.",
          ),
          "publish",
          "active",
          "Recarregando app-data.json publicado.",
        ),
      );
      await onPayloadReloaded();
      setSteps((current) =>
        updateOperationalStep(current, "publish", "done", "app-data.json recarregado; recomendação pronta."),
      );
      setCoachReady(true);
      setStatus("Workflow concluído com sucesso. Sua semana está pronta.");
    } catch (err) {
      if (err instanceof WorkflowRunFailedError) {
        setWorkflowUrl(err.run.html_url);
        setStatus(`Workflow falhou: ${err.run.conclusion ?? "conclusão desconhecida"}. Abra o run no GitHub Actions para ver logs e rerun.`);
        setSteps((current) =>
          updateOperationalStep(current, "llm", "failed", "Falha no workflow. Verifique logs, secrets e validações no run."),
        );
      } else if (err instanceof WorkflowRunTimeoutError) {
        if (err.run?.html_url) {
          setWorkflowUrl(err.run.html_url);
        }
        setStatus("Workflow não completou dentro do limite. Abra o run no GitHub Actions e confirme se ficou preso ou sem runner.");
        setSteps((current) =>
          updateOperationalStep(current, "workflow", "failed", "Timeout aguardando conclusão do GitHub Actions."),
        );
      } else {
        setStatus(err instanceof Error ? err.message : "Falha operacional desconhecida.");
        setSteps((current) =>
          updateOperationalStep(current, "commit", "failed", "Falha antes de concluir commit, dispatch ou polling."),
        );
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="view" aria-label="Operar">
      <SectionHeader
        eyebrow="Operação pelo frontend"
        title="Inserir treino e disparar análise"
        copy="O browser versiona o intake no GitHub e dispara Actions. A LLM roda apenas no Actions com secret, nunca no GitHub Pages."
      />

      <div className="operate-grid">
        <article className="operate-panel">
          <div className="panel-title">
            <Rocket />
            <h3>GitHub</h3>
          </div>
          <div className="form-grid two">
            <TextInput label="Dono (owner)" value={settings.owner} onChange={(value) => updateSettings("owner", value)} />
            <TextInput label="Repositório" value={settings.repo} onChange={(value) => updateSettings("repo", value)} />
            <TextInput label="Ramo (branch)" value={settings.branch} onChange={(value) => updateSettings("branch", value)} />
            <TextInput label="Token" type="password" value={settings.token} onChange={(value) => updateSettings("token", value)} />
          </div>
          <p className="helper">
            Use token fine-grained do GitHub limitado a este repo: Contents read/write e Actions read/write.
            Token fica apenas na memória desta aba e não é salvo no navegador.
          </p>
        </article>

        <article className="operate-panel">
          <div className="panel-title">
            <UploadCloud />
            <h3>Garmin CSV</h3>
          </div>
          <input
            aria-label="Upload Garmin CSV"
            className="file-input"
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => onCsv(event.target.files?.[0] ?? null)}
          />
          <p className="helper">
            {form.garminCsvName
              ? `${form.garminCsvName} lido localmente; CSV bruto nao sera commitado.`
              : "Opcional: use para preencher o resumo local da atividade selecionada."}
          </p>
        </article>
      </div>

      <article className="operate-panel">
        <h3>Check-in do treino</h3>
        <div className="form-grid three">
          <TextInput label="Data" type="date" value={form.date} onChange={(value) => update("date", value)} />
          <TextInput label="Activity ID Garmin (avancado/opcional)" value={form.activityId} onChange={(value) => update("activityId", value)} />
          <TextInput label="Título Garmin" value={form.garminTitle} onChange={(value) => update("garminTitle", value)} />
          <TextInput label="Data/hora Garmin" value={form.garminDatetime} onChange={(value) => update("garminDatetime", value)} />
          <TextInput label="Planejado" value={form.plannedType} onChange={(value) => update("plannedType", value)} />
          <TextInput label="Executado" value={form.actualType} onChange={(value) => update("actualType", value)} />
          <TextInput label="FC média Bruna" type="number" value={form.brunaAvgHr} onChange={(value) => update("brunaAvgHr", value)} />
          <TextInput label="FC máx Bruna" type="number" value={form.brunaMaxHr} onChange={(value) => update("brunaMaxHr", value)} />
          <TextInput label="PSE Bruna" type="number" value={form.brunaPse} onChange={(value) => update("brunaPse", value)} />
          <TextInput label="Sono Bruna" value={form.brunaSleep} onChange={(value) => update("brunaSleep", value)} />
          <TextInput label="Aquiles manhã" type="number" value={form.achillesMorning} onChange={(value) => update("achillesMorning", value)} />
          <TextInput label="Aquiles depois" type="number" value={form.achillesAfter} onChange={(value) => update("achillesAfter", value)} />
        </div>
        <div className="form-grid two">
          <TextArea label="Sintomas Bruna" value={form.brunaSymptoms} onChange={(value) => update("brunaSymptoms", value)} />
          <TextArea label="Relato Bruna" value={form.brunaSubjective} onChange={(value) => update("brunaSubjective", value)} />
          <TextArea label="Relato Matheus" value={form.matheusSubjective} onChange={(value) => update("matheusSubjective", value)} />
          <TextArea label="Decisão/nota do coach" value={form.coachNote} onChange={(value) => update("coachNote", value)} />
        </div>
        <div className="toggle-row">
          <label><input type="checkbox" checked={form.sharedRun} onChange={(event) => update("sharedRun", event.target.checked)} /> Corrida conjunta</label>
          <label><input type="checkbox" checked={form.volleyballPreviousDay} onChange={(event) => update("volleyballPreviousDay", event.target.checked)} /> Vôlei no dia anterior</label>
          <label><input type="checkbox" checked={form.gymPreviousDay} onChange={(event) => update("gymPreviousDay", event.target.checked)} /> Academia no dia anterior</label>
          <label><input type="checkbox" checked={form.couldRepeatLastBlock} onChange={(event) => update("couldRepeatLastBlock", event.target.checked)} /> Bruna repetiria último bloco</label>
        </div>
      </article>

      <article className="operate-panel" aria-label="Adicionar prova">
        <div className="panel-title"><Trophy /><h3>Adicionar prova (balizador)</h3></div>
        <p className="helper">
          Registre uma prova concluída para recalibrar as zonas de ritmo e a projeção da meia.
          Não precisa de check-in nem CSV — preencha e clique em "Salvar prova".
        </p>
        <div className="form-grid three">
          <TextInput label="Data da prova" type="date" value={form.raceDate} onChange={(value) => update("raceDate", value)} />
          <TextInput label="Distância (km)" type="number" value={form.raceDistanceKm} onChange={(value) => update("raceDistanceKm", value)} />
          <TextInput label="Tempo (mm:ss ou h:mm:ss)" value={form.raceTime} onChange={(value) => update("raceTime", value)} />
          <TextInput label="FC máxima (opcional)" type="number" value={form.raceMaxHr} onChange={(value) => update("raceMaxHr", value)} />
          <label className="field">
            <span>Condições</span>
            <select value={form.raceConditions} onChange={(event) => update("raceConditions", event.target.value)}>
              <option value="normal">Normal</option>
              <option value="heat">Calor</option>
            </select>
          </label>
        </div>
        <TextArea label="Notas (opcional)" value={form.raceNotes} onChange={(value) => update("raceNotes", value)} />
        {raceErrors.length ? (
          <ul className="error-list">{raceErrors.map((e) => <li key={e}>{e}</li>)}</ul>
        ) : (
          <p className="success-text">Prova pronta para salvar em {racePath}.</p>
        )}
        <button className="primary-action" disabled={busy || raceErrors.length > 0} onClick={submitRace} type="button">
          {busy ? "Enviando..." : "Salvar prova e recalibrar zonas"}
        </button>
      </article>

      <div className="operate-grid">
        <article className="operate-panel">
          <h3>Validação</h3>
          {errors.length ? (
            <ul className="error-list">
              {errors.map((error) => <li key={error}>{error}</li>)}
            </ul>
          ) : (
            <p className="success-text">Payload válido para commit e workflow.</p>
          )}
          <p className="helper">Caminho: {path}</p>
          <button className="primary-action" disabled={busy || errors.length > 0} onClick={commitAndDispatch} type="button">
            {busy ? "Enviando..." : "Salvar e ver minha semana"}
          </button>
          <OperationalProgress steps={steps} />
          <p className="helper">{status}</p>
          {workflowUrl && (
            <a className="run-link" href={workflowUrl} target="_blank" rel="noreferrer">
              Abrir run no GitHub Actions
            </a>
          )}
          {coachReady && (
            <div className="result-cta">
              <button className="primary-action" onClick={onOpenPlan} type="button">
                Ver plano da semana
              </button>
              <button className="secondary-action" onClick={onOpenCoach} type="button">
                Ver análise do coach
              </button>
            </div>
          )}
        </article>
        <article className="operate-panel">
          <h3>Revisão legível</h3>
          <IntakeReview form={form} path={path} />
        </article>
      </div>
    </section>
  );
}

function IntakeReview({ form, path }: { form: OperationalFormState; path: string }) {
  const selected = form.garminActivity;
  return (
    <div className="review-summary">
      <div>
        <p className="eyebrow">Atividade</p>
        <h4>{form.garminTitle || selected?.title || "Atividade ainda não selecionada"}</h4>
        <p>
          {form.garminDatetime || selected?.local_datetime || form.date}
          {selected?.distance_km ? ` · ${selected.distance_km.toFixed(2)} km` : ""}
          {selected?.avg_pace ? ` · ${selected.avg_pace}/km` : ""}
        </p>
      </div>
      <div>
        <p className="eyebrow">Bruna</p>
        <p>
          PSE {form.brunaPse || "não informado"} · Sono {formatToken(form.brunaSleep)}
          {form.brunaAvgHr || form.brunaMaxHr ? ` · FC ${form.brunaAvgHr || "?"}/${form.brunaMaxHr || "?"}` : " · FC manual ausente"}
        </p>
        <p>{form.brunaSubjective || "Sem relato subjetivo ainda."}</p>
      </div>
      <div>
        <p className="eyebrow">Matheus</p>
        <p>
          Aquiles {form.achillesMorning || "0"}/10 manhã · {form.achillesAfter || "0"}/10 depois · {formatToken(form.matheusRole)}
        </p>
        <p>{form.matheusSubjective || "Sem relato subjetivo ainda."}</p>
      </div>
      <div>
        <p className="eyebrow">Carga e segurança</p>
        <div className="badge-row">
          <span className={`badge ${form.sharedRun ? "teal" : "neutral"}`}>{form.sharedRun ? "corrida conjunta" : "Matheus-only"}</span>
          {form.volleyballPreviousDay && <span className="badge amber">vôlei anterior</span>}
          {form.gymPreviousDay && <span className="badge amber">academia anterior</span>}
          {form.couldRepeatLastBlock && <span className="badge teal">Bruna repetiria bloco</span>}
        </div>
      </div>
      <p className="helper">Será versionado em {path}. O CSV bruto não entra no Git.</p>
    </div>
  );
}

function OperationalProgress({ steps }: { steps: OperationalStep[] }) {
  return (
    <ol className="operational-progress" aria-label="Progresso operacional">
      {steps.map((step) => (
        <li className={step.state} key={step.key}>
          <span>{step.label}</span>
          <strong>{stepStateLabel(step.state)}</strong>
          <p>{step.detail}</p>
        </li>
      ))}
    </ol>
  );
}

function stepStateLabel(state: OperationalStep["state"]) {
  const labels: Record<OperationalStep["state"], string> = {
    pending: "Pendente",
    active: "Em andamento",
    done: "Concluído",
    failed: "Falhou",
  };
  return labels[state];
}

function TextInput({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input type={type} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function TextArea({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="field">
      <span>{label}</span>
      <textarea value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function Timeline({ payload }: { payload: FrontendPayload }) {
  return (
    <section className="view" aria-label="Timeline">
      <SectionHeader
        eyebrow="Evidência treino a treino"
        title="Histórico"
        copy="Cada sessão carrega contexto de atleta, qualidade da evidência e decisão posterior."
      />
      <div className="timeline-list">
        {payload.recent_workouts.map((workout) => (
          <WorkoutRow key={workout.workout_id} workout={workout} />
        ))}
      </div>
    </section>
  );
}

function WorkoutRow({ workout }: { workout: Workout }) {
  const matheusOnly = workout.bruna_usage === "not_bruna_evidence";
  return (
    <article className={`workout-row ${matheusOnly ? "matheus-only" : ""}`}>
      <div>
        <p className="date-line">{workout.date ?? workout.local_date}</p>
        <h3>{workout.distance_km} km @ {workout.avg_pace}</h3>
        <p>{matheusOnly ? "Garmin Matheus: não usar como evolução da Bruna." : "Corrida conjunta: pace compartilhado com contexto manual."}</p>
      </div>
      <div className="badge-row">
        {(workout.badges ?? []).map((badge) => (
          <span className={`badge ${badge.includes("missing") ? "amber" : "teal"}`} key={badge}>
            {formatToken(badge)}
          </span>
        ))}
        <span className="badge neutral">confiança {formatToken(workout.evidence_confidence)}</span>
      </div>
    </article>
  );
}

function PlanView({ payload }: { payload: FrontendPayload }) {
  const next = payload.next_workouts[0];
  const week = payload.week;
  return (
    <section className="view" aria-label="Plano">
      <SectionHeader
        eyebrow="Minha semana de treinos"
        title="O que fazer esta semana"
        copy="Próximo treino em destaque e a semana inteira (Seg–Dom) para você organizar a rotina."
      />

      {payload.week_narrative && (
        <p className="week-narrative">{payload.week_narrative}</p>
      )}

      {next ? (
        <article className="next-highlight">
          <p className="eyebrow">Próximo treino</p>
          <h3>{formatToken(next.intended_category)}</h3>
          <p className="date-line">{next.date} · Semana {next.week_number}</p>
          <p>{next.decision_basis}</p>
        </article>
      ) : (
        <article className="next-highlight">
          <p className="eyebrow">Próximo treino</p>
          <h3>Semana ainda não atualizada</h3>
          <p>Registre o último treino em Operar para gerar a semana.</p>
        </article>
      )}

      <div className="panel-title"><CalendarDays /><h3>Semana</h3></div>
      {week.generated ? (
        <div className="week-grid">
          {week.days.map((d) => (
            <div className={`week-day ${d.kind}`} key={d.date}>
              <p className="week-dow">{d.day}</p>
              <p className="week-label">{d.label}</p>
              {d.pace && <p className="week-pace">{d.pace}</p>}
              {d.workout && <p className="week-workout">{d.workout}</p>}
            </div>
          ))}
        </div>
      ) : (
        <article className="empty-week">
          <ShieldAlert />
          <p>{week.empty_message}</p>
        </article>
      )}

      {payload.pace_zones && payload.pace_zones.calibrated_from && (
        <article className="zones-card">
          <div className="panel-title"><Gauge /><h3>Zonas de ritmo</h3></div>
          <p className="helper">Calibradas por prova: {payload.pace_zones.calibrated_from}</p>
          <div className="zones-grid">
            <ZoneChip label="Leve / longo" pace={payload.pace_zones.easy} />
            <ZoneChip label="Limiar / ritmo de meia" pace={payload.pace_zones.tempo_hmp} />
            <ZoneChip label="Tiros 5-10K" pace={payload.pace_zones.intervals_5_10k} />
            <ZoneChip label="Projeção meia" pace={payload.pace_zones.half_projection} />
          </div>
        </article>
      )}

      <div className="principles-strip">
        {payload.evidence_contracts.hard_rules.map((rule) => (
          <div key={rule}>
            <BadgeCheck />
            <span>{rule}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function CoachRoom({ payload }: { payload: FrontendPayload }) {
  const recommendation = payload.latest_llm_recommendation;
  const history = payload.recommendation_history ?? [];

  return (
    <section className="view" aria-label="Sala do coach">
      <SectionHeader
        eyebrow="LLM auditável"
        title="Sala do coach"
        copy="A IA interpreta um pacote já preparado. A fronteira de segurança continua no pipeline determinístico."
      />
      {recommendation ? (
        <article className="coach-panel recommendation-panel">
          <div className="panel-title">
            <Rocket />
            <div>
              <h3>Recomendação validada</h3>
              <p>
                Gerada em {recommendation.generated_at || payload.llm_context.generated_at}
                {recommendation.timestamp_source ? ` · ${formatToken(recommendation.timestamp_source)}` : ""}
              </p>
            </div>
          </div>
          {recommendation.stale && (
            <div className="stale-banner">
              <ShieldAlert />
              <span>{recommendation.stale_message}</span>
            </div>
          )}
          <div className="signal-row">
            <Signal label="Ação" value={formatToken(recommendation.next_workout_action)} tone="good" />
            <Signal label="Decisão" value={formatToken(recommendation.decision_type)} tone="neutral" />
            <Signal label="Confiança" value={formatToken(recommendation.confidence)} tone="warn" />
          </div>
          <p>{recommendation.summary}</p>
          <div className="recommendation-grid">
            <div>
              <p className="eyebrow">Próximo treino</p>
              <p>{recommendation.next_workout}</p>
            </div>
            <div>
              <p className="eyebrow">Risco</p>
              <p>{recommendation.risk_assessment}</p>
            </div>
          </div>
          <div className="recommendation-grid evidence-grid">
            <EvidenceList title="Evidência usada" items={recommendation.evidence_used} empty="Nenhuma evidência estruturada registrada." />
            <EvidenceList
              title="Evidência faltante"
              items={recommendation.missing_evidence}
              empty="Sem lacunas críticas registradas."
              tone={recommendation.missing_evidence.length ? "warn" : "good"}
            />
          </div>
          <div className="rule-list">
            {recommendation.science_refs.slice(0, 6).map((ref) => (
              <span key={ref}>{formatToken(ref)}</span>
            ))}
          </div>
        </article>
      ) : (
        <article className="coach-panel recommendation-panel">
          <div className="panel-title">
            <ShieldAlert />
            <h3>Sem recomendação validada</h3>
          </div>
          <p>Dispare uma análise pelo Operar para gerar `reports/llm/latest-recommendation.json`.</p>
        </article>
      )}
      <article className="coach-panel recommendation-history">
        <div className="panel-title">
          <History />
          <div>
            <h3>Histórico de recomendações</h3>
            <p>Série auditável para comparar ação, confiança e data própria da recomendação.</p>
          </div>
        </div>
        {history.length ? (
          <div className="history-list">
            {history.slice(0, 6).map((item) => (
              <div className="history-item" key={item.recommendation_id || `${item.generated_at}-${item.decision_type}`}>
                <div>
                  <p className="date-line">{item.generated_at || item.source_modified_at || "sem timestamp"}</p>
                  <strong>{formatToken(item.next_workout_action)}</strong>
                </div>
                <span className="badge neutral">{formatToken(item.confidence)}</span>
                <p>{item.summary}</p>
              </div>
            ))}
          </div>
        ) : (
          <p>Sem histórico publicado ainda. A próxima análise validada cria a primeira entrada.</p>
        )}
      </article>
      <div className="coach-grid">
        <article className="coach-panel">
          <Brain />
          <h3>Pacote LLM</h3>
          <p>Gerado em {payload.llm_context.generated_at}</p>
          <p>{payload.llm_context.data_contract}</p>
        </article>
        <article className="coach-panel">
          <ShieldAlert />
          <h3>Claims proibidos</h3>
          <ul>
            {payload.llm_context.forbidden_claims.map((claim) => (
              <li key={claim}>{claim}</li>
            ))}
          </ul>
        </article>
        <article className="coach-panel">
          <BookOpen />
          <h3>Base científica</h3>
          <p>{payload.llm_context.approved_science_ref_count} referências aprovadas entram no pacote.</p>
          <p>Sem ciência aprovada, recomendação vira rascunho, não decisão.</p>
        </article>
      </div>
      <div className="warning-board">
        {payload.presentation_warnings.map((warning) => (
          <p key={warning}>{warning}</p>
        ))}
      </div>
    </section>
  );
}

function EvidenceList({
  title,
  items,
  empty,
  tone = "neutral",
}: {
  title: string;
  items: string[];
  empty: string;
  tone?: "neutral" | "warn" | "good";
}) {
  return (
    <div className={`evidence-box ${tone}`}>
      <p className="eyebrow">{title}</p>
      {items.length ? (
        <ul>
          {items.slice(0, 6).map((item) => (
            <li key={item}>{formatToken(item)}</li>
          ))}
        </ul>
      ) : (
        <p>{empty}</p>
      )}
    </div>
  );
}

function ScienceDecisions({ payload }: { payload: FrontendPayload }) {
  return (
    <section className="view" aria-label="Ciência e Decisões">
      <SectionHeader
        eyebrow="Ciência separada de feedback manual"
        title="Ciência & Decisões"
        copy="Fontes aprovadas, interpretação prática e decisões registradas sem misturar estudo, check-in e inferência."
      />
      <div className="science-grid">
        {payload.science_refs.slice(0, 6).map((ref) => (
          <ScienceCard key={ref.science_ref_id} refItem={ref} />
        ))}
      </div>
      <div className="decision-list">
        {payload.decisions.slice(0, 6).map((decision) => (
          <article className="decision-card" key={`${decision.date}-${decision.related_workout_id}`}>
            <p className="date-line">{decision.date} · {formatToken(decision.confidence)}</p>
            <h3>{decision.decision || decision.recommendation_action}</h3>
            <p>{decision.reason || decision.impact}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function ScienceCard({ refItem }: { refItem: ScienceRef }) {
  return (
    <article className="science-card">
      <div>
        <p className="eyebrow">{refItem.year} · {refItem.journal_or_publisher}</p>
        <h3>{refItem.title}</h3>
      </div>
      <p>{refItem.practical_application}</p>
      <a href={refItem.doi_or_url} target="_blank" rel="noreferrer">
        Fonte <ArrowUpRight size={15} />
      </a>
    </article>
  );
}

function ZoneChip({ label, pace }: { label: string; pace?: string }) {
  if (!pace) return null;
  return (
    <div className="zone-chip">
      <span className="zone-label">{label}</span>
      <strong>{pace}</strong>
    </div>
  );
}

function SectionHeader({ eyebrow, title, copy }: { eyebrow: string; title: string; copy: string }) {
  return (
    <div className="section-header">
      <p className="eyebrow">{eyebrow}</p>
      <h2>{title}</h2>
      <p>{copy}</p>
    </div>
  );
}

function MetricCard({
  icon,
  label,
  value,
  detail,
  tone,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  detail: string;
  tone: "teal" | "green" | "amber" | "red";
}) {
  return (
    <article className={`metric-card ${tone}`}>
      <div className="metric-icon">{icon}</div>
      <p className="eyebrow">{label}</p>
      <h3>{value}</h3>
      <p>{detail}</p>
    </article>
  );
}

type SignalTone = "good" | "warn" | "danger" | "neutral";

function Signal({ label, value, tone }: { label: string; value: string; tone: SignalTone }) {
  return (
    <div className={`signal ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ChartPanel({
  title,
  subtitle,
  icon,
  children,
}: {
  title: string;
  subtitle?: string;
  icon: ReactNode;
  children: ReactNode;
}) {
  return (
    <article className="chart-panel">
      <div className="panel-title">
        {icon}
        <div>
          <h3>{title}</h3>
          {subtitle && <p>{subtitle}</p>}
        </div>
      </div>
      {children}
    </article>
  );
}

function PaceTooltip({ active, payload }: { active?: boolean; payload?: { payload: { avg_pace: string; date: string; context: string } }[] }) {
  if (!active || !payload?.[0]) {
    return null;
  }
  const data = payload[0].payload;
  return (
    <div className="tooltip">
      <strong>{data.date}</strong>
      <span>{data.avg_pace} min/km</span>
      <small>{formatToken(data.context)}</small>
    </div>
  );
}

function formatToken(value: string) {
  const labels: Record<string, string> = {
    diagnostic_race_10k: "Prova diagnóstica 10K",
    easy_run: "Corrida leve",
    ten_k_polish: "Polimento 10K",
    post_ten_k_recovery: "Recuperação pós-10K",
    bad_sleep_reduce_volume_or_intensity: "Sono ruim: reduzir volume ou intensidade",
    bruna_symptoms_reduce_intensity: "Sintomas da Bruna: reduzir intensidade",
    matheus_achilles_above_3_remove_speed: "Aquiles > 3: remover velocidade",
    do_not_chase_pace_if_heat_or_course_raise_risk: "Não perseguir pace se clima/percurso elevarem risco",
    keep_easy_even_if_previous_session_was_missed: "Manter leve mesmo se treino anterior foi perdido",
    shared_run_with_manual_checkin: "Corrida conjunta com check-in",
    matheus_garmin_only: "Garmin apenas Matheus",
  };
  return labels[value] ?? value.replace(/_/g, " ").replace(/\b\w/g, (letter: string) => letter.toUpperCase());
}

function riskLabel(value: string) {
  if (value === "low") return "Baixo";
  if (value === "moderate") return "Moderado";
  return "Atenção";
}

function riskSignalTone(value: string): SignalTone {
  if (value === "low") return "good";
  if (value === "moderate") return "warn";
  return "danger";
}

function extractRiskDrivers(payload: FrontendPayload) {
  const structuredDrivers = payload.current_state.risk_drivers
    .map((driver) => driver.label)
    .filter(Boolean);
  if (structuredDrivers.length) {
    return structuredDrivers.slice(0, 5);
  }
  const trendReasons = payload.trends.risk.flatMap((entry) => entry.reasons).filter(Boolean).map(formatToken);
  const currentRiskLines = currentRisksFromMarkdown(payload.current_state.summary_markdown);
  const drivers = [...trendReasons, ...currentRiskLines];
  return [...new Set(drivers)].slice(0, 5);
}

function currentRisksFromMarkdown(markdown: string) {
  const section = markdown.split("## Current Risks")[1]?.split("\n## ")[0] ?? "";
  return section
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.startsWith("- "))
    .map((line) => line.slice(2).trim())
    .filter(Boolean);
}

function formatSeconds(value: number) {
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}
