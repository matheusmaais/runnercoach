from __future__ import annotations

import base64
import json
from pathlib import Path

import yaml

from running_coach.operational import FrontendIntake, process_frontend_intake
from scripts.call_bedrock_recommendation import (
    _extract_bedrock_text,
    _repair_bedrock_response,
    _strip_json_fences,
)
from scripts.call_openai_recommendation import _extract_response_text, _response_json_schema


def _intake_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "created_at": "2026-05-29T12:00:00Z",
        "source": "github_pages",
        "checkin": {
            "schema_version": 1,
            "date": "2026-05-29",
            "confidence": "medium",
            "activity_match": {
                "activity_id": "garmin-test-20260529",
                "garmin_title": "Treino teste",
                "garmin_datetime": "2026-05-29 18:00:00",
            },
            "session": {
                "planned_type": "easy_run",
                "actual_type": "easy_run",
                "shared_run": True,
            },
            "bruna": {
                "avg_hr": 168,
                "max_hr": 184,
                "pse": 6,
                "symptoms": ["sem sintomas"],
                "sleep_quality": "boa",
                "volleyball_previous_day": False,
                "gym_previous_day": False,
                "lower_body_load_previous_day": "none",
                "subjective": "Controlado.",
                "could_repeat_last_block": True,
            },
            "matheus": {
                "achilles_morning": 0,
                "achilles_after": 0,
                "role": "pacer",
                "subjective": "Aquiles silencioso.",
            },
            "attachments": {
                "bruna_hr_screenshot": None,
                "bruna_hr_screenshot_sha256": None,
                "bruna_hr_extraction": {
                    "extracted_avg_hr": None,
                    "extracted_max_hr": None,
                    "extraction_method": "not_applicable",
                    "extraction_confidence": None,
                },
            },
            "coach_notes": {
                "decision_after_workout": "Manter progressão conservadora.",
            },
        },
        "garmin_csv": {
            "filename": "Activities.csv",
            "content_base64": base64.b64encode(b"Activity Type,Date\nRunning,2026-05-29\n").decode(),
        },
        "workflow": {
            "run_llm": True,
            "commit_results": True,
        },
    }


def test_frontend_intake_validates_payload() -> None:
    intake = FrontendIntake.model_validate(_intake_payload())

    assert intake.source == "github_pages"
    assert intake.checkin.bruna.pse == 6
    assert intake.workflow.run_llm is True


def test_process_frontend_intake_writes_checkin_and_garmin_csv(tmp_path: Path) -> None:
    intake_path = tmp_path / "data/manual/frontend_intake/2026-05-29T120000Z.json"
    intake_path.parent.mkdir(parents=True)
    intake_path.write_text(json.dumps(_intake_payload()), encoding="utf-8")

    result = process_frontend_intake(tmp_path, intake_path)

    assert result.checkin_path is not None
    assert result.garmin_csv_path is not None
    assert result.checkin_path.name == "2026-05-29-treino-teste.yaml"
    checkin = yaml.safe_load(result.checkin_path.read_text(encoding="utf-8"))
    assert checkin["schema_version"] == 1
    assert checkin["bruna"]["avg_hr"] == 168
    assert checkin["matheus"]["role"] == "pacer"
    assert result.garmin_csv_path.read_text(encoding="utf-8").startswith("Activity Type,Date")


def test_process_frontend_intake_updates_existing_checkin_for_same_activity(tmp_path: Path) -> None:
    existing = tmp_path / "data/manual/checkins/2026-05-29-existing.yaml"
    existing.parent.mkdir(parents=True)
    existing.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "date": "2026-05-29",
                "confidence": "low",
                "activity_match": {"activity_id": "garmin-test-20260529"},
                "session": {"shared_run": True},
                "bruna": {},
                "matheus": {"achilles_morning": 0, "achilles_after": 0, "role": "pacer"},
            }
        ),
        encoding="utf-8",
    )
    intake_path = tmp_path / "data/manual/frontend_intake/2026-05-29T120000Z.json"
    intake_path.parent.mkdir(parents=True)
    intake_path.write_text(json.dumps(_intake_payload()), encoding="utf-8")

    result = process_frontend_intake(tmp_path, intake_path)

    assert result.checkin_path == existing
    assert not (tmp_path / "data/manual/checkins/2026-05-29-treino-teste.yaml").exists()


def test_extract_response_text_from_responses_payload() -> None:
    payload = {
        "output": [
            {
                "content": [
                    {
                        "type": "output_text",
                        "text": '{"recommendation_id":"rec-1"}',
                    }
                ]
            }
        ]
    }

    assert _extract_response_text(payload) == '{"recommendation_id":"rec-1"}'


def test_openai_structured_output_schema_is_strict() -> None:
    schema = _response_json_schema()

    assert schema["additionalProperties"] is False
    assert schema["properties"]["schema_version"]["const"] == 1
    assert set(schema["required"]) == set(schema["properties"])


def test_extract_bedrock_text_and_strip_json_fences() -> None:
    payload = {
        "output": {
            "message": {
                "content": [
                    {
                        "text": '```json\n{"recommendation_id":"rec-bedrock"}\n```',
                    }
                ]
            }
        }
    }

    assert _strip_json_fences(_extract_bedrock_text(payload)) == '{"recommendation_id":"rec-bedrock"}'


def test_repair_bedrock_response_normalizes_common_shape_errors() -> None:
    repaired = _repair_bedrock_response(
        {
            "decision_type": "pre_workout_recommendation",
            "evidence_used": "workout-1, plan-1",
            "missing_evidence": "bruna_avg_hr, bruna_max_hr",
            "science_refs": ["seiler"],
        }
    )

    assert repaired["decision_type"] == "race_strategy"
    assert repaired["evidence_used"] == ["workout-1", "plan-1"]
    assert repaired["missing_evidence"] == ["bruna_avg_hr", "bruna_max_hr"]


def test_repair_bedrock_response_normalizes_pre_race_alias() -> None:
    repaired = _repair_bedrock_response(
        {
            "decision_type": "pre_race_taper_confirmation",
            "evidence_used": ["race_plan"],
            "missing_evidence": [],
            "science_refs": "world-athletics",
        }
    )

    assert repaired["decision_type"] == "race_strategy"
    assert repaired["science_refs"] == ["world-athletics"]
