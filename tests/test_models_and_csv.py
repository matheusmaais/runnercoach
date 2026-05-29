import pytest
from pydantic import ValidationError

from running_coach.csv_utils import decode_json_cell, encode_json_cell
from running_coach.models import (
    Confidence,
    RecommendationAction,
    SymptomSeverity,
    WorkoutRecord,
)


def valid_workout_kwargs(**overrides):
    values = {
        "local_date": "2026-05-28",
        "timezone": "America/Sao_Paulo",
        "workout_id": "workout-1",
        "activity_id": "activity-1",
        "planned_workout_id": "plan-1",
        "participants": ["matheus", "bruna"],
        "shared_run": True,
        "bruna_present": True,
        "matheus_role": "pacer",
        "confidence": Confidence.HIGH,
        "evidence_level": Confidence.HIGH,
        "recommendation_action": RecommendationAction.MAINTAIN_NEXT_WORKOUT,
    }
    values.update(overrides)
    return values


def test_json_cell_round_trip_preserves_order():
    values = ["matheus", "bruna", "science-ref"]
    encoded = encode_json_cell(values)
    assert encoded == '["matheus","bruna","science-ref"]'
    assert decode_json_cell(encoded) == values


def test_invalid_enum_value_is_rejected():
    with pytest.raises(ValidationError):
        WorkoutRecord(**valid_workout_kwargs(confidence="certain"))


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
        WorkoutRecord(**valid_workout_kwargs(participants=["matheus", "ana"]))


def test_non_canonical_timezone_is_rejected():
    with pytest.raises(ValidationError):
        WorkoutRecord(**valid_workout_kwargs(timezone="UTC"))


def test_shared_run_requires_both_participants_and_bruna_present():
    with pytest.raises(ValidationError):
        WorkoutRecord(
            **valid_workout_kwargs(
                participants=["matheus"],
                shared_run=True,
                bruna_present=False,
            )
        )


def test_pacer_role_requires_shared_run_with_bruna_present():
    with pytest.raises(ValidationError):
        WorkoutRecord(
            **valid_workout_kwargs(
                participants=["matheus", "bruna"],
                shared_run=False,
                bruna_present=True,
                matheus_role="pacer",
                confidence="high",
                evidence_level="high",
                recommendation_action="maintain_next_workout",
            )
        )


def test_matheus_not_present_role_rejects_matheus_participant():
    with pytest.raises(ValidationError):
        WorkoutRecord(**valid_workout_kwargs(matheus_role="not_present"))


def test_duplicate_participants_are_rejected():
    with pytest.raises(ValidationError):
        WorkoutRecord(
            **valid_workout_kwargs(
                participants=["matheus", "matheus"],
                shared_run=False,
                bruna_present=False,
                matheus_role="solo",
            )
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("shared_run", "false"),
        ("bruna_present", "true"),
    ],
)
def test_string_booleans_are_rejected(field, value):
    with pytest.raises(ValidationError):
        WorkoutRecord(**valid_workout_kwargs(**{field: value}))
