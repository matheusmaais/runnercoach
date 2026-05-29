from pathlib import Path
import csv

import pytest
import yaml
from pydantic import ValidationError

from running_coach.checkins import CheckIn, compute_sha256
from running_coach.plan import load_planned_workouts


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


def test_seed_checkin_references_existing_activity_id():
    checkin_path = Path("data/manual/checkins/2026-05-28-3x10-controlado.yaml")
    payload = yaml.safe_load(checkin_path.read_text(encoding="utf-8"))
    checkin = CheckIn.model_validate(payload)

    with Path("data/processed/activities.csv").open(encoding="utf-8", newline="") as handle:
        activity_ids = {row["activity_id"] for row in csv.DictReader(handle)}

    assert checkin.activity_match.activity_id in activity_ids
