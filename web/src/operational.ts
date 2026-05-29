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
  garminCsvBase64: string;
};

export type GithubSettings = {
  owner: string;
  repo: string;
  branch: string;
  token: string;
};

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
    garminCsvBase64: "",
  };
}

export function defaultGithubSettings(): GithubSettings {
  return {
    owner: "matheusandrade",
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
        activity_id: form.activityId,
        garmin_title: form.garminTitle || null,
        garmin_datetime: form.garminDatetime || null,
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
    garmin_csv: form.garminCsvBase64
      ? {
          filename: form.garminCsvName || "Activities.csv",
          content_base64: form.garminCsvBase64,
        }
      : null,
    workflow: {
      run_llm: true,
      commit_results: true,
    },
  };
}

export function validateOperationalForm(form: OperationalFormState): string[] {
  const errors: string[] = [];
  if (!form.date) errors.push("Data do treino é obrigatória.");
  if (!form.activityId.trim()) errors.push("Activity ID do Garmin é obrigatório para casar check-in e treino.");
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

export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Falha ao ler arquivo."));
    reader.onload = () => {
      const result = String(reader.result || "");
      resolve(result.includes(",") ? result.split(",")[1] : result);
    };
    reader.readAsDataURL(file);
  });
}

function numberOrNull(value: string) {
  return value === "" ? null : Number(value);
}

function inRange(value: number, min: number, max: number) {
  return Number.isFinite(value) && value >= min && value <= max;
}
