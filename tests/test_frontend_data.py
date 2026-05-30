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
        "recommendation_history",
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
    assert recommendation["generated_at"]
    assert recommendation["source_path"] == "reports/llm/latest-recommendation.json"
    assert recommendation["timestamp_source"] in {
        "payload_generated_at",
        "source_modified_at",
    }
    assert "workout-garmin-20260528T161736-7p47km-3039s-17b463bc" in recommendation["evidence_used"]
    assert "bruna_avg_hr" in recommendation["missing_evidence"]
    assert "load-management-recovery" in recommendation["science_refs"]


def test_frontend_payload_exposes_recommendation_history_from_llm_artifacts() -> None:
    payload = build_frontend_payload(Path("."))

    history = payload["recommendation_history"]

    assert history
    assert history[0]["recommendation_id"]
    assert all(item["source_path"].startswith("reports/llm/") for item in history)
    assert payload["latest_llm_recommendation"] in history


def test_frontend_payload_exposes_readable_risk_drivers() -> None:
    payload = build_frontend_payload(Path("."))

    current_state = payload["current_state"]
    risk_summary = current_state["risk_summary"]

    assert risk_summary["level"] == current_state["risk_level"]
    assert risk_summary["drivers"] == current_state["risk_drivers"]
    assert risk_summary["drivers"]
    assert any(
        driver["code"] == "volleyball_previous_day"
        and "vôlei" in driver["label"].lower()
        for driver in risk_summary["drivers"]
    )


def test_write_frontend_payload_creates_json(tmp_path: Path) -> None:
    output = tmp_path / "app-data.json"

    written = write_frontend_payload(Path("."), output)

    assert written == output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["mission"]["target_race_window"] == "late January 2027"


def test_today_block_is_present_and_ptbr(tmp_path):
    from running_coach.frontend_data import build_frontend_payload
    from pathlib import Path
    payload = build_frontend_payload(Path("."))
    today = payload["today"]
    assert set(today) >= {"headline", "why", "next_planned", "confidence", "science_refs", "date"}
    assert today["headline"]  # non-empty PT-BR headline
    assert "evidence" not in today["why"].lower()  # no leaked EN engine string


def test_week_view_seven_days_ptbr_and_empty_state():
    from datetime import date
    from running_coach.frontend_data import _week_view
    rows = [
        {"date": "2026-05-31", "intended_category": "diagnostic_race_10k", "planned_status": "planned"},
    ]
    wk = _week_view(rows, date(2026, 5, 28))
    assert wk["generated"] is True
    assert [d["day"] for d in wk["days"]] == ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]
    assert any(d["label"] == "Prova diagnostica 10K" and d["kind"] == "quality" for d in wk["days"])
    assert any(d["label"] == "Volei" for d in wk["days"])  # Wed baseline
    # empty state when no future plan
    empty = _week_view([], date(2026, 5, 28))
    assert empty["generated"] is False
    assert "Operar" in empty["empty_message"]


def test_week_view_boundary_and_priority():
    from datetime import date
    from running_coach.frontend_data import _week_view
    # A plan row in NEXT week must not mark THIS week as generated.
    next_week = [{"date": "2026-06-08", "intended_category": "easy_run", "planned_status": "planned"}]
    wk = _week_view(next_week, date(2026, 6, 1))  # week of 2026-06-01..07
    assert wk["generated"] is False
    assert "não atualizada" in wk["empty_message"]
    # Duplicate rows same date: a run beats an 'off'.
    dup = [
        {"date": "2026-06-07", "intended_category": "off", "planned_status": "planned"},
        {"date": "2026-06-07", "intended_category": "easy_run", "planned_status": "planned"},
    ]
    wk2 = _week_view(dup, date(2026, 6, 1))
    sunday = next(d for d in wk2["days"] if d["day"] == "Dom")
    assert sunday["label"] == "Corrida leve"
