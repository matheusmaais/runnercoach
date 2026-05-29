from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, StrictBool, field_validator, model_validator


TIMEZONE = "America/Sao_Paulo"
KNOWN_PARTICIPANTS = {"matheus", "bruna"}


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Phase(StrEnum):
    TEN_K_POLISH = "ten_k_polish"
    POST_TEN_K_RECOVERY = "post_ten_k_recovery"
    FIVE_TEN_K_DEVELOPMENT = "five_ten_k_development"
    HALF_BASE = "half_base"
    HALF_SPECIFIC = "half_specific"
    HALF_TAPER = "half_taper"


class PlannedWorkoutStatus(StrEnum):
    PLANNED = "planned"
    COMPLETED_AS_PLANNED = "completed_as_planned"
    COMPLETED_MODIFIED = "completed_modified"
    DEFERRED = "deferred"
    SKIPPED = "skipped"
    REPLACED = "replaced"
    CANCELLED = "cancelled"


class DecisionType(StrEnum):
    MAINTAIN = "maintain"
    REDUCE = "reduce"
    ALTER = "alter"
    DEFER = "defer"
    RECOVER = "recover"
    HOLD_PHASE = "hold_phase"
    ADVANCE_PHASE = "advance_phase"
    RACE_STRATEGY = "race_strategy"


class RecommendationAction(StrEnum):
    MAINTAIN_NEXT_WORKOUT = "maintain_next_workout"
    REDUCE_NEXT_WORKOUT = "reduce_next_workout"
    REPLACE_WITH_EASY = "replace_with_easy"
    REPLACE_WITH_OFF = "replace_with_off"
    REPLACE_WITH_CROSS_TRAINING = "replace_with_cross_training"
    DEFER_QUALITY = "defer_quality"
    BRUNA_WITHOUT_MATHEUS = "bruna_without_matheus"
    REQUEST_MANUAL_RESOLUTION = "request_manual_resolution"


class SymptomSeverity(StrEnum):
    NONE = "none"
    MILD = "mild"
    MODERATE = "moderate"
    RED_FLAG = "red_flag"


class MatheusRole(StrEnum):
    PACER = "pacer"
    SOLO = "solo"
    SUPPORT = "support"
    NOT_PRESENT = "not_present"


class SourceType(StrEnum):
    PEER_REVIEWED_STUDY = "peer_reviewed_study"
    POSITION_STAND = "position_stand"
    TEXTBOOK_OR_BOOK = "textbook_or_book"
    COACHING_FRAMEWORK = "coaching_framework"
    GOVERNING_BODY_GUIDANCE = "governing_body_guidance"


class ExtractionMethod(StrEnum):
    MANUAL_READ = "manual_read"
    OCR = "ocr"
    NOT_APPLICABLE = "not_applicable"


class WorkoutRecord(BaseModel):
    local_date: str
    local_datetime: str | None = None
    timezone: Literal["America/Sao_Paulo"]
    workout_id: str
    activity_id: str
    planned_workout_id: str | None = None
    participants: list[str]
    shared_run: StrictBool
    bruna_present: StrictBool
    matheus_role: MatheusRole
    confidence: Confidence
    evidence_level: Confidence
    match_confidence: Confidence = Confidence.HIGH
    recommendation_action: RecommendationAction | None = None
    bruna_symptoms: list[str] = Field(default_factory=list)
    symptom_severity: SymptomSeverity = SymptomSeverity.NONE
    missing_evidence: list[str] = Field(default_factory=list)

    @field_validator("participants")
    @classmethod
    def participants_must_be_known(cls, value: list[str]) -> list[str]:
        unknown = sorted(set(value) - KNOWN_PARTICIPANTS)
        if unknown:
            raise ValueError(f"unknown participants: {unknown}")
        return value

    @model_validator(mode="after")
    def participant_invariants_are_consistent(self) -> WorkoutRecord:
        participants = set(self.participants)
        if len(participants) != len(self.participants):
            raise ValueError("participants must be unique")
        if self.shared_run and (
            participants != KNOWN_PARTICIPANTS or not self.bruna_present
        ):
            raise ValueError(
                "shared_run requires matheus and bruna participants and bruna_present"
            )
        if self.bruna_present and "bruna" not in participants:
            raise ValueError("bruna_present requires bruna in participants")
        if self.matheus_role == MatheusRole.NOT_PRESENT and "matheus" in participants:
            raise ValueError("matheus_role=not_present requires matheus absent")
        if "matheus" not in participants and self.matheus_role != MatheusRole.NOT_PRESENT:
            raise ValueError("matheus absent requires matheus_role=not_present")
        return self
