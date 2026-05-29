from pathlib import Path
import csv

import pytest
import yaml
from pydantic import ValidationError

from running_coach.checkins import CheckIn, compute_sha256
from running_coach.plan import (
    PlanLoadError,
    load_planned_workouts,
    load_workout_template_keys,
)


def valid_checkin_payload(**overrides):
    payload = {
        "schema_version": 1,
        "date": "2026-05-28",
        "activity_match": {"activity_id": "activity-1"},
        "session": {"shared_run": True},
        "bruna": {"pse": 7, "symptoms": []},
        "matheus": {"achilles_morning": 0, "achilles_after": 0, "role": "pacer"},
    }
    payload.update(overrides)
    return payload


def test_checkin_rejects_invalid_pse():
    payload = valid_checkin_payload(bruna={"pse": 11, "symptoms": []})

    with pytest.raises(ValidationError):
        CheckIn.model_validate(payload)


def test_checkin_rejects_invalid_achilles():
    payload = valid_checkin_payload(
        matheus={"achilles_morning": 0, "achilles_after": 11, "role": "pacer"}
    )

    with pytest.raises(ValidationError):
        CheckIn.model_validate(payload)


def test_checkin_rejects_unknown_top_level_field():
    payload = valid_checkin_payload(unexpected="value")

    with pytest.raises(ValidationError):
        CheckIn.model_validate(payload)


def test_checkin_rejects_blank_activity_id():
    payload = valid_checkin_payload(activity_match={"activity_id": ""})

    with pytest.raises(ValidationError):
        CheckIn.model_validate(payload)


def test_checkin_rejects_invalid_date():
    payload = valid_checkin_payload(date="2026-02-31")

    with pytest.raises(ValidationError):
        CheckIn.model_validate(payload)


@pytest.mark.parametrize("hr_value", [-1, 241])
def test_checkin_rejects_negative_or_too_high_hr(hr_value: int):
    payload = valid_checkin_payload(bruna={"avg_hr": hr_value, "symptoms": []})

    with pytest.raises(ValidationError):
        CheckIn.model_validate(payload)


def test_checkin_rejects_invalid_screenshot_sha():
    payload = valid_checkin_payload(
        attachments={
            "bruna_hr_screenshot": "data/manual/screenshots/bruna.jpg",
            "bruna_hr_screenshot_sha256": "ABC123",
        }
    )

    with pytest.raises(ValidationError):
        CheckIn.model_validate(payload)


def test_checkin_rejects_extraction_without_confidence():
    payload = valid_checkin_payload(
        attachments={
            "bruna_hr_extraction": {
                "extracted_avg_hr": 168,
                "extraction_method": "manual_read",
            }
        }
    )

    with pytest.raises(ValidationError):
        CheckIn.model_validate(payload)


def test_compute_sha256(tmp_path: Path):
    image = tmp_path / "screenshot.jpg"
    image.write_bytes(b"heart-rate")

    assert (
        compute_sha256(image)
        == "2620d9183f1b08318e0b0f547a5c8c6ead7f48af359eb2553fc03d6bd62a9878"
    )


def test_load_planned_workouts_has_week_numbers(tmp_path: Path):
    csv_path = tmp_path / "planned.csv"
    csv_path.write_text(
        "planned_workout_id,week_number,date,phase,slot,intended_category,purpose,"
        "primary_athlete,planned_distance_or_duration,planned_intensity_range,"
        "allowed_fallbacks,contraindications,status\n"
        "plan-1,1,2026-05-31,ten_k_polish,sunday,race,10K diagnostic,"
        "bruna,10 km,6:15-6:20/km,"
        '"[""replace_with_easy""]","[""red_flag""]",planned\n',
        encoding="utf-8",
    )

    rows = load_planned_workouts(csv_path)

    assert rows[0]["week_number"] == 1
    assert rows[0]["allowed_fallbacks"] == ["replace_with_easy"]
    assert rows[0]["contraindications"] == ["red_flag"]


def test_load_planned_workouts_rejects_non_string_json_list_element(tmp_path: Path):
    csv_path = tmp_path / "planned.csv"
    csv_path.write_text(
        "planned_workout_id,week_number,date,phase,slot,intended_category,purpose,"
        "primary_athlete,planned_distance_or_duration,planned_intensity_range,"
        "allowed_fallbacks,contraindications,status\n"
        "plan-1,1,2026-05-31,ten_k_polish,sunday,race,10K diagnostic,"
        'bruna,10 km,6:15-6:20/km,"[1]","[]",planned\n',
        encoding="utf-8",
    )

    with pytest.raises(PlanLoadError):
        load_planned_workouts(csv_path)


def test_load_planned_workouts_missing_week_number_header_raises_plan_load_error(
    tmp_path: Path,
):
    csv_path = tmp_path / "planned.csv"
    csv_path.write_text(
        "planned_workout_id,date,phase,status\n"
        "plan-1,2026-05-31,ten_k_polish,planned\n",
        encoding="utf-8",
    )

    with pytest.raises(PlanLoadError) as error:
        load_planned_workouts(csv_path)

    assert "week_number" in str(error.value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("phase", "unknown_phase"),
        ("status", "unknown_status"),
    ],
)
def test_load_planned_workouts_rejects_unknown_phase_or_status(
    tmp_path: Path, field: str, value: str
):
    row = {
        "planned_workout_id": "plan-1",
        "week_number": "1",
        "date": "2026-05-31",
        "phase": "ten_k_polish",
        "slot": "sunday",
        "intended_category": "diagnostic_race_10k",
        "purpose": "10K diagnostic",
        "primary_athlete": "bruna",
        "planned_distance_or_duration": "10 km",
        "planned_intensity_range": "6:15-6:20/km",
        "allowed_fallbacks": '["replace_with_easy"]',
        "contraindications": '["red_flag"]',
        "status": "planned",
    }
    row[field] = value
    csv_path = tmp_path / "planned.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)

    with pytest.raises(PlanLoadError):
        load_planned_workouts(csv_path)


def test_load_planned_workouts_rejects_unknown_intended_category(
    tmp_path: Path,
):
    csv_path = tmp_path / "planned.csv"
    csv_path.write_text(
        "planned_workout_id,week_number,date,phase,slot,intended_category,purpose,"
        "primary_athlete,planned_distance_or_duration,planned_intensity_range,"
        "allowed_fallbacks,contraindications,status\n"
        "plan-1,1,2026-05-31,ten_k_polish,sunday,missing_category,"
        "10K diagnostic,bruna,10 km,6:15-6:20/km,"
        '"[""replace_with_easy""]","[""red_flag""]",planned\n',
        encoding="utf-8",
    )

    with pytest.raises(PlanLoadError) as error:
        load_planned_workouts(csv_path, allowed_categories={"easy_run"})

    assert "unknown intended category" in str(error.value)


def test_seed_plan_categories_exist_in_workout_templates():
    template_keys = load_workout_template_keys(Path("data/plan/workout_templates.yaml"))
    planned_rows = load_planned_workouts(
        Path("data/plan/planned_workouts.csv"),
        allowed_categories=template_keys,
    )

    assert {row["intended_category"] for row in planned_rows} <= template_keys


def test_seed_checkin_references_existing_activity_id():
    checkin_path = Path("data/manual/checkins/2026-05-28-3x10-controlado.yaml")
    payload = yaml.safe_load(checkin_path.read_text(encoding="utf-8"))
    checkin = CheckIn.model_validate(payload)

    with Path("data/processed/activities.csv").open(encoding="utf-8", newline="") as handle:
        activity_ids = {row["activity_id"] for row in csv.DictReader(handle)}

    assert checkin.activity_match.activity_id in activity_ids
    assert checkin.confidence
    assert isinstance(checkin.missing_evidence, list)
