from __future__ import annotations

import json
import re
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from running_coach.checkins import (
    ActivityMatch,
    Attachments,
    BrunaCheckIn,
    CheckIn,
    CoachNotes,
    MatheusCheckIn,
    SessionCheckIn,
)
from running_coach.garmin import make_activity_id, matches_activity_keys
from running_coach.models import Confidence


class GarminActivitySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_filename: str | None = None
    activity_id: str | None = Field(default=None, min_length=1)
    local_date: str
    local_datetime: str | None = None
    timezone: Literal["America/Sao_Paulo"] = "America/Sao_Paulo"
    activity_type: str | None = None
    title: str | None = None
    distance_km: float | None = None
    duration_seconds: float | None = None
    avg_pace: str | None = None
    best_pace: str | None = None


class OperationalWorkflow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_llm: bool = True
    commit_results: bool = True


class FrontendIntake(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    created_at: str
    source: Literal["github_pages"]
    checkin: CheckIn | None = None
    garmin_activity: GarminActivitySummary | None = None
    workflow: OperationalWorkflow = Field(default_factory=OperationalWorkflow)

    @model_validator(mode="after")
    def garmin_summary_matches_checkin(self) -> FrontendIntake:
        if self.checkin and self.garmin_activity:
            checkin_activity_id = self.checkin.activity_match.activity_id
            if (
                checkin_activity_id
                and self.garmin_activity.activity_id
                and self.garmin_activity.activity_id != checkin_activity_id
            ):
                raise ValueError("garmin_activity.activity_id must match checkin.activity_match.activity_id")
        return self


@dataclass(frozen=True)
class ProcessedIntake:
    checkin_path: Path | None
    garmin_csv_path: Path | None
    run_llm: bool
    commit_results: bool


def process_frontend_intake(repo_root: Path, intake_path: Path) -> ProcessedIntake:
    root = repo_root.resolve()
    source_path = intake_path if intake_path.is_absolute() else root / intake_path
    intake = FrontendIntake.model_validate_json(source_path.read_text(encoding="utf-8"))

    checkin_path = (
        _write_checkin(root, intake.checkin, intake.garmin_activity)
        if intake.checkin
        else None
    )
    garmin_csv_path = (
        _write_sanitized_garmin_csv(root, intake)
        if intake.garmin_activity
        else None
    )

    return ProcessedIntake(
        checkin_path=checkin_path,
        garmin_csv_path=garmin_csv_path,
        run_llm=intake.workflow.run_llm,
        commit_results=intake.workflow.commit_results,
    )


def write_frontend_intake(repo_root: Path, payload: dict) -> Path:
    intake = FrontendIntake.model_validate(payload)
    root = repo_root.resolve()
    timestamp = _timestamp_slug(intake.created_at)
    path = root / "data/manual/frontend_intake" / f"{timestamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(intake.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _write_checkin(
    repo_root: Path,
    checkin: CheckIn,
    garmin_activity: GarminActivitySummary | None = None,
) -> Path:
    checkin = _checkin_with_resolved_activity_id(checkin, garmin_activity)
    activity_id = checkin.activity_match.activity_id
    existing_path = _existing_checkin_path(repo_root, activity_id)
    title = checkin.activity_match.garmin_title or activity_id or checkin.date.isoformat()
    path = existing_path or repo_root / "data/manual/checkins" / f"{checkin.date.isoformat()}-{_slug(title)}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = checkin.model_dump(mode="json")
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return path


def _existing_checkin_path(repo_root: Path, activity_id: str | None) -> Path | None:
    if not activity_id:
        return None
    checkins_dir = repo_root / "data/manual/checkins"
    if not checkins_dir.exists():
        return None
    for path in sorted(checkins_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        existing = (data.get("activity_match") or {}).get("activity_id")
        if existing == activity_id:
            return path
    return None


def _checkin_with_resolved_activity_id(
    checkin: CheckIn,
    garmin_activity: GarminActivitySummary | None,
) -> CheckIn:
    match = checkin.activity_match
    if match.activity_id or garmin_activity is None:
        return checkin

    activity = garmin_activity.model_dump(mode="json")
    if not matches_activity_keys(
        activity,
        date=checkin.date.isoformat(),
        garmin_title=match.garmin_title,
        garmin_datetime=match.garmin_datetime,
        distance_km=match.distance_km,
    ):
        raise ValueError("garmin_activity summary does not match check-in activity keys")

    activity_id = garmin_activity.activity_id or _derive_activity_id(garmin_activity)
    if activity_id is None:
        return checkin
    return checkin.model_copy(
        update={
            "activity_match": match.model_copy(update={"activity_id": activity_id})
        }
    )


def _derive_activity_id(activity: GarminActivitySummary) -> str | None:
    if (
        not activity.local_datetime
        or activity.distance_km is None
        or activity.duration_seconds is None
        or not activity.title
    ):
        return None
    return make_activity_id(
        activity.local_datetime,
        activity.distance_km,
        activity.duration_seconds,
        activity.title,
    )


def _write_sanitized_garmin_csv(repo_root: Path, intake: FrontendIntake) -> Path:
    activity = intake.garmin_activity
    if activity is None:
        raise ValueError("garmin_activity is required to write a sanitized Garmin CSV")
    missing = [
        field
        for field, value in {
            "local_datetime": activity.local_datetime,
            "title": activity.title,
            "distance_km": activity.distance_km,
            "duration_seconds": activity.duration_seconds,
        }.items()
        if value in {None, ""}
    ]
    if missing:
        raise ValueError(
            "garmin_activity summary cannot build sanitized Garmin CSV; "
            f"missing {', '.join(missing)}"
        )

    target_dir = repo_root / ".runnercoach" / "tmp" / "frontend-intake"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{_timestamp_slug(intake.created_at)}-garmin-sanitized.csv"
    activity_type = _garmin_activity_type(activity.activity_type)

    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "activity_id",
                "Tipo de atividade",
                "Data",
                "Título",
                "Distância",
                "Tempo",
                "Ritmo médio",
                "Melhor ritmo",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "activity_id": activity.activity_id or _derive_activity_id(activity) or "",
                "Tipo de atividade": activity_type,
                "Data": activity.local_datetime,
                "Título": activity.title,
                "Distância": f"{float(activity.distance_km):.2f}",
                "Tempo": _duration_hhmmss(float(activity.duration_seconds)),
                "Ritmo médio": activity.avg_pace or "",
                "Melhor ritmo": activity.best_pace or "",
            }
        )
    return target


def _garmin_activity_type(value: str | None) -> str:
    normalized = (value or "").strip().casefold()
    if normalized in {"running", "run", "corrida"}:
        return "Corrida"
    return value or "Corrida"


def _duration_hhmmss(seconds: float) -> str:
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "intake"


def _timestamp_slug(value: str) -> str:
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return _slug(value)
    return parsed.strftime("%Y%m%dT%H%M%SZ")


def checkin_from_frontend(
    *,
    date: str,
    confidence: str,
    activity_id: str | None,
    garmin_title: str | None,
    garmin_datetime: str | None,
    distance_km: float | None = None,
    planned_type: str | None,
    actual_type: str | None,
    shared_run: bool,
    bruna: dict,
    matheus: dict,
    coach_note: str | None,
) -> CheckIn:
    return CheckIn(
        schema_version=1,
        date=date,
        confidence=Confidence(confidence),
        activity_match=ActivityMatch(
            activity_id=activity_id,
            garmin_title=garmin_title,
            garmin_datetime=garmin_datetime,
            distance_km=distance_km,
        ),
        session=SessionCheckIn(
            planned_type=planned_type,
            actual_type=actual_type,
            shared_run=shared_run,
        ),
        bruna=BrunaCheckIn(**bruna),
        matheus=MatheusCheckIn(**matheus),
        attachments=Attachments(),
        coach_notes=CoachNotes(decision_after_workout=coach_note),
        missing_evidence=_missing_evidence(bruna),
    )


def _missing_evidence(bruna: dict) -> list[str]:
    missing = []
    if bruna.get("avg_hr") in {None, ""}:
        missing.append("bruna_avg_hr")
    if bruna.get("max_hr") in {None, ""}:
        missing.append("bruna_max_hr")
    return missing
