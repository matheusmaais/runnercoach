from __future__ import annotations

import json
from pathlib import Path

from running_coach.frontend_data import build_frontend_payload, write_frontend_payload


def test_frontend_payload_has_required_sections() -> None:
    payload = build_frontend_payload(Path("."))

    assert {
        "generated_at",
        "mission",
        "athletes",
        "current_state",
        "next_workouts",
        "recent_workouts",
        "weekly_summary",
        "trends",
        "decisions",
        "science_refs",
        "llm_context",
        "latest_llm_recommendation",
        "evidence_contracts",
        "presentation_warnings",
    }.issubset(payload)

    assert payload["mission"]["name"] == "Meia Forte Janeiro 2027"
    assert payload["athletes"]["bruna"]["data_sources"]["pace"] == "shared_run"
    assert payload["athletes"]["matheus"]["strategic_limit"] == "left_achilles"


def test_frontend_payload_keeps_matheus_solo_separate_from_bruna_evidence() -> None:
    payload = build_frontend_payload(Path("."))

    latest_shared = payload["current_state"]["latest_shared_workout"]
    latest_solo = payload["current_state"]["latest_matheus_solo"]
    bruna_state = payload["athletes"]["bruna"]["current_training_state"]

    assert latest_shared["workout_id"] != latest_solo["workout_id"]
    assert latest_shared["bruna_evidence"] == "available"
    assert latest_solo["bruna_evidence"] == "not_applicable"
    assert latest_solo["avg_pace"] == "4:22"
    assert bruna_state["short_max_current"] == "~5:50/km"
    assert bruna_state["short_max_current"] != latest_solo["avg_pace"]

    warnings = " ".join(payload["presentation_warnings"])
    assert "Pace solo do Matheus não pode ser renderizado como evolução da Bruna" in warnings


def test_frontend_payload_marks_missing_bruna_manual_biometrics() -> None:
    payload = build_frontend_payload(Path("."))

    latest_shared = payload["current_state"]["latest_shared_workout"]

    assert latest_shared["shared_run"] is True
    assert latest_shared["bruna_present"] is True
    assert "bruna_avg_hr" in latest_shared["missing_evidence"]
    assert "bruna_max_hr" in latest_shared["missing_evidence"]
    assert latest_shared["evidence_confidence"] in {"medium", "high"}


def test_frontend_payload_includes_science_and_next_workouts() -> None:
    payload = build_frontend_payload(Path("."))

    assert len(payload["science_refs"]) >= 8
    assert all(ref["doi_or_url"].startswith("http") for ref in payload["science_refs"])
    assert len(payload["next_workouts"]) >= 2
    assert payload["next_workouts"][0]["date"] == "2026-05-31"
    assert payload["next_workouts"][0]["decision_basis"]


def test_frontend_payload_exposes_latest_llm_recommendation() -> None:
    payload = build_frontend_payload(Path("."))

    recommendation = payload["latest_llm_recommendation"]

    assert recommendation["recommendation_id"]
    assert recommendation["decision_type"] == "race_strategy"
    assert recommendation["next_workout_action"] == "reduce_next_workout"
    assert recommendation["summary"]
    assert recommendation["science_refs"]


def test_write_frontend_payload_creates_json(tmp_path: Path) -> None:
    output = tmp_path / "app-data.json"

    written = write_frontend_payload(Path("."), output)

    assert written == output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["mission"]["target_race_window"] == "late January 2027"
