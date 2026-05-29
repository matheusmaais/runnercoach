from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import yaml

from running_coach.checkins import CheckIn
from running_coach.csv_utils import encode_json_cell
from running_coach.garmin import GARMIN_ACTIVITY_FIELDS, parse_garmin_csv_text
from running_coach.models import (
    Confidence,
    DecisionType,
    MatheusRole,
    RecommendationAction,
    WorkoutRecord,
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

DECISION_FIELDS = [
    "date",
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
    "local_date",
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


def run_pipeline(garmin_csv: Path, repo_root: Path, after_workout: bool) -> None:
    garmin_csv = Path(garmin_csv)
    repo_root = Path(repo_root)

    activities = parse_garmin_csv_text(
        garmin_csv.read_text(encoding="utf-8-sig"), source_file=garmin_csv.name
    )
    checkins = _load_checkins(repo_root)
    workouts = [
        _workout_from_activity(activity, checkins.get(activity["activity_id"]))
        for activity in activities
    ]
    decisions = [_decision_from_workout(workout) for workout in workouts]
    science_refs = _load_science_refs(repo_root)

    processed_dir = repo_root / "data/processed"
    _write_csv(processed_dir / "activities.csv", GARMIN_ACTIVITY_FIELDS, activities)
    _write_csv(
        processed_dir / "workouts.csv",
        WORKOUT_FIELDS,
        [_workout_csv_row(workout) for workout in workouts],
    )
    _write_csv(processed_dir / "decisions.csv", DECISION_FIELDS, decisions)
    _write_csv(
        processed_dir / "science_refs.csv",
        SCIENCE_REF_FIELDS,
        [_science_ref_csv_row(ref) for ref in science_refs.values()],
    )

    _write_reports(repo_root, activities, workouts, decisions, science_refs, after_workout)


def _load_checkins(repo_root: Path) -> dict[str, CheckIn]:
    checkins_dir = repo_root / "data/manual/checkins"
    if not checkins_dir.exists():
        return {}

    checkins: dict[str, CheckIn] = {}
    for path in sorted(checkins_dir.glob("*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        checkin = CheckIn.model_validate(payload)
        checkins[checkin.activity_match.activity_id] = checkin
    return checkins


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
    row["participants"] = encode_json_cell(row["participants"])
    row["bruna_symptoms"] = encode_json_cell(row["bruna_symptoms"])
    row["missing_evidence"] = encode_json_cell(row["missing_evidence"])
    return row


def _decision_from_workout(workout: WorkoutRecord) -> dict[str, Any]:
    missing_evidence = list(workout.missing_evidence)
    has_checkin = "checkin" not in missing_evidence
    decision_type = DecisionType.DEFER
    reason = (
        "Manual check-in evidence is missing; confidence remains low."
        if not has_checkin
        else "Manual check-in matched; recommendation remains deferred until adaptive engine consumes full context."
    )
    return {
        "date": workout.local_date,
        "event": "pipeline_after_workout",
        "decision": decision_type.value,
        "reason": reason,
        "impact": "No automatic workout change in Task 7; preserve audit trail for recommendation engine.",
        "related_workout_id": workout.workout_id,
        "evidence": "manual_checkin" if has_checkin else "garmin_only",
        "confidence": workout.confidence.value,
        "science_refs": encode_json_cell([]),
        "decision_type": decision_type.value,
        "blocked_by_red_flag": "false",
        "missing_evidence": encode_json_cell(missing_evidence),
        "decision_id": f"decision-{workout.workout_id}",
        "workout_id": workout.workout_id,
        "activity_id": workout.activity_id,
        "local_date": workout.local_date,
        "recommendation_action": RecommendationAction.REQUEST_MANUAL_RESOLUTION.value,
        "rationale": reason,
    }


def _load_science_refs(repo_root: Path) -> dict[str, ScienceRef]:
    registry = repo_root / "data/knowledge/science_refs.yaml"
    if not registry.exists():
        return {}
    return load_science_refs(registry)


def _science_ref_csv_row(ref: ScienceRef) -> dict[str, Any]:
    row = ref.model_dump(mode="json")
    row["authors"] = encode_json_cell(row["authors"])
    row["tags"] = encode_json_cell(row["tags"])
    return row


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_reports(
    repo_root: Path,
    activities: list[dict[str, Any]],
    workouts: list[WorkoutRecord],
    decisions: list[dict[str, Any]],
    science_refs: dict[str, ScienceRef],
    after_workout: bool,
) -> None:
    missing_checkins = sum("checkin" in workout.missing_evidence for workout in workouts)
    mode = "after-workout" if after_workout else "analysis"

    write_text_report(
        repo_root / "docs/state.md",
        "Running Coach State",
        [
            f"- Mode: {mode}",
            f"- Activities processed: {len(activities)}",
            f"- Workouts modeled: {len(workouts)}",
            f"- Missing check-in evidence: {missing_checkins}",
            f"- Approved science refs available: {sum(ref.approved for ref in science_refs.values())}",
        ],
    )
    write_text_report(
        repo_root / "docs/decisions.md",
        "Running Coach Decisions",
        [
            f"- Decisions written: {len(decisions)}",
            "- Current V1 decision policy: request manual resolution when check-in evidence is missing.",
            "- Confidence is intentionally low until subjective athlete state is captured.",
        ],
    )
    write_text_report(
        repo_root / "reports/latest-summary.md",
        "Latest Running Coach Summary",
        [
            f"- Activities: {len(activities)}",
            f"- Workouts missing check-in evidence: {missing_checkins}",
            "- Confidence: low when check-in evidence is absent.",
        ],
    )
