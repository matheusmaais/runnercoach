export type GarminActivitySummary = {
  source_filename: string;
  activity_id: string | null;
  local_date: string;
  local_datetime: string | null;
  timezone: "America/Sao_Paulo";
  activity_type: string | null;
  title: string | null;
  distance_km: number | null;
  duration_seconds: number | null;
  avg_pace: string | null;
  best_pace: string | null;
};

export type OperationalFormState = {
  date: string;
  activityId: string;
  garminTitle: string;
  garminDatetime: string;
  plannedType: string;
  actualType: string;
  sharedRun: boolean;
  brunaAvgHr: string;
  brunaMaxHr: string;
  brunaPse: string;
  brunaSymptoms: string;
  brunaSleep: string;
  volleyballPreviousDay: boolean;
  gymPreviousDay: boolean;
  lowerBodyLoad: string;
  brunaSubjective: string;
  couldRepeatLastBlock: boolean;
  achillesMorning: string;
  achillesAfter: string;
  matheusRole: string;
  matheusSubjective: string;
  coachNote: string;
  garminCsvName: string;
  garminActivity: GarminActivitySummary | null;
  raceDate: string;
  raceDistanceKm: string;
  raceTime: string;
  raceConditions: string;
  raceMaxHr: string;
  raceNotes: string;
};

export type GithubSettings = {
  owner: string;
  repo: string;
  branch: string;
  token: string;
};

export type OperationalStepKey = "commit" | "workflow" | "llm" | "publish";

export type OperationalStepState = "pending" | "active" | "done" | "failed";

export type OperationalStep = {
  key: OperationalStepKey;
  label: string;
  state: OperationalStepState;
  detail: string;
};

export function defaultOperationalSteps(): OperationalStep[] {
  return [
    { key: "commit", label: "Commit/payload", state: "pending", detail: "Aguardando envio do intake." },
    { key: "workflow", label: "Workflow", state: "pending", detail: "Aguardando dispatch no GitHub Actions." },
    { key: "llm", label: "LLM/validação", state: "pending", detail: "Roda apenas no Actions com secrets do repositório." },
    { key: "publish", label: "Publicação", state: "pending", detail: "Aguardando atualização do app-data.json." },
  ];
}

export function updateOperationalStep(
  steps: OperationalStep[],
  key: OperationalStepKey,
  state: OperationalStepState,
  detail: string,
) {
  return steps.map((step) => (step.key === key ? { ...step, state, detail } : step));
}

export function defaultOperationalForm(): OperationalFormState {
  const today = new Date().toISOString().slice(0, 10);
  return {
    date: today,
    activityId: "",
    garminTitle: "",
    garminDatetime: "",
    plannedType: "easy_run",
    actualType: "easy_run",
    sharedRun: true,
    brunaAvgHr: "",
    brunaMaxHr: "",
    brunaPse: "",
    brunaSymptoms: "",
    brunaSleep: "regular",
    volleyballPreviousDay: false,
    gymPreviousDay: false,
    lowerBodyLoad: "none",
    brunaSubjective: "",
    couldRepeatLastBlock: false,
    achillesMorning: "0",
    achillesAfter: "0",
    matheusRole: "pacer",
    matheusSubjective: "",
    coachNote: "",
    garminCsvName: "",
    garminActivity: null,
    raceDate: today,
    raceDistanceKm: "",
    raceTime: "",
    raceConditions: "normal",
    raceMaxHr: "",
    raceNotes: "",
  };
}

export function defaultGithubSettings(): GithubSettings {
  return {
    owner: "matheusmaais",
    repo: "runnercoach",
    branch: "main",
    token: "",
  };
}

export function buildIntakePayload(form: OperationalFormState) {
  const symptoms = form.brunaSymptoms
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  const createdAt = new Date().toISOString();

  return {
    schema_version: 1,
    created_at: createdAt,
    source: "github_pages",
    checkin: {
      schema_version: 1,
      date: form.date,
      confidence: "medium",
      activity_match: {
        activity_id: form.activityId.trim() || null,
        garmin_title: form.garminTitle || null,
        garmin_datetime: form.garminDatetime || null,
        distance_km: form.garminActivity?.distance_km ?? null,
      },
      session: {
        planned_type: form.plannedType || null,
        actual_type: form.actualType || null,
        shared_run: form.sharedRun,
      },
      bruna: {
        avg_hr: numberOrNull(form.brunaAvgHr),
        max_hr: numberOrNull(form.brunaMaxHr),
        pse: numberOrNull(form.brunaPse),
        symptoms,
        sleep_quality: form.brunaSleep || null,
        volleyball_previous_day: form.volleyballPreviousDay,
        gym_previous_day: form.gymPreviousDay,
        lower_body_load_previous_day: form.lowerBodyLoad || null,
        subjective: form.brunaSubjective || null,
        could_repeat_last_block: form.couldRepeatLastBlock,
      },
      matheus: {
        achilles_morning: Number(form.achillesMorning || 0),
        achilles_after: Number(form.achillesAfter || 0),
        role: form.matheusRole,
        subjective: form.matheusSubjective || null,
      },
      attachments: {
        bruna_hr_screenshot: null,
        bruna_hr_screenshot_sha256: null,
        bruna_hr_extraction: {
          extracted_avg_hr: null,
          extracted_max_hr: null,
          extraction_method: "not_applicable",
          extraction_confidence: null,
        },
      },
      coach_notes: {
        decision_after_workout: form.coachNote || null,
      },
    },
    garmin_activity: form.garminActivity
      ? {
          ...form.garminActivity,
          activity_id: form.activityId.trim() || form.garminActivity.activity_id,
          local_date: form.date,
          local_datetime: form.garminDatetime || form.garminActivity.local_datetime,
          title: form.garminTitle || form.garminActivity.title,
        }
      : null,
    workflow: {
      run_llm: true,
      commit_results: true,
    },
  };
}

export function parseRaceTimeSeconds(value: string): number | null {
  const parts = value.trim().split(":");
  if (parts.length < 2 || parts.length > 3) return null;
  const nums = parts.map((p) => Number(p));
  if (nums.some((n) => !Number.isInteger(n) || n < 0)) return null;
  const ss = nums[nums.length - 1];
  const mm = nums[nums.length - 2];
  if (ss >= 60) return null;
  if (parts.length === 3 && mm >= 60) return null;
  const total = parts.length === 2 ? mm * 60 + ss : nums[0] * 3600 + mm * 60 + ss;
  return total > 0 ? total : null;
}

export function validateRaceForm(form: OperationalFormState): string[] {
  const errors: string[] = [];
  if (!form.raceDate) errors.push("Data da prova é obrigatória.");
  const dist = Number(form.raceDistanceKm);
  if (!Number.isFinite(dist) || dist <= 0) errors.push("Distância da prova deve ser maior que 0.");
  if (parseRaceTimeSeconds(form.raceTime) == null) errors.push("Tempo da prova inválido (use mm:ss ou h:mm:ss).");
  if (form.raceMaxHr && !inRange(Number(form.raceMaxHr), 30, 240)) errors.push("FC máxima deve estar entre 30 e 240.");
  return errors;
}

export function buildRaceIntakePayload(form: OperationalFormState) {
  return {
    schema_version: 1,
    created_at: new Date().toISOString(),
    source: "github_pages",
    race: {
      date: form.raceDate,
      distance_km: Number(form.raceDistanceKm),
      time_seconds: parseRaceTimeSeconds(form.raceTime) ?? 0,
      conditions: form.raceConditions === "heat" ? "heat" : "normal",
      max_hr: form.raceMaxHr ? Number(form.raceMaxHr) : null,
      notes: form.raceNotes || null,
    },
    workflow: { run_llm: false, commit_results: true },
  };
}

export function validateOperationalForm(form: OperationalFormState): string[] {
  const errors: string[] = [];
  if (!form.date) errors.push("Data do treino é obrigatória.");
  const hasTechnicalId = Boolean(form.activityId.trim());
  const hasHumanKeys = Boolean(
    (form.garminDatetime && (form.garminTitle || form.garminActivity?.distance_km != null)) ||
      (form.garminTitle && form.garminActivity?.distance_km != null),
  );
  if (!hasTechnicalId && !hasHumanKeys) {
    errors.push("Informe data/hora Garmin e título ou distância para casar a atividade.");
  }
  if (form.brunaPse && !inRange(Number(form.brunaPse), 0, 10)) errors.push("PSE da Bruna deve estar entre 0 e 10.");
  if (!inRange(Number(form.achillesMorning), 0, 10)) errors.push("Aquiles de manhã deve estar entre 0 e 10.");
  if (!inRange(Number(form.achillesAfter), 0, 10)) errors.push("Aquiles depois deve estar entre 0 e 10.");
  if (form.brunaAvgHr && !inRange(Number(form.brunaAvgHr), 30, 240)) errors.push("FC média da Bruna deve estar entre 30 e 240.");
  if (form.brunaMaxHr && !inRange(Number(form.brunaMaxHr), 30, 240)) errors.push("FC máxima da Bruna deve estar entre 30 e 240.");
  return errors;
}

export function intakePath(payload: { created_at: string }) {
  const slug = payload.created_at.replace(/[-:]/g, "").replace(/\.\d+Z$/, "Z");
  return `data/manual/frontend_intake/${slug}.json`;
}

export async function deriveGarminActivityFromCsv(file: File): Promise<GarminActivitySummary> {
  const rows = parseCsv(await file.text());
  if (rows.length < 2) {
    throw new Error("CSV Garmin sem atividades.");
  }
  const headers = rows[0].map((header) => header.trim());
  const firstActivity = rows.slice(1).find((row) => row.some((value) => value.trim()));
  if (!firstActivity) {
    throw new Error("CSV Garmin sem atividades.");
  }
  const get = (...names: string[]) => {
    for (const name of names) {
      const index = headers.indexOf(name);
      if (index >= 0) return firstActivity[index]?.trim() || "";
    }
    return "";
  };

  const localDatetime = get("Data", "Date");
  const title = get("Título", "Title");
  const distanceKm = parseGarminNumber(get("Distância", "Distance"));
  const durationSeconds = parseDurationSeconds(get("Tempo", "Time"));
  const activityId = await makeGarminActivityId({
    localDatetime,
    title,
    distanceKm,
    durationSeconds,
  });

  return {
    source_filename: file.name,
    activity_id: activityId,
    local_date: localDatetime.slice(0, 10),
    local_datetime: localDatetime || null,
    timezone: "America/Sao_Paulo",
    activity_type: get("Tipo de atividade", "Activity Type") || null,
    title: title || null,
    distance_km: distanceKm,
    duration_seconds: durationSeconds,
    avg_pace: get("Ritmo médio", "Avg Pace") || null,
    best_pace: get("Melhor ritmo", "Best Pace") || null,
  };
}

function numberOrNull(value: string) {
  return value === "" ? null : Number(value);
}

function inRange(value: number, min: number, max: number) {
  return Number.isFinite(value) && value >= min && value <= max;
}

function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  const normalized = text.replace(/^\uFEFF/, "");

  for (let index = 0; index < normalized.length; index += 1) {
    const char = normalized[index];
    const next = normalized[index + 1];
    if (quoted) {
      if (char === "\"" && next === "\"") {
        field += "\"";
        index += 1;
      } else if (char === "\"") {
        quoted = false;
      } else {
        field += char;
      }
    } else if (char === "\"") {
      quoted = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n") {
      row.push(field.replace(/\r$/, ""));
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += char;
    }
  }

  if (field || row.length) {
    row.push(field.replace(/\r$/, ""));
    rows.push(row);
  }
  return rows;
}

function parseGarminNumber(value: string): number | null {
  const normalized = value.trim();
  if (!normalized || normalized === "--") return null;
  const parsed = Number(normalized.replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

function parseDurationSeconds(value: string): number | null {
  const parts = value.trim().split(":");
  if (parts.length !== 3) return null;
  const [hours, minutes, seconds] = parts.map(Number);
  if (![hours, minutes, seconds].every(Number.isFinite)) return null;
  return hours * 3600 + minutes * 60 + seconds;
}

async function makeGarminActivityId({
  localDatetime,
  title,
  distanceKm,
  durationSeconds,
}: {
  localDatetime: string;
  title: string;
  distanceKm: number | null;
  durationSeconds: number | null;
}) {
  if (!localDatetime || !title || distanceKm == null || durationSeconds == null) {
    return null;
  }
  const normalizedTitle = title.trim().toLowerCase().replace(/\s+/g, " ");
  const distance = distanceKm;
  const duration = durationSeconds;
  const source = `${localDatetime.replace(" ", "T")}|${distance.toFixed(2)}|${duration.toFixed(1)}|${normalizedTitle}`;
  const digest = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(source));
  const hash = Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 8);
  const stamp = localDatetime.replace(/[-:]/g, "").replace(" ", "T").slice(0, 15) || "unknown";
  const distanceToken = distance.toFixed(2).replace(".", "p");
  return `garmin-${stamp}-${distanceToken}km-${Math.round(duration)}s-${hash}`;
}
