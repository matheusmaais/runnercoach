import pytest
from pydantic import ValidationError

from running_coach.csv_utils import decode_json_cell, encode_json_cell
from running_coach.models import (
    Confidence,
    RecommendationAction,
    SymptomSeverity,
    WorkoutRecord,
)


def test_json_cell_round_trip_preserves_order():
    values = ["matheus", "bruna", "science-ref"]
    encoded = encode_json_cell(values)
    assert encoded == '["matheus","bruna","science-ref"]'
    assert decode_json_cell(encoded) == values


def test_invalid_enum_value_is_rejected():
    with pytest.raises(ValidationError):
        WorkoutRecord(
            local_date="2026-05-28",
            timezone="America/Sao_Paulo",
            workout_id="workout-1",
            activity_id="activity-1",
            planned_workout_id="plan-1",
            participants=["matheus", "bruna"],
            shared_run=True,
            bruna_present=True,
            matheus_role="pacer",
            confidence="certain",
            evidence_level="high",
            recommendation_action="maintain_next_workout",
        )


def test_valid_minimal_workout_record():
    record = WorkoutRecord(
        local_date="2026-05-28",
        timezone="America/Sao_Paulo",
        workout_id="workout-1",
        activity_id="activity-1",
        planned_workout_id="plan-1",
        participants=["matheus", "bruna"],
        shared_run=True,
        bruna_present=True,
        matheus_role="pacer",
        confidence=Confidence.HIGH,
        evidence_level=Confidence.HIGH,
        recommendation_action=RecommendationAction.MAINTAIN_NEXT_WORKOUT,
        bruna_symptoms=[],
        symptom_severity=SymptomSeverity.NONE,
    )
    assert record.timezone == "America/Sao_Paulo"
    assert record.participants == ["matheus", "bruna"]


def test_unknown_participant_is_rejected():
    with pytest.raises(ValidationError):
        WorkoutRecord(
            local_date="2026-05-28",
            timezone="America/Sao_Paulo",
            workout_id="workout-1",
            activity_id="activity-1",
            planned_workout_id="plan-1",
            participants=["matheus", "ana"],
            shared_run=True,
            bruna_present=True,
            matheus_role="pacer",
            confidence=Confidence.HIGH,
            evidence_level=Confidence.HIGH,
            recommendation_action=RecommendationAction.MAINTAIN_NEXT_WORKOUT,
        )


def test_non_canonical_timezone_is_rejected():
    with pytest.raises(ValidationError):
        WorkoutRecord(
            local_date="2026-05-28",
            timezone="UTC",
            workout_id="workout-1",
            activity_id="activity-1",
            planned_workout_id="plan-1",
            participants=["matheus", "bruna"],
            shared_run=True,
            bruna_present=True,
            matheus_role="pacer",
            confidence=Confidence.HIGH,
            evidence_level=Confidence.HIGH,
            recommendation_action=RecommendationAction.MAINTAIN_NEXT_WORKOUT,
        )
