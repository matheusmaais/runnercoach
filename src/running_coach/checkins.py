from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from running_coach.models import Confidence, ExtractionMethod, MatheusRole

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ActivityMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_id: str | None = Field(default=None, min_length=1)
    garmin_title: str | None = None
    garmin_datetime: str | None = None
    distance_km: float | None = Field(default=None, gt=0)


class SessionCheckIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    planned_type: str | None = None
    actual_type: str | None = None
    shared_run: StrictBool


class BrunaCheckIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    avg_hr: int | None = Field(default=None, ge=30, le=240)
    max_hr: int | None = Field(default=None, ge=30, le=240)
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
    model_config = ConfigDict(extra="forbid")

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
    model_config = ConfigDict(extra="forbid")

    extracted_avg_hr: int | None = Field(default=None, ge=30, le=240)
    extracted_max_hr: int | None = Field(default=None, ge=30, le=240)
    extraction_method: ExtractionMethod = ExtractionMethod.NOT_APPLICABLE
    extraction_confidence: Confidence | None = None

    @model_validator(mode="after")
    def confidence_required_for_real_extraction(self) -> BrunaHrExtraction:
        if (
            self.extraction_method != ExtractionMethod.NOT_APPLICABLE
            and self.extraction_confidence is None
        ):
            raise ValueError(
                "extraction_confidence is required when extraction_method is not "
                "not_applicable"
            )
        return self


class Attachments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bruna_hr_screenshot: str | None = None
    bruna_hr_screenshot_sha256: str | None = None
    bruna_hr_extraction: BrunaHrExtraction | None = None

    @field_validator("bruna_hr_screenshot_sha256")
    @classmethod
    def screenshot_sha256_must_be_lower_hex(cls, value: str | None) -> str | None:
        if value is not None and not SHA256_PATTERN.fullmatch(value):
            raise ValueError("bruna_hr_screenshot_sha256 must be 64 lowercase hex chars")
        return value


class CoachNotes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_after_workout: str | None = None


class CheckIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    date: date
    activity_match: ActivityMatch
    session: SessionCheckIn
    bruna: BrunaCheckIn
    matheus: MatheusCheckIn
    attachments: Attachments = Field(default_factory=Attachments)
    coach_notes: CoachNotes = Field(default_factory=CoachNotes)
    missing_evidence: list[str] = Field(default_factory=list)
    confidence: Confidence = Confidence.LOW
