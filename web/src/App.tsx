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
  HeartPulse,
  LineChart as LineChartIcon,
  ShieldAlert,
  TimerReset,
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
import type { FrontendPayload, PlannedWorkout, ScienceRef, Workout } from "./types";

type View = "cockpit" | "timeline" | "plan" | "coach" | "science";

const nav: { id: View; label: string }[] = [
  { id: "cockpit", label: "Cockpit" },
  { id: "timeline", label: "Timeline" },
  { id: "plan", label: "Plano" },
  { id: "coach", label: "Coach Room" },
  { id: "science", label: "Ciência" },
];

export function App() {
  const [payload, setPayload] = useState<FrontendPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<View>("cockpit");

  useEffect(() => {
    loadPayload().then(setPayload).catch((err: Error) => setError(err.message));
  }, []);

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

  return (
    <section className="view cockpit" aria-label="Cockpit">
      <div className="mission-grid">
        <div className="mission-copy">
          <p className="eyebrow">Missão ativa</p>
          <h2>No caminho da meia forte, com freio de segurança ligado.</h2>
          <p>{payload.mission.primary_objective}</p>
          <div className="signal-row">
            <Signal label="Status" value="Evoluindo" tone="good" />
            <Signal label="Risco" value={riskLabel(payload.current_state.risk_level)} tone="warn" />
            <Signal label="Fase" value={formatToken(payload.current_state.phase)} tone="neutral" />
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
        <ChartPanel title="Pace médio" icon={<LineChartIcon />}>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={payload.trends.pace}>
              <CartesianGrid stroke="#213047" strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fill: "#9aa8bc", fontSize: 11 }} />
              <YAxis
                tickFormatter={formatSeconds}
                tick={{ fill: "#9aa8bc", fontSize: 11 }}
                domain={["dataMin - 20", "dataMax + 20"]}
              />
              <Tooltip content={<PaceTooltip />} />
              <Line type="monotone" dataKey="pace_seconds" stroke="#2dd4bf" strokeWidth={3} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartPanel>
        <ChartPanel title="Volume semanal" icon={<CalendarDays />}>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={payload.weekly_summary}>
              <CartesianGrid stroke="#213047" strokeDasharray="3 3" />
              <XAxis dataKey="week" tick={{ fill: "#9aa8bc", fontSize: 11 }} />
              <YAxis tick={{ fill: "#9aa8bc", fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="distance_km" fill="#22c55e" radius={[4, 4, 0, 0]} />
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

function Timeline({ payload }: { payload: FrontendPayload }) {
  return (
    <section className="view" aria-label="Timeline">
      <SectionHeader
        eyebrow="Evidência treino a treino"
        title="Timeline"
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
  return (
    <section className="view" aria-label="Plano">
      <SectionHeader
        eyebrow="Coerência do ciclo"
        title="Plano ligado ao que já aconteceu"
        copy="As próximas sessões não são aleatórias: elas respeitam fase, última evidência, carga de vôlei/academia e regras de segurança."
      />
      <div className="plan-grid">
        {payload.next_workouts.map((workout) => (
          <article className="plan-card" key={workout.planned_workout_id}>
            <p className="eyebrow">{workout.date} · Semana {workout.week_number}</p>
            <h3>{formatToken(workout.intended_category)}</h3>
            <p>{workout.decision_basis}</p>
            <div className="rule-list">
              {workout.safety_triggers.map((trigger) => (
                <span key={trigger}>{formatToken(trigger)}</span>
              ))}
            </div>
          </article>
        ))}
      </div>
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
  return (
    <section className="view" aria-label="Coach Room">
      <SectionHeader
        eyebrow="LLM auditável"
        title="Coach Room"
        copy="A IA interpreta um pacote já preparado. A fronteira de segurança continua no pipeline determinístico."
      />
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

function Signal({ label, value, tone }: { label: string; value: string; tone: "good" | "warn" | "neutral" }) {
  return (
    <div className={`signal ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ChartPanel({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <article className="chart-panel">
      <div className="panel-title">
        {icon}
        <h3>{title}</h3>
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
      <span>{data.avg_pace}</span>
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

function formatSeconds(value: number) {
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}
