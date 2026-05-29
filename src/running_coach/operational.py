from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from running_coach.checkins import (
    ActivityMatch,
    Attachments,
    BrunaCheckIn,
    CheckIn,
    CoachNotes,
    MatheusCheckIn,
    SessionCheckIn,
)
from running_coach.models import Confidence


class GarminCsvUpload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1)
    content_base64: str = Field(min_length=1)


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
    garmin_csv: GarminCsvUpload | None = None
    workflow: OperationalWorkflow = Field(default_factory=OperationalWorkflow)


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

    checkin_path = _write_checkin(root, intake.checkin) if intake.checkin else None
    garmin_csv_path = _write_garmin_csv(root, intake) if intake.garmin_csv else None

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


def _write_checkin(repo_root: Path, checkin: CheckIn) -> Path:
    title = checkin.activity_match.garmin_title or checkin.activity_match.activity_id
    filename = f"{checkin.date.isoformat()}-{_slug(title)}.yaml"
    path = repo_root / "data/manual/checkins" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = checkin.model_dump(mode="json")
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return path


def _write_garmin_csv(repo_root: Path, intake: FrontendIntake) -> Path:
    if intake.garmin_csv is None:
        raise ValueError("garmin_csv is required")
    timestamp = _timestamp_slug(intake.created_at)
    path = repo_root / "data/raw/garmin" / f"frontend-{timestamp}-{_slug(intake.garmin_csv.filename)}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(intake.garmin_csv.content_base64))
    return path


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
    activity_id: str,
    garmin_title: str | None,
    garmin_datetime: str | None,
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
