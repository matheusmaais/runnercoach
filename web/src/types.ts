export type FrontendPayload = {
  generated_at: string;
  mission: {
    name: string;
    target_race_window: string;
    primary_objective: string;
    short_term_focus: string;
    interface_role: string;
  };
  athletes: {
    matheus: Athlete;
    bruna: Athlete;
  };
  current_state: {
    phase: string;
    status: string;
    risk_level: string;
    risk_drivers: RiskDriver[];
    risk_summary: RiskSummary;
    latest_shared_workout: Workout;
    latest_matheus_solo: Workout;
    summary_markdown: string;
  };
  next_workouts: PlannedWorkout[];
  recent_workouts: Workout[];
  weekly_summary: WeeklySummary[];
  trends: {
    pace: PaceTrend[];
    long_runs: LongRunTrend[];
    strong_sustainable: PaceTrend[];
    risk: RiskTrend[];
  };
  decisions: Decision[];
  science_refs: ScienceRef[];
  llm_context: {
    generated_at: string;
    data_contract: string;
    forbidden_claims: string[];
    approved_science_ref_count: number;
  };
  latest_llm_recommendation: LlmRecommendation | null;
  recommendation_history: LlmRecommendation[];
  evidence_contracts: {
    garmin_owner: string;
    shared_data: string[];
    bruna_manual_data: string[];
    hard_rules: string[];
  };
  presentation_warnings: string[];
};

export type LlmRecommendation = {
  recommendation_id: string;
  generated_at: string;
  timestamp_source: string;
  source_path: string;
  source_modified_at: string;
  decision_type: string;
  next_workout_action: string;
  confidence: string;
  summary: string;
  what_workout_showed: string;
  risk_assessment: string;
  next_workout: string;
  science_refs: string[];
  evidence_used: string[];
  missing_evidence: string[];
};

export type Athlete = {
  age: number;
  role: string;
  strategic_limit: string;
  data_sources: Record<string, string>;
  current_training_state: Record<string, string>;
};

export type Workout = {
  workout_id: string;
  date?: string;
  local_date?: string;
  datetime?: string;
  local_datetime?: string;
  athlete_context: string;
  distance_km: number | string;
  avg_pace: string;
  bruna_evidence?: string;
  bruna_pse?: string;
  bruna_symptoms?: string[];
  missing_evidence: string[];
  evidence_confidence: string;
  display_context?: string;
  shared_run: boolean;
  bruna_present: boolean;
  badges?: string[];
  bruna_usage?: string;
  recommendation_action?: string;
  decision_after_workout?: string;
};

export type PlannedWorkout = {
  planned_workout_id: string;
  week_number: string;
  date: string;
  phase: string;
  intended_category: string;
  planned_status: string;
  derived_status: string;
  evidence: string;
  missing_evidence: string[];
  decision_basis: string;
  safety_triggers: string[];
};

export type WeeklySummary = {
  week: string;
  runs: number;
  distance_km: number;
  quality_runs: number;
  shared_runs: number;
};

export type PaceTrend = {
  date: string;
  pace_seconds: number;
  avg_pace: string;
  context: string;
};

export type LongRunTrend = {
  date: string;
  distance_km: number;
  avg_pace: string;
};

export type RiskTrend = {
  date: string;
  workout_id: string;
  score: number;
  reasons: string[];
};

export type RiskDriver = {
  code: string;
  label: string;
  source_date: string;
  source_workout_id: string;
};

export type RiskSummary = {
  level: string;
  latest_score: number;
  source: string;
  source_date: string;
  source_workout_id: string;
  drivers: RiskDriver[];
};

export type Decision = {
  date: string;
  event: string;
  decision: string;
  reason: string;
  impact: string;
  confidence: string;
  evidence: string;
  science_refs: string[];
  recommendation_action: string;
  related_workout_id: string;
};

export type ScienceRef = {
  science_ref_id: string;
  title: string;
  authors: string;
  year: string;
  journal_or_publisher: string;
  doi_or_url: string;
  finding: string;
  practical_application: string;
  limits: string;
  tags: string[];
};
