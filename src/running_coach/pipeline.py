from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from running_coach.csv_utils import encode_json_cell
from running_coach.garmin import GARMIN_ACTIVITY_FIELDS, parse_garmin_csv_text
from running_coach.models import (
    Confidence,
    MatheusRole,
    RecommendationAction,
    WorkoutRecord,
)
from running_coach.reports import write_text_report
from running_coach.science import ScienceRef, load_science_refs


WORKOUT_FIELDS = [
    "local_date",
    "local_datetime",
    "timezone",
    "workout_id",
    "activity_id",
    "planned_workout_id",
    "participants",
    "shared_run",
    "bruna_present",
    "matheus_role",
    "confidence",
    "evidence_level",
    "match_confidence",
    "recommendation_action",
    "bruna_symptoms",
    "symptom_severity",
    "missing_evidence",
]

DECISION_FIELDS = [
    "decision_id",
    "workout_id",
    "activity_id",
    "local_date",
    "decision_type",
    "recommendation_action",
    "confidence",
    "missing_evidence",
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
    workouts = [_workout_from_activity(activity) for activity in activities]
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


def _workout_from_activity(activity: dict[str, Any]) -> WorkoutRecord:
    return WorkoutRecord(
        local_date=activity["local_date"],
        local_datetime=activity["local_datetime"],
        timezone=activity["timezone"],
        workout_id=f"workout-{activity['activity_id']}",
        activity_id=activity["activity_id"],
        planned_workout_id=None,
        participants=["matheus"],
        shared_run=False,
        bruna_present=False,
        matheus_role=MatheusRole.SOLO,
        confidence=Confidence.LOW,
        evidence_level=Confidence.LOW,
        recommendation_action=RecommendationAction.REQUEST_MANUAL_RESOLUTION,
        missing_evidence=["checkin"],
    )


def _workout_csv_row(workout: WorkoutRecord) -> dict[str, Any]:
    row = workout.model_dump(mode="json")
    row["participants"] = encode_json_cell(row["participants"])
    row["bruna_symptoms"] = encode_json_cell(row["bruna_symptoms"])
    row["missing_evidence"] = encode_json_cell(row["missing_evidence"])
    return row


def _decision_from_workout(workout: WorkoutRecord) -> dict[str, Any]:
    missing_evidence = list(workout.missing_evidence)
    return {
        "decision_id": f"decision-{workout.workout_id}",
        "workout_id": workout.workout_id,
        "activity_id": workout.activity_id,
        "local_date": workout.local_date,
        "decision_type": "defer",
        "recommendation_action": RecommendationAction.REQUEST_MANUAL_RESOLUTION.value,
        "confidence": workout.confidence.value,
        "missing_evidence": encode_json_cell(missing_evidence),
        "rationale": "Manual check-in evidence is missing; confidence remains low.",
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
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
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
