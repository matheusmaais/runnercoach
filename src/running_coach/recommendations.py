from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from running_coach.models import Confidence, RecommendationAction, SymptomSeverity


class RecommendationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bruna_pse: int | None = None
    symptom_severity: SymptomSeverity
    matheus_achilles_morning: int
    matheus_achilles_after: int
    volleyball_previous_day: StrictBool
    poor_sleep: StrictBool
    all_out_race: StrictBool
    planned_action: RecommendationAction
    phase: str = Field(min_length=1)
    week_number: int = Field(ge=1)
    planned_workout_id: str = Field(min_length=1)

    @field_validator("bruna_pse")
    @classmethod
    def pse_must_be_in_range(cls, value: int | None) -> int | None:
        if value is not None and not 0 <= value <= 10:
            raise ValueError("bruna_pse must be between 0 and 10")
        return value

    @field_validator("matheus_achilles_morning", "matheus_achilles_after")
    @classmethod
    def achilles_must_be_in_range(cls, value: int) -> int:
        if not 0 <= value <= 10:
            raise ValueError("achilles score must be between 0 and 10")
        return value


class RecommendationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: RecommendationAction
    confidence: Confidence
    blocked_by_red_flag: bool
    reasons: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    phase: str
    week_number: int
    planned_workout_id: str


def recommend_next_action(input_data: RecommendationInput) -> RecommendationResult:
    missing_evidence: list[str] = []
    assumptions: list[str] = []
    confidence = Confidence.HIGH

    if input_data.bruna_pse is None:
        missing_evidence.append("bruna_pse")
        assumptions.append(
            "Bruna PSE was not provided; recommendation uses available guardrails only."
        )
        confidence = Confidence.MEDIUM

    action, reasons, blocked_by_red_flag = _select_action(input_data)
    if _is_high_confidence_hard_stop(action, blocked_by_red_flag):
        confidence = Confidence.HIGH

    return RecommendationResult(
        action=action,
        confidence=confidence,
        blocked_by_red_flag=blocked_by_red_flag,
        reasons=reasons,
        missing_evidence=missing_evidence,
        assumptions=assumptions,
        phase=input_data.phase,
        week_number=input_data.week_number,
        planned_workout_id=input_data.planned_workout_id,
    )


def _select_action(
    input_data: RecommendationInput,
) -> tuple[RecommendationAction, list[str], bool]:
    if input_data.symptom_severity == SymptomSeverity.RED_FLAG:
        return (
            RecommendationAction.REPLACE_WITH_OFF,
            ["red_flag_symptoms"],
            True,
        )

    if _max_achilles(input_data) >= 5:
        return (
            RecommendationAction.BRUNA_WITHOUT_MATHEUS,
            ["matheus_achilles_at_least_5"],
            False,
        )

    if input_data.bruna_pse is not None and input_data.bruna_pse >= 9:
        return (
            RecommendationAction.REPLACE_WITH_EASY,
            ["bruna_pse_at_least_9"],
            False,
        )

    if _max_achilles(input_data) >= 3:
        return (
            RecommendationAction.DEFER_QUALITY,
            ["matheus_achilles_between_3_and_4"],
            False,
        )

    load_reasons = _load_reduction_reasons(input_data)
    if load_reasons:
        return (
            RecommendationAction.REDUCE_NEXT_WORKOUT,
            load_reasons,
            False,
        )

    return (
        input_data.planned_action,
        ["no_guardrail_triggered"],
        False,
    )


def _max_achilles(input_data: RecommendationInput) -> int:
    return max(input_data.matheus_achilles_morning, input_data.matheus_achilles_after)


def _load_reduction_reasons(input_data: RecommendationInput) -> list[str]:
    reasons: list[str] = []
    if input_data.volleyball_previous_day:
        reasons.append("volleyball_previous_day")
    if input_data.poor_sleep:
        reasons.append("poor_sleep")
    if input_data.all_out_race:
        reasons.append("all_out_race")
    return reasons


def _is_high_confidence_hard_stop(
    action: RecommendationAction, blocked_by_red_flag: bool
) -> bool:
    return blocked_by_red_flag or action == RecommendationAction.BRUNA_WITHOUT_MATHEUS
