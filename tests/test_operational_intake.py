from __future__ import annotations

import json
import csv
from pathlib import Path

import yaml

from running_coach.operational import FrontendIntake, process_frontend_intake
from running_coach.pipeline import run_pipeline
from scripts.call_bedrock_recommendation import (
    _extract_bedrock_text,
    _persist_bedrock_response,
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
        "garmin_activity": {
            "source_filename": "Activities.csv",
            "activity_id": "garmin-test-20260529",
            "local_date": "2026-05-29",
            "local_datetime": "2026-05-29 18:00:00",
            "timezone": "America/Sao_Paulo",
            "activity_type": "Running",
            "title": "Treino teste",
            "distance_km": 7.0,
            "duration_seconds": 2700,
            "avg_pace": "6:26",
        },
        "workflow": {
            "run_llm": True,
            "commit_results": True,
        },
    }


def _human_matched_intake_payload() -> dict[str, object]:
    payload = _intake_payload()
    checkin = dict(payload["checkin"])
    checkin["date"] = "2026-05-28"
    checkin["activity_match"] = {
        "garmin_title": "Santo Angelo Corrida",
        "garmin_datetime": "2026-05-28 16:17:36",
        "distance_km": 7.47,
    }
    checkin["session"] = {
        "planned_type": "quality_controlled",
        "actual_type": "cruise_intervals",
        "shared_run": True,
    }
    payload["checkin"] = checkin
    payload["garmin_activity"] = {
        "source_filename": "Activities.csv",
        "local_date": "2026-05-28",
        "local_datetime": "2026-05-28 16:17:36",
        "timezone": "America/Sao_Paulo",
        "activity_type": "Corrida",
        "title": "Santo Angelo Corrida",
        "distance_km": 7.47,
        "duration_seconds": 3039,
        "avg_pace": "6:46",
    }
    return payload


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_intake_without_activity_id_matches_uploaded_activity_end_to_end(tmp_path: Path) -> None:
    intake_path = tmp_path / "data/manual/frontend_intake/2026-05-29T120000Z.json"
    intake_path.parent.mkdir(parents=True)
    intake_path.write_text(json.dumps(_human_matched_intake_payload()), encoding="utf-8")

    result = process_frontend_intake(tmp_path, intake_path)
    assert result.checkin_path is not None
    assert result.garmin_csv_path is not None
    assert result.garmin_csv_path.exists()
    assert result.garmin_csv_path.is_relative_to(tmp_path / ".runnercoach" / "tmp")

    sanitized = result.garmin_csv_path.read_text(encoding="utf-8")
    assert "FC Média" not in sanitized
    assert "FC máxima" not in sanitized
    assert "activity_id" in sanitized
    run_pipeline(result.garmin_csv_path, tmp_path, after_workout=True)

    workouts = _read_csv(tmp_path / "data/processed/workouts.csv")
    assert workouts[0]["athlete_context"] == "shared_run_with_manual_checkin"
    assert workouts[0]["shared_run"] == "true"
    assert workouts[0]["activity_id"].startswith("garmin-20260528T161736")


def test_frontend_intake_validates_payload() -> None:
    intake = FrontendIntake.model_validate(_intake_payload())

    assert intake.source == "github_pages"
    assert intake.checkin.bruna.pse == 6
    assert intake.garmin_activity is not None
    assert intake.garmin_activity.activity_id == "garmin-test-20260529"
    assert intake.workflow.run_llm is True


def test_process_frontend_intake_writes_checkin_without_raw_garmin_csv(tmp_path: Path) -> None:
    intake_path = tmp_path / "data/manual/frontend_intake/2026-05-29T120000Z.json"
    intake_path.parent.mkdir(parents=True)
    intake_path.write_text(json.dumps(_intake_payload()), encoding="utf-8")

    result = process_frontend_intake(tmp_path, intake_path)

    assert result.checkin_path is not None
    assert result.garmin_csv_path is not None
    assert result.garmin_csv_path.exists()
    assert result.checkin_path.name == "2026-05-29-treino-teste.yaml"
    checkin = yaml.safe_load(result.checkin_path.read_text(encoding="utf-8"))
    assert checkin["schema_version"] == 1
    assert checkin["bruna"]["avg_hr"] == 168
    assert checkin["matheus"]["role"] == "pacer"
    assert not (tmp_path / "data/raw/garmin").exists()
    sanitized = result.garmin_csv_path.read_text(encoding="utf-8")
    assert "content_base64" not in sanitized
    assert "FC Média" not in sanitized
    assert "Potência média" not in sanitized


def test_tracked_frontend_intakes_do_not_contain_garmin_base64() -> None:
    intake_dir = Path("data/manual/frontend_intake")
    for path in sorted(intake_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert "content_base64" not in json.dumps(payload), path
        garmin_csv = payload.get("garmin_csv")
        assert not isinstance(garmin_csv, dict), path


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


def test_persist_bedrock_response_preserves_raw_before_repair(tmp_path: Path) -> None:
    raw_response = {
        "decision_type": "pre_workout_recommendation",
        "evidence_used": "workout-1, plan-1",
        "missing_evidence": "bruna_avg_hr",
        "science_refs": "load-management-recovery",
    }

    paths = _persist_bedrock_response(tmp_path, raw_response)

    raw = json.loads(paths["raw"].read_text(encoding="utf-8"))
    repaired = json.loads(paths["repaired"].read_text(encoding="utf-8"))
    assert raw == raw_response
    assert raw["evidence_used"] == "workout-1, plan-1"
    assert repaired["evidence_used"] == ["workout-1", "plan-1"]
    assert paths["raw"].name == "latest-bedrock-response.json"
    assert paths["repaired"].name == "latest-bedrock-repaired-response.json"
