import pytest
from pydantic import ValidationError

from running_coach.models import (
    Confidence,
    DecisionType,
    RecommendationAction,
    SymptomSeverity,
)
from running_coach.recommendations import RecommendationInput, recommend_next_action


def recommendation_input(**overrides):
    values = {
        "bruna_pse": 6,
        "symptom_severity": SymptomSeverity.NONE,
        "matheus_achilles_morning": 0,
        "matheus_achilles_after": 0,
        "volleyball_previous_day": False,
        "poor_sleep": False,
        "all_out_race": False,
        "planned_action": RecommendationAction.MAINTAIN_NEXT_WORKOUT,
        "phase": "ten_k_polish",
        "week_number": 1,
        "planned_workout_id": "plan-1",
    }
    values.update(overrides)
    return RecommendationInput(**values)


def test_red_flag_suppresses_performance():
    result = recommend_next_action(
        recommendation_input(
            bruna_pse=9,
            symptom_severity=SymptomSeverity.RED_FLAG,
            planned_action=RecommendationAction.MAINTAIN_NEXT_WORKOUT,
        )
    )

    assert result.action == RecommendationAction.REPLACE_WITH_OFF
    assert result.blocked_by_red_flag is True
    assert result.confidence == Confidence.HIGH
    assert result.decision == DecisionType.RECOVER
    assert result.selected_fallback == RecommendationAction.REPLACE_WITH_OFF
    assert result.science_refs == []
    assert result.rule_refs
    assert result.reasons


def test_pse_nine_forces_easy_or_off():
    result = recommend_next_action(recommendation_input(bruna_pse=9))

    assert result.action == RecommendationAction.REPLACE_WITH_EASY
    assert result.blocked_by_red_flag is False


def test_achilles_three_defers_quality():
    result = recommend_next_action(
        recommendation_input(matheus_achilles_morning=3, matheus_achilles_after=4)
    )

    assert result.action == RecommendationAction.DEFER_QUALITY


def test_achilles_five_recommends_bruna_without_matheus_or_cross_training():
    result = recommend_next_action(
        recommendation_input(matheus_achilles_morning=5, matheus_achilles_after=2)
    )

    assert result.action == RecommendationAction.BRUNA_WITHOUT_MATHEUS
    assert result.action != RecommendationAction.REPLACE_WITH_CROSS_TRAINING
    assert result.confidence == Confidence.HIGH


def test_combined_pse_nine_and_achilles_five_prioritizes_bruna_recovery():
    result = recommend_next_action(
        recommendation_input(bruna_pse=9, matheus_achilles_morning=5)
    )

    assert result.action == RecommendationAction.REPLACE_WITH_EASY
    assert result.decision == DecisionType.RECOVER
    assert result.selected_fallback == RecommendationAction.REPLACE_WITH_EASY
    assert "bruna_pse_ge_9" in result.reasons
    assert "matheus_achilles_ge_5" in result.reasons
    assert result.science_refs == []
    assert result.rule_refs == [
        "load-management-recovery",
        "achilles-tendinopathy-load",
    ]
    assert result.assumptions


def test_red_flag_overrides_combined_guardrails():
    result = recommend_next_action(
        recommendation_input(
            bruna_pse=9,
            symptom_severity=SymptomSeverity.RED_FLAG,
            matheus_achilles_morning=5,
            all_out_race=True,
        )
    )

    assert result.action == RecommendationAction.REPLACE_WITH_OFF
    assert result.decision == DecisionType.RECOVER
    assert result.selected_fallback == RecommendationAction.REPLACE_WITH_OFF


def test_volleyball_previous_day_reduces_next_workout():
    result = recommend_next_action(recommendation_input(volleyball_previous_day=True))

    assert result.action == RecommendationAction.REDUCE_NEXT_WORKOUT
    assert result.decision == DecisionType.REDUCE
    assert result.science_refs == []
    assert result.rule_refs == ["volleyball-neuromuscular-load"]


def test_poor_sleep_reduces_next_workout():
    result = recommend_next_action(recommendation_input(poor_sleep=True))

    assert result.action == RecommendationAction.REDUCE_NEXT_WORKOUT
    assert result.decision == DecisionType.REDUCE
    assert result.science_refs == []
    assert result.rule_refs == ["sleep-fatigue-load-management"]


def test_all_out_race_reduces_next_workout():
    result = recommend_next_action(recommendation_input(all_out_race=True))

    assert result.action == RecommendationAction.REDUCE_NEXT_WORKOUT
    assert result.decision == DecisionType.RECOVER
    assert result.science_refs == []
    assert result.rule_refs == ["sleep-fatigue-load-management"]


def test_missing_bruna_pse_records_missing_evidence_and_medium_confidence():
    result = recommend_next_action(recommendation_input(bruna_pse=None))

    assert result.action == RecommendationAction.MAINTAIN_NEXT_WORKOUT
    assert result.decision == DecisionType.MAINTAIN
    assert result.selected_fallback is None
    assert result.confidence == Confidence.MEDIUM
    assert result.missing_evidence == ["bruna_pse"]
    assert result.assumptions


def test_output_includes_phase_week_and_planned_workout_id():
    result = recommend_next_action(
        recommendation_input(
            phase="half_base",
            week_number=7,
            planned_workout_id="half-base-w7-easy",
        )
    )

    assert result.phase == "half_base"
    assert result.week_number == 7
    assert result.planned_workout_id == "half-base-w7-easy"
    assert isinstance(result.reasons, list)
    assert isinstance(result.assumptions, list)
    assert isinstance(result.missing_evidence, list)
    dumped = result.model_dump()
    assert dumped["decision"] == DecisionType.MAINTAIN
    assert dumped["selected_fallback"] is None
    assert dumped["science_refs"] == []
    assert dumped["rule_refs"] == ["training-consistency-principle"]


def test_maintain_planned_action_has_no_selected_fallback():
    result = recommend_next_action(
        recommendation_input(planned_action=RecommendationAction.MAINTAIN_NEXT_WORKOUT)
    )

    assert result.action == RecommendationAction.MAINTAIN_NEXT_WORKOUT
    assert result.decision == DecisionType.MAINTAIN
    assert result.selected_fallback is None
    assert result.science_refs == []
    assert result.rule_refs == ["training-consistency-principle"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("bruna_pse", "9"),
        ("bruna_pse", True),
        ("matheus_achilles_morning", "5"),
        ("week_number", 1.0),
    ],
)
def test_numeric_inputs_are_strict(field, value):
    values = {
        "bruna_pse": 6,
        "symptom_severity": SymptomSeverity.NONE,
        "matheus_achilles_morning": 0,
        "matheus_achilles_after": 0,
        "volleyball_previous_day": False,
        "poor_sleep": False,
        "all_out_race": False,
        "planned_action": RecommendationAction.MAINTAIN_NEXT_WORKOUT,
        "phase": "ten_k_polish",
        "week_number": 1,
        "planned_workout_id": "plan-1",
    }
    values[field] = value

    with pytest.raises(ValidationError):
        RecommendationInput(**values)
