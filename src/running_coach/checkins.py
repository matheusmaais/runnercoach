from __future__ import annotations

import hashlib
from datetime import date as Date
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, StrictBool, field_validator

from running_coach.models import Confidence, ExtractionMethod, MatheusRole


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ActivityMatch(BaseModel):
    activity_id: str
    garmin_title: str | None = None
    garmin_datetime: str | None = None


class SessionCheckIn(BaseModel):
    planned_type: str | None = None
    actual_type: str | None = None
    shared_run: StrictBool


class BrunaCheckIn(BaseModel):
    avg_hr: int | None = None
    max_hr: int | None = None
    pse: int | None = None
    symptoms: list[str] = Field(default_factory=list)
    sleep_quality: str | None = None
    volleyball_previous_day: bool | None = None
    gym_previous_day: bool | None = None
    lower_body_load_previous_day: str | None = None
    subjective: str | None = None
    could_repeat_last_block: bool | None = None

    @field_validator("pse")
    @classmethod
    def pse_must_be_in_range(cls, value: int | None) -> int | None:
        if value is not None and not 0 <= value <= 10:
            raise ValueError("pse must be between 0 and 10")
        return value


class MatheusCheckIn(BaseModel):
    achilles_morning: int
    achilles_after: int
    role: MatheusRole
    subjective: str | None = None

    @field_validator("achilles_morning", "achilles_after")
    @classmethod
    def achilles_must_be_in_range(cls, value: int) -> int:
        if not 0 <= value <= 10:
            raise ValueError("achilles score must be between 0 and 10")
        return value


class BrunaHrExtraction(BaseModel):
    extracted_avg_hr: int | None = None
    extracted_max_hr: int | None = None
    extraction_method: ExtractionMethod = ExtractionMethod.NOT_APPLICABLE
    extraction_confidence: Confidence | None = None


class Attachments(BaseModel):
    bruna_hr_screenshot: str | None = None
    bruna_hr_screenshot_sha256: str | None = None
    bruna_hr_extraction: BrunaHrExtraction | None = None


class CoachNotes(BaseModel):
    decision_after_workout: str | None = None


class CheckIn(BaseModel):
    schema_version: int
    date: str
    activity_match: ActivityMatch
    session: SessionCheckIn
    bruna: BrunaCheckIn
    matheus: MatheusCheckIn
    attachments: Attachments = Field(default_factory=Attachments)
    coach_notes: CoachNotes = Field(default_factory=CoachNotes)

    @field_validator("date", mode="before")
    @classmethod
    def date_must_be_iso_string(cls, value: Any) -> str:
        if isinstance(value, Date):
            return value.isoformat()
        return value
