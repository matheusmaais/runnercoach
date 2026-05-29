from __future__ import annotations

import csv
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import ValidationError
import yaml

from running_coach.checkins import CheckIn
from running_coach.csv_utils import encode_json_cell
from running_coach.garmin import (
    GARMIN_ACTIVITY_FIELDS,
    human_activity_key_summary,
    matches_activity_keys,
    parse_garmin_csv_text,
)
from running_coach.models import (
    Confidence,
    DecisionType,
    MatheusRole,
    RecommendationAction,
    SymptomSeverity,
    WorkoutRecord,
)
from running_coach.recommendations import (
    RecommendationInput,
    RecommendationResult,
    recommend_next_action,
)
from running_coach.reports import write_text_report
from running_coach.science import ScienceRef, load_science_refs


WORKOUT_FIELDS = [
    "date",
    "local_date",
    "local_datetime",
    "timezone",
    "workout_id",
    "activity_id",
    "planned_workout_id",
    "athlete_context",
    "participants",
    "shared_run",
    "bruna_present",
    "matheus_role",
    "activity_type",
    "category",
    "distance_km",
    "duration",
    "avg_pace",
    "best_pace",
    "matheus_avg_hr",
    "matheus_max_hr",
    "matheus_cadence",
    "matheus_power",
    "matheus_ground_contact",
    "matheus_stride_length",
    "bruna_avg_hr",
    "bruna_max_hr",
    "bruna_pse",
    "bruna_symptoms",
    "matheus_achilles_morning",
    "matheus_achilles_after",
    "sleep_quality",
    "volleyball_previous_day",
    "gym_previous_day",
    "notes",
    "decision_after_workout",
    "recommendation_action",
    "confidence",
    "symptom_severity",
    "missing_evidence",
    "evidence_level",
    "match_confidence",
]

PLAN_STATUS_FIELDS = [
    "planned_workout_id",
    "week_number",
    "date",
    "phase",
    "intended_category",
    "planned_status",
    "derived_status",
    "matched_workout_id",
    "related_decision",
    "evidence",
    "missing_evidence",
]

DECISION_FIELDS = [
    "date",
    "local_date",
    "local_datetime",
    "timezone",
    "event",
    "decision",
    "reason",
    "impact",
    "related_workout_id",
    "evidence",
    "confidence",
    "science_refs",
    "decision_type",
    "blocked_by_red_flag",
    "missing_evidence",
    "decision_id",
    "workout_id",
    "activity_id",
    "recommendation_action",
    "rationale",
]

SCIENCE_REF_FIELDS = [
    "science_ref_id",
    "title",
    "authors",
    "year",
    "source_type",
    "journal_or_publisher",
    "doi_or_url",
    "population",
    "finding",
    "practical_application",
    "limits",
    "tags",
    "approved",
    "approved_date",
    "notes",
]


class PipelineError(RuntimeError):
    pass


class CheckInLoadError(PipelineError):
    pass


@dataclass(frozen=True)
class LoadedCheckIn:
    path: Path
    checkin: CheckIn


def run_pipeline(
    garmin_csv: Path,
    repo_root: Path,
    after_workout: bool,
    monthly_report: bool = False,
) -> None:
    garmin_csv = Path(garmin_csv)
    repo_root = Path(repo_root)

    activities = parse_garmin_csv_text(
        garmin_csv.read_text(encoding="utf-8-sig"), source_file=garmin_csv.name
    )
    activities = _merge_with_existing_processed_activities(repo_root, activities)
    checkins = _match_checkins_to_activities(repo_root, activities)
    workouts = [
        _workout_from_activity(activity, checkins.get(activity["activity_id"]))
        for activity in activities
    ]
    _attach_planned_workouts(repo_root, workouts)
    recommendations = {
        workout.workout_id: _recommendation_for_workout(repo_root, workout)
        for workout in workouts
    }
    workouts = [
        workout.model_copy(
            update={"recommendation_action": recommendations[workout.workout_id].action}
        )
        for workout in workouts
    ]
    decisions = [
        _decision_from_workout(workout, recommendations[workout.workout_id])
        for workout in workouts
    ]
    plan_status = _build_plan_status(repo_root, workouts, decisions)
    science_refs = _load_science_refs(repo_root)

    processed_dir = repo_root / "data/processed"
    _write_csv(processed_dir / "activities.csv", GARMIN_ACTIVITY_FIELDS, activities)
    _write_csv(
        processed_dir / "workouts.csv",
        WORKOUT_FIELDS,
        [_workout_csv_row(workout) for workout in workouts],
    )
    _write_csv(processed_dir / "decisions.csv", DECISION_FIELDS, decisions)
    _write_csv(processed_dir / "plan_status.csv", PLAN_STATUS_FIELDS, plan_status)
    _write_csv(
        processed_dir / "science_refs.csv",
        SCIENCE_REF_FIELDS,
        [_science_ref_csv_row(ref) for ref in science_refs.values()],
    )

    _write_reports(
        repo_root,
        activities,
        workouts,
        decisions,
        science_refs,
        plan_status,
        after_workout,
        monthly_report,
    )


def _merge_with_existing_processed_activities(
    repo_root: Path, incoming: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    existing_path = repo_root / "data/processed/activities.csv"
    if not existing_path.exists():
        return incoming

    with existing_path.open(encoding="utf-8", newline="") as handle:
        existing = list(csv.DictReader(handle))

    merged: dict[str, dict[str, Any]] = {
        str(activity["activity_id"]): _normalize_existing_activity(activity)
        for activity in existing
        if activity.get("activity_id")
    }
    for activity in incoming:
        merged[str(activity["activity_id"])] = activity

    return sorted(
        merged.values(),
        key=lambda activity: str(activity.get("local_datetime") or activity.get("local_date") or ""),
    )


def _normalize_existing_activity(activity: dict[str, str]) -> dict[str, Any]:
    normalized: dict[str, Any] = dict(activity)
    for field in ("source_row_number", "matheus_avg_hr", "matheus_max_hr", "matheus_cadence", "matheus_power"):
        normalized[field] = _optional_int(normalized.get(field))
    for field in ("distance_km", "duration_seconds", "matheus_ground_contact", "matheus_stride_length"):
        normalized[field] = _optional_float(normalized.get(field))
    normalized["is_shared_run_candidate"] = str(
        normalized.get("is_shared_run_candidate", "")
    ).strip().casefold() in {"true", "1", "yes"}
    for field in ("avg_pace", "best_pace", "title", "activity_type"):
        if normalized.get(field) == "":
            normalized[field] = None
    return normalized


def _optional_int(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    return int(float(value))


def _optional_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    return float(value)


def _load_checkins(repo_root: Path) -> list[LoadedCheckIn]:
    checkins_dir = repo_root / "data/manual/checkins"
    if not checkins_dir.exists():
        return []

    checkins: list[LoadedCheckIn] = []
    checkin_paths: dict[str, Path] = {}
    for path in sorted(checkins_dir.glob("*.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            checkin = CheckIn.model_validate(payload)
        except (OSError, ValidationError, yaml.YAMLError) as exc:
            raise CheckInLoadError(f"Failed to load check-in {path}: {exc}") from exc
        activity_id = checkin.activity_match.activity_id
        if activity_id and activity_id in checkin_paths:
            first_path = checkin_paths[activity_id]
            raise CheckInLoadError(
                "Duplicate check-ins reference activity_id "
                f"{activity_id}: {first_path} and {path}"
            )
        if activity_id:
            checkin_paths[activity_id] = path
        checkins.append(LoadedCheckIn(path=path, checkin=checkin))
    return checkins


def _match_checkins_to_activities(
    repo_root: Path, activities: list[dict[str, Any]]
) -> dict[str, CheckIn]:
    matched: dict[str, CheckIn] = {}
    matched_paths: dict[str, Path] = {}
    activities_by_id = {activity["activity_id"]: activity for activity in activities}

    for loaded in _load_checkins(repo_root):
        activity_id = _resolve_checkin_activity_id(loaded, activities, activities_by_id)
        if activity_id in matched:
            first_path = matched_paths[activity_id]
            raise CheckInLoadError(
                "Duplicate check-ins matched activity_id "
                f"{activity_id}: {first_path} and {loaded.path}"
            )
        matched[activity_id] = loaded.checkin
        matched_paths[activity_id] = loaded.path
    return matched


def _resolve_checkin_activity_id(
    loaded: LoadedCheckIn,
    activities: list[dict[str, Any]],
    activities_by_id: dict[str, dict[str, Any]],
) -> str:
    checkin = loaded.checkin
    match = checkin.activity_match
    if match.activity_id:
        if match.activity_id not in activities_by_id:
            raise CheckInLoadError(
                "Check-in references activity_id not present in Garmin CSV "
                f"{loaded.path}: activity_id={match.activity_id}"
            )
        return match.activity_id

    _require_human_activity_keys(loaded)
    candidates = [
        activity
        for activity in activities
        if matches_activity_keys(
            activity,
            date=checkin.date.isoformat(),
            garmin_title=match.garmin_title,
            garmin_datetime=match.garmin_datetime,
            distance_km=match.distance_km,
        )
    ]
    summary = human_activity_key_summary(
        date=checkin.date.isoformat(),
        garmin_title=match.garmin_title,
        garmin_datetime=match.garmin_datetime,
        distance_km=match.distance_km,
    )
    if not candidates:
        raise CheckInLoadError(
            f"No Garmin activity matched check-in {loaded.path}: {summary}"
        )
    if len(candidates) > 1:
        ids = ", ".join(activity["activity_id"] for activity in candidates)
        raise CheckInLoadError(
            f"Multiple Garmin activities matched check-in {loaded.path}: "
            f"{summary}; candidates={ids}"
        )
    return str(candidates[0]["activity_id"])


def _require_human_activity_keys(loaded: LoadedCheckIn) -> None:
    match = loaded.checkin.activity_match
    if match.garmin_datetime and (match.garmin_title or match.distance_km is not None):
        return
    if match.garmin_title and match.distance_km is not None:
        return
    raise CheckInLoadError(
        "Check-in needs activity_id or human Garmin match keys "
        f"{loaded.path}: provide garmin_datetime plus title or distance_km"
    )


def _activity_fields(activity: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": activity["local_date"],
        "local_date": activity["local_date"],
        "local_datetime": activity["local_datetime"],
        "timezone": activity["timezone"],
        "workout_id": f"workout-{activity['activity_id']}",
        "activity_id": activity["activity_id"],
        "planned_workout_id": None,
        "activity_type": activity["activity_type"],
        "distance_km": activity["distance_km"],
        "duration": activity["duration_seconds"],
        "avg_pace": activity["avg_pace"],
        "best_pace": activity["best_pace"],
        "matheus_avg_hr": activity["matheus_avg_hr"],
        "matheus_max_hr": activity["matheus_max_hr"],
        "matheus_cadence": activity["matheus_cadence"],
        "matheus_power": activity["matheus_power"],
        "matheus_ground_contact": activity["matheus_ground_contact"],
        "matheus_stride_length": activity["matheus_stride_length"],
    }


def _workout_from_activity(
    activity: dict[str, Any], checkin: CheckIn | None = None
) -> WorkoutRecord:
    base = _activity_fields(activity)
    if checkin is None:
        return WorkoutRecord(
            **base,
            athlete_context="matheus_garmin_only",
            participants=["matheus"],
            shared_run=False,
            bruna_present=False,
            matheus_role=MatheusRole.SOLO,
            category=None,
            confidence=Confidence.LOW,
            evidence_level=Confidence.LOW,
            recommendation_action=RecommendationAction.REQUEST_MANUAL_RESOLUTION,
            missing_evidence=["checkin"],
        )

    shared_run = checkin.session.shared_run
    notes = " ".join(
        note for note in [checkin.bruna.subjective, checkin.matheus.subjective] if note
    )
    return WorkoutRecord(
        **base,
        athlete_context=(
            "shared_run_with_manual_checkin"
            if shared_run
            else "matheus_garmin_with_manual_checkin"
        ),
        participants=["matheus", "bruna"] if shared_run else ["matheus"],
        shared_run=shared_run,
        bruna_present=shared_run,
        matheus_role=checkin.matheus.role,
        category=checkin.session.actual_type or checkin.session.planned_type,
        bruna_avg_hr=checkin.bruna.avg_hr,
        bruna_max_hr=checkin.bruna.max_hr,
        bruna_pse=checkin.bruna.pse,
        bruna_symptoms=checkin.bruna.symptoms,
        symptom_severity=_classify_symptom_severity(checkin.bruna.symptoms),
        matheus_achilles_morning=checkin.matheus.achilles_morning,
        matheus_achilles_after=checkin.matheus.achilles_after,
        sleep_quality=checkin.bruna.sleep_quality,
        volleyball_previous_day=checkin.bruna.volleyball_previous_day,
        gym_previous_day=checkin.bruna.gym_previous_day,
        notes=notes or None,
        decision_after_workout=checkin.coach_notes.decision_after_workout,
        confidence=checkin.confidence,
        evidence_level=checkin.confidence,
        recommendation_action=RecommendationAction.REQUEST_MANUAL_RESOLUTION,
        missing_evidence=_checkin_missing_evidence(checkin),
    )


def _attach_planned_workouts(repo_root: Path, workouts: list[WorkoutRecord]) -> None:
    planned_path = repo_root / "data/plan/planned_workouts.csv"
    if not planned_path.exists():
        return

    with planned_path.open(encoding="utf-8", newline="") as handle:
        planned_rows = list(csv.DictReader(handle))

    used_plans: set[str] = set()
    for workout in workouts:
        if workout.planned_workout_id:
            continue
        candidates = [
            planned
            for planned in planned_rows
            if planned.get("planned_workout_id") not in used_plans
            and planned.get("date") == workout.local_date
            and _planned_category_matches_workout(planned, workout)
        ]
        if len(candidates) > 1:
            ids = ", ".join(row.get("planned_workout_id", "") for row in candidates)
            raise PipelineError(
                "Multiple planned workouts matched executed workout "
                f"{workout.workout_id}: {ids}"
            )
        if len(candidates) == 1:
            planned_id = candidates[0].get("planned_workout_id", "")
            workout.planned_workout_id = planned_id or None
            if planned_id:
                used_plans.add(planned_id)


def _planned_category_matches_workout(
    planned: dict[str, str], workout: WorkoutRecord
) -> bool:
    intended = (planned.get("intended_category") or "").strip().casefold()
    category = (workout.category or "").strip().casefold()
    return bool(intended and category and intended == category)


def _recommendation_for_workout(
    repo_root: Path, workout: WorkoutRecord
) -> RecommendationResult:
    if "checkin" in workout.missing_evidence:
        return RecommendationResult(
            action=RecommendationAction.REQUEST_MANUAL_RESOLUTION,
            decision=DecisionType.DEFER,
            selected_fallback=RecommendationAction.REQUEST_MANUAL_RESOLUTION,
            confidence=Confidence.LOW,
            blocked_by_red_flag=False,
            reasons=["missing_checkin"],
            science_refs=[],
            rule_refs=[],
            missing_evidence=list(workout.missing_evidence),
            assumptions=["Manual check-in is required before deterministic guardrails can evaluate athlete state."],
            phase="unknown",
            week_number=1,
            planned_workout_id=workout.planned_workout_id or "unplanned-next-workout",
        )

    planned = _next_planned_workout(repo_root, workout.local_date)
    recommendation_input = RecommendationInput(
        bruna_pse=workout.bruna_pse,
        symptom_severity=workout.symptom_severity,
        matheus_achilles_morning=workout.matheus_achilles_morning or 0,
        matheus_achilles_after=workout.matheus_achilles_after or 0,
        volleyball_previous_day=bool(workout.volleyball_previous_day),
        poor_sleep=_is_poor_sleep(workout.sleep_quality),
        all_out_race=_is_all_out_race(workout),
        planned_action=RecommendationAction.MAINTAIN_NEXT_WORKOUT,
        phase=planned.get("phase") or "unknown",
        week_number=_safe_int(planned.get("week_number"), default=1),
        planned_workout_id=(
            planned.get("planned_workout_id")
            or workout.planned_workout_id
            or "unplanned-next-workout"
        ),
    )
    return recommend_next_action(recommendation_input)


def _next_planned_workout(repo_root: Path, local_date: str) -> dict[str, str]:
    planned_path = repo_root / "data/plan/planned_workouts.csv"
    if not planned_path.exists():
        return {}

    with planned_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    candidates = [
        row
        for row in rows
        if row.get("status") == "planned" and row.get("date", "") >= local_date
    ]
    if candidates:
        return min(candidates, key=lambda row: row.get("date", ""))
    return {}


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _is_poor_sleep(value: str | None) -> bool:
    if not value:
        return False
    normalized = value.strip().lower()
    return normalized in {"poor", "bad", "ruim", "pessima", "péssima"}


def _is_all_out_race(workout: WorkoutRecord) -> bool:
    category = (workout.category or "").lower()
    notes = (workout.notes or "").lower()
    return any(
        token in f"{category} {notes}"
        for token in ["all_out", "all-out", "maximo", "máximo", "race"]
    )


def _classify_symptom_severity(symptoms: list[str]) -> SymptomSeverity:
    normalized = [symptom.strip().lower() for symptom in symptoms if symptom.strip()]
    if not normalized or all(
        symptom in {"sem sintomas", "none", "no symptoms", "assintomatica", "assintomática"}
        for symptom in normalized
    ):
        return SymptomSeverity.NONE
    red_flag_terms = [
        "tontura",
        "desmaio",
        "dor no peito",
        "visao turva",
        "visão turva",
        "neurologico",
        "neurológico",
        "heat",
        "calor extremo",
    ]
    if any(any(term in symptom for term in red_flag_terms) for symptom in normalized):
        return SymptomSeverity.RED_FLAG
    strong_terms = ["forte", "severo", "severa", "alterou", "limitou", "mecanica", "mecânica"]
    if any(any(term in symptom for term in strong_terms) for symptom in normalized):
        return SymptomSeverity.MODERATE
    return SymptomSeverity.MILD


def _checkin_missing_evidence(checkin: CheckIn) -> list[str]:
    missing = [item for item in checkin.missing_evidence if item != "checkin"]
    if checkin.bruna.avg_hr is None and "bruna_avg_hr" not in missing:
        missing.append("bruna_avg_hr")
    if checkin.bruna.max_hr is None and "bruna_max_hr" not in missing:
        missing.append("bruna_max_hr")
    if (
        checkin.attachments.bruna_hr_screenshot is None
        and "bruna_hr_screenshot" not in missing
    ):
        missing.append("bruna_hr_screenshot")
    return missing


def _workout_csv_row(workout: WorkoutRecord) -> dict[str, Any]:
    row = workout.model_dump(mode="json")
    return {field: _encode_csv_cell(row.get(field)) for field in WORKOUT_FIELDS}


def _encode_csv_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return encode_json_cell(value)
    if isinstance(value, Enum):
        return value.value
    return value


def _decision_from_workout(
    workout: WorkoutRecord, recommendation: RecommendationResult
) -> dict[str, Any]:
    missing_evidence = list(workout.missing_evidence)
    has_checkin = "checkin" not in missing_evidence
    reason = (
        "Manual check-in evidence is missing; confidence remains low."
        if not has_checkin
        else "; ".join(recommendation.reasons)
    )
    return {
        "date": workout.local_date,
        "local_date": workout.local_date,
        "local_datetime": workout.local_datetime,
        "timezone": workout.timezone,
        "event": "pipeline_after_workout",
        "decision": recommendation.decision.value,
        "reason": reason,
        "impact": f"Deterministic guardrail action: {recommendation.action.value}.",
        "related_workout_id": workout.workout_id,
        "evidence": "manual_checkin" if has_checkin else "garmin_only",
        "confidence": recommendation.confidence.value,
        "science_refs": encode_json_cell(recommendation.science_refs),
        "decision_type": recommendation.decision.value,
        "blocked_by_red_flag": recommendation.blocked_by_red_flag,
        "missing_evidence": encode_json_cell(missing_evidence),
        "decision_id": f"decision-{workout.workout_id}",
        "workout_id": workout.workout_id,
        "activity_id": workout.activity_id,
        "recommendation_action": recommendation.action.value,
        "rationale": reason,
    }


def _build_plan_status(
    repo_root: Path,
    workouts: list[WorkoutRecord],
    decisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    planned_path = repo_root / "data/plan/planned_workouts.csv"
    if not planned_path.exists():
        return []

    with planned_path.open(encoding="utf-8", newline="") as handle:
        planned_rows = list(csv.DictReader(handle))

    workouts_by_plan = {
        workout.planned_workout_id: workout
        for workout in workouts
        if workout.planned_workout_id
    }
    decisions_by_workout = {
        decision["workout_id"]: decision
        for decision in decisions
        if decision.get("workout_id")
    }
    latest_date = max((workout.local_date for workout in workouts), default="")
    rows: list[dict[str, Any]] = []
    for planned in planned_rows:
        planned_id = planned.get("planned_workout_id", "")
        matched = workouts_by_plan.get(planned_id)
        related_decision = decisions_by_workout.get(matched.workout_id, {}) if matched else {}
        if matched:
            derived_status = "completed_with_evidence"
            evidence = "matched_workout"
        elif planned.get("date", "") <= latest_date:
            derived_status = "needs_manual_resolution"
            evidence = "planned_without_matched_workout"
        else:
            derived_status = "planned"
            evidence = "future_or_pending"
        rows.append(
            {
                "planned_workout_id": planned_id,
                "week_number": planned.get("week_number", ""),
                "date": planned.get("date", ""),
                "phase": planned.get("phase", ""),
                "intended_category": planned.get("intended_category", ""),
                "planned_status": planned.get("status", ""),
                "derived_status": derived_status,
                "matched_workout_id": matched.workout_id if matched else "",
                "related_decision": related_decision.get("decision", ""),
                "evidence": evidence,
                "missing_evidence": encode_json_cell(matched.missing_evidence) if matched else "[]",
            }
        )
    return rows


def _load_science_refs(repo_root: Path) -> dict[str, ScienceRef]:
    registry = repo_root / "data/knowledge/science_refs.yaml"
    if not registry.exists():
        return {}
    return load_science_refs(registry)


def _science_ref_csv_row(ref: ScienceRef) -> dict[str, Any]:
    row = ref.model_dump(mode="json")
    return {field: _encode_csv_cell(row.get(field)) for field in SCIENCE_REF_FIELDS}


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            {field: _encode_csv_cell(row.get(field)) for field in fieldnames}
            for row in rows
        )


def _write_reports(
    repo_root: Path,
    activities: list[dict[str, Any]],
    workouts: list[WorkoutRecord],
    decisions: list[dict[str, Any]],
    science_refs: dict[str, ScienceRef],
    plan_status: list[dict[str, Any]],
    after_workout: bool,
    monthly_report: bool,
) -> None:
    missing_checkins = sum("checkin" in workout.missing_evidence for workout in workouts)
    mode = "after-workout" if after_workout else "analysis"
    latest_workout = max(workouts, key=lambda workout: workout.local_datetime or "", default=None)
    shared_workouts = [
        workout
        for workout in workouts
        if workout.athlete_context == "shared_run_with_manual_checkin"
    ]
    latest_shared = max(
        shared_workouts, key=lambda workout: workout.local_datetime or "", default=None
    )
    cycle = _load_cycle(repo_root)
    approved_science_count = sum(ref.approved for ref in science_refs.values())
    next_plans = [row for row in plan_status if row.get("derived_status") == "planned"][:3]

    write_text_report(
        repo_root / "docs/state.md",
        "Running Coach State",
        [
            "## Last Update",
            "",
            f"- Mode: {mode}",
            f"- Latest Garmin activity: {_workout_label(latest_workout)}",
            f"- Latest shared coaching evidence: {_workout_label(latest_shared)}",
            f"- Activities processed: {len(activities)}",
            f"- Workouts modeled: {len(workouts)}",
            f"- Missing check-in evidence: {missing_checkins}",
            f"- Approved science refs available: {approved_science_count}",
            "",
            "## Current Phase",
            "",
            f"- Phase: {cycle.get('current_phase', 'unknown')}",
            f"- Week number: {cycle.get('current_week_number', 'unknown')}",
            "- Weekly rhythm: run Tuesday, Thursday, Sunday; strength Monday/Friday and sometimes Saturday; volleyball Wednesday.",
            "",
            "## Current Paces",
            "",
            "- Bruna easy/long run estimate: 6:40-7:00/km.",
            "- Bruna strong sustainable estimate: 6:10-6:20/km.",
            "- Bruna threshold estimate: around 6:00/km when recovered.",
            "- Bruna short all-out ceiling from recent rustic race: around 5:50/km; not continuous training pace.",
            "- Matheus recent solo residual speed: 1.33 km at 4:22/km; not used as Bruna evolution evidence.",
            "",
            "## Current Risks",
            "",
            f"- Missing check-ins: {missing_checkins}.",
            "- Matheus Achilles remains the strategic limiter.",
            "- Volleyball counts as neuromuscular load before Thursday sessions.",
            "- Poor sleep, high PSE, strong symptoms, or heavy legs reduce the next workout.",
            "",
            "## Next Milestones",
            "",
            *[
                f"- {row.get('date')}: {row.get('intended_category')} ({row.get('phase')}) -> {row.get('derived_status')}"
                for row in next_plans
            ],
            "",
            "## Active Decisions",
            "",
            "- Do not compensate missed workouts with volume.",
            "- Keep long runs easy.",
            "- Treat Matheus Garmin physiology as Matheus-only.",
            "- Use shared pace for Bruna only when check-in confirms shared run and Bruna presence.",
        ],
    )
    write_text_report(
        repo_root / "docs/decisions.md",
        "Running Coach Decisions",
        _decision_doc_lines(decisions),
    )
    write_text_report(
        repo_root / "reports/latest-summary.md",
        "Latest Running Coach Summary",
        [
            f"- Activities: {len(activities)}",
            f"- Workouts missing check-in evidence: {missing_checkins}",
            f"- Latest shared evidence: {_workout_label(latest_shared)}",
            f"- Current phase: {cycle.get('current_phase', 'unknown')} week {cycle.get('current_week_number', 'unknown')}",
            f"- Plan status rows: {len(plan_status)}",
            "- Confidence remains low when check-in evidence is absent.",
        ],
    )
    if monthly_report:
        _write_monthly_report(repo_root, workouts, decisions, plan_status)


def _load_cycle(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "data/plan/cycle.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _workout_label(workout: WorkoutRecord | None) -> str:
    if workout is None:
        return "none"
    return (
        f"{workout.local_date} {workout.activity_id} "
        f"{workout.distance_km or ''}km @{workout.avg_pace or 'no pace'}"
    )


def _decision_doc_lines(decisions: list[dict[str, Any]]) -> list[str]:
    lines = [
        "## Summary",
        "",
        f"- Decisions written: {len(decisions)}",
        "- Current V1 decision policy: request manual resolution when check-in evidence is missing.",
        "- Confidence is intentionally low until subjective athlete state is captured.",
        "",
        "## Decision Log",
        "",
        "| Date | Event | Evidence | Decision | Impact | Related Workout | Missing Evidence |",
        "|---|---|---|---|---|---|---|",
    ]
    for decision in decisions:
        lines.append(
            "| {date} | {event} | {evidence} | {decision} | {impact} | {workout} | {missing} |".format(
                date=decision.get("date", ""),
                event=decision.get("event", ""),
                evidence=decision.get("evidence", ""),
                decision=decision.get("decision", ""),
                impact=decision.get("impact", ""),
                workout=decision.get("related_workout_id", ""),
                missing=decision.get("missing_evidence", "[]"),
            )
        )
    return lines


def _write_monthly_report(
    repo_root: Path,
    workouts: list[WorkoutRecord],
    decisions: list[dict[str, Any]],
    plan_status: list[dict[str, Any]],
) -> None:
    latest_date = max((workout.local_date for workout in workouts), default="unknown")
    month = latest_date[:7] if latest_date != "unknown" else "unknown"
    recent = [workout for workout in workouts if workout.local_date.startswith(month)]
    volume = sum(workout.distance_km or 0 for workout in recent)
    long_runs = sum((workout.distance_km or 0) >= 8 for workout in recent)
    quality = sum(
        any(token in (workout.category or "") for token in ["cruise", "quality", "race", "threshold"])
        for workout in recent
    )
    missing_checkins = sum("checkin" in workout.missing_evidence for workout in recent)
    lines = [
        "## Period",
        "",
        f"- Month: {month}",
        f"- Workouts: {len(recent)}",
        "",
        "## Consistency",
        "",
        f"- Total volume: {volume:.2f} km",
        f"- Long runs: {long_runs}",
        f"- Quality/race-like sessions: {quality}",
        "",
        "## Fatigue And Risk",
        "",
        f"- Workouts missing check-in: {missing_checkins}",
        "- Treat missing subjective evidence as low confidence, not as readiness.",
        "",
        "## Decisions",
        "",
        f"- Decisions this dataset: {len(decisions)}",
        f"- Plan status rows: {len(plan_status)}",
        "",
        "## Next 30 Days",
        "",
        "- Keep long runs easy.",
        "- Keep quality controlled and linked to recovery.",
        "- Do not compensate missed sessions with extra volume.",
        "- Preserve Matheus Achilles guardrails.",
    ]
    monthly_dir = repo_root / "reports/monthly"
    write_text_report(monthly_dir / f"{month}.md", "Monthly Running Coach Report", lines)
    write_text_report(monthly_dir / "latest.md", "Monthly Running Coach Report", lines)
