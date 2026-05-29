from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from running_coach.models import (
    Confidence,
    DecisionType,
    RecommendationAction,
    SymptomSeverity,
)


class RecommendationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bruna_pse: StrictInt | None = Field(default=None, ge=0, le=10)
    symptom_severity: SymptomSeverity
    matheus_achilles_morning: StrictInt = Field(ge=0, le=10)
    matheus_achilles_after: StrictInt = Field(ge=0, le=10)
    volleyball_previous_day: StrictBool
    poor_sleep: StrictBool
    all_out_race: StrictBool
    planned_action: RecommendationAction
    phase: str = Field(min_length=1)
    week_number: StrictInt = Field(ge=1)
    planned_workout_id: str = Field(min_length=1)


class RecommendationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: RecommendationAction
    decision: DecisionType
    selected_fallback: RecommendationAction | None
    confidence: Confidence
    blocked_by_red_flag: bool
    reasons: list[str] = Field(default_factory=list)
    science_refs: list[str] = Field(default_factory=list)
    rule_refs: list[str] = Field(default_factory=list)
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
    assumptions.extend(_assumptions_for(reasons))
    if _is_high_confidence_hard_stop(action, blocked_by_red_flag):
        confidence = Confidence.HIGH

    science_refs = _rule_refs_for(reasons)
    return RecommendationResult(
        action=action,
        decision=_decision_for(action, reasons),
        selected_fallback=_selected_fallback(action, input_data.planned_action),
        confidence=confidence,
        blocked_by_red_flag=blocked_by_red_flag,
        reasons=reasons,
        science_refs=science_refs,
        rule_refs=science_refs,
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
            ["red_flag_symptom"],
            True,
        )

    reasons = _guardrail_reasons(input_data)
    reason_tags = set(reasons)

    if "bruna_strong_symptoms" in reason_tags:
        return (
            RecommendationAction.REDUCE_NEXT_WORKOUT,
            reasons,
            False,
        )

    if "bruna_pse_ge_9" in reason_tags and "all_out_race" in reason_tags:
        return (
            RecommendationAction.REPLACE_WITH_OFF,
            reasons,
            False,
        )

    if "bruna_pse_ge_9" in reason_tags:
        return (
            RecommendationAction.REPLACE_WITH_EASY,
            reasons,
            False,
        )

    if "matheus_achilles_ge_5" in reason_tags:
        return (
            RecommendationAction.BRUNA_WITHOUT_MATHEUS,
            reasons,
            False,
        )

    if "matheus_achilles_ge_3" in reason_tags:
        return (
            RecommendationAction.DEFER_QUALITY,
            reasons,
            False,
        )

    if reasons:
        return (
            RecommendationAction.REDUCE_NEXT_WORKOUT,
            reasons,
            False,
        )

    return (
        input_data.planned_action,
        ["within_guardrails"],
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


def _guardrail_reasons(input_data: RecommendationInput) -> list[str]:
    reasons: list[str] = []
    if input_data.bruna_pse is not None and input_data.bruna_pse >= 9:
        reasons.append("bruna_pse_ge_9")
    if input_data.symptom_severity == SymptomSeverity.MODERATE:
        reasons.append("bruna_strong_symptoms")
    if _max_achilles(input_data) >= 5:
        reasons.append("matheus_achilles_ge_5")
    elif _max_achilles(input_data) >= 3:
        reasons.append("matheus_achilles_ge_3")
    reasons.extend(_load_reduction_reasons(input_data))
    return reasons


def _selected_fallback(
    action: RecommendationAction, planned_action: RecommendationAction
) -> RecommendationAction | None:
    if action == planned_action:
        return None
    return action


def _decision_for(action: RecommendationAction, reasons: list[str]) -> DecisionType:
    reason_tags = set(reasons)
    if action == RecommendationAction.MAINTAIN_NEXT_WORKOUT:
        return DecisionType.MAINTAIN
    if action == RecommendationAction.REQUEST_MANUAL_RESOLUTION:
        return DecisionType.DEFER
    if "red_flag_symptom" in reason_tags or "all_out_race" in reason_tags:
        return DecisionType.RECOVER
    if "bruna_pse_ge_9" in reason_tags:
        return DecisionType.RECOVER
    if "bruna_strong_symptoms" in reason_tags:
        return DecisionType.REDUCE
    if "matheus_achilles_ge_5" in reason_tags:
        return DecisionType.ALTER
    if "matheus_achilles_ge_3" in reason_tags:
        return DecisionType.DEFER
    if action == RecommendationAction.REDUCE_NEXT_WORKOUT:
        return DecisionType.REDUCE
    if action == RecommendationAction.DEFER_QUALITY:
        return DecisionType.DEFER
    return DecisionType.ALTER


def _rule_refs_for(reasons: list[str]) -> list[str]:
    reason_tags = set(reasons)
    refs: list[str] = []
    if "red_flag_symptom" in reason_tags:
        refs.append("safety-red-flag-conservative")
    if "bruna_pse_ge_9" in reason_tags:
        refs.append("load-management-recovery")
    if "bruna_strong_symptoms" in reason_tags:
        refs.append("load-management-recovery")
    if reason_tags & {"matheus_achilles_ge_5", "matheus_achilles_ge_3"}:
        refs.append("achilles-tendinopathy-load")
    if reason_tags & {"volleyball_previous_day", "poor_sleep", "all_out_race"}:
        if "volleyball_previous_day" in reason_tags:
            refs.append("volleyball-neuromuscular-load")
        else:
            refs.append("sleep-fatigue-load-management")
    if refs:
        return refs
    return ["training-consistency-principle"]


def _assumptions_for(reasons: list[str]) -> list[str]:
    if "matheus_achilles_ge_5" in set(reasons):
        return ["Matheus should not pace while Achilles severity is at least 5."]
    return []


def _is_high_confidence_hard_stop(
    action: RecommendationAction, blocked_by_red_flag: bool
) -> bool:
    return blocked_by_red_flag or action == RecommendationAction.BRUNA_WITHOUT_MATHEUS
