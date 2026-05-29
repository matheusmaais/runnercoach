import csv
import json
from pathlib import Path

import pytest

from running_coach.garmin import make_activity_id
from running_coach.models import Confidence, DecisionType, RecommendationAction
from running_coach.pipeline import CheckInLoadError, run_pipeline
from running_coach.recommendations import RecommendationResult


REQUIRED_WORKOUT_COLUMNS = {
    "date",
    "local_date",
    "local_datetime",
    "timezone",
    "workout_id",
    "activity_id",
    "planned_workout_id",
    "athlete_context",
    "participants",
    "shared_run",
    "bruna_present",
    "matheus_role",
    "activity_type",
    "category",
    "distance_km",
    "duration",
    "avg_pace",
    "best_pace",
    "matheus_avg_hr",
    "matheus_max_hr",
    "matheus_cadence",
    "matheus_power",
    "matheus_ground_contact",
    "matheus_stride_length",
    "bruna_avg_hr",
    "bruna_max_hr",
    "bruna_pse",
    "bruna_symptoms",
    "matheus_achilles_morning",
    "matheus_achilles_after",
    "sleep_quality",
    "volleyball_previous_day",
    "gym_previous_day",
    "notes",
    "decision_after_workout",
    "recommendation_action",
    "confidence",
    "missing_evidence",
    "evidence_level",
    "match_confidence",
}

REQUIRED_DECISION_COLUMNS = {
    "date",
    "local_date",
    "local_datetime",
    "timezone",
    "event",
    "decision",
    "reason",
    "impact",
    "related_workout_id",
    "evidence",
    "confidence",
    "science_refs",
    "decision_type",
    "blocked_by_red_flag",
    "missing_evidence",
}


def write_garmin_csv(path: Path) -> None:
    path.write_text(
        "Tipo de atividade,Data,Título,Distância,Tempo,FC Média,FC máxima\n"
        "Corrida,2026-05-28 16:17:36,Santo Angelo Corrida,7.47,00:50:39,147,164\n",
        encoding="utf-8",
    )


def write_matching_checkin(path: Path, activity_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"schema_version: 1\n"
        f"date: 2026-05-28\n"
        f"confidence: low\n"
        f"missing_evidence:\n"
        f"  - bruna_hr_screenshot\n"
        f"  - bruna_avg_hr\n"
        f"  - bruna_max_hr\n"
        f"activity_match:\n"
        f"  activity_id: {activity_id}\n"
        f"  garmin_title: Santo Angelo Corrida\n"
        f"  garmin_datetime: '2026-05-28 16:17:36'\n"
        f"session:\n"
        f"  planned_type: quality_controlled\n"
        f"  actual_type: cruise_intervals\n"
        f"  shared_run: true\n"
        f"bruna:\n"
        f"  avg_hr: null\n"
        f"  max_hr: null\n"
        f"  pse: 7\n"
        f"  symptoms: []\n"
        f"  sleep_quality: regular\n"
        f"  volleyball_previous_day: true\n"
        f"  gym_previous_day: false\n"
        f"  subjective: Cansada pelo volei, mas controlou bem.\n"
        f"matheus:\n"
        f"  achilles_morning: 0\n"
        f"  achilles_after: 0\n"
        f"  role: pacer\n"
        f"  subjective: Aquiles silencioso.\n"
        f"attachments:\n"
        f"  bruna_hr_screenshot: null\n"
        f"  bruna_hr_screenshot_sha256: null\n"
        f"  bruna_hr_extraction:\n"
        f"    extracted_avg_hr: null\n"
        f"    extracted_max_hr: null\n"
        f"    extraction_method: not_applicable\n"
        f"    extraction_confidence: null\n"
        f"coach_notes:\n"
        f"  decision_after_workout: Manter polimento conservador.\n",
        encoding="utf-8",
    )


def write_human_matched_checkin(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "schema_version: 1\n"
        "date: 2026-05-28\n"
        "confidence: medium\n"
        "missing_evidence: []\n"
        "activity_match:\n"
        "  garmin_title: Santo Angelo Corrida\n"
        "  garmin_datetime: '2026-05-28 16:17:36'\n"
        "  distance_km: 7.47\n"
        "session:\n"
        "  planned_type: quality_controlled\n"
        "  actual_type: cruise_intervals\n"
        "  shared_run: true\n"
        "bruna:\n"
        "  avg_hr: 168\n"
        "  max_hr: 184\n"
        "  pse: 7\n"
        "  symptoms: []\n"
        "  sleep_quality: regular\n"
        "  volleyball_previous_day: false\n"
        "  gym_previous_day: false\n"
        "  subjective: Controlado.\n"
        "matheus:\n"
        "  achilles_morning: 0\n"
        "  achilles_after: 0\n"
        "  role: pacer\n"
        "  subjective: Aquiles silencioso.\n",
        encoding="utf-8",
    )


def write_science_registry(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "refs:\n"
        "  - science_ref_id: source-1\n"
        "    title: Example source\n"
        "    authors:\n"
        "      - Researcher A\n"
        "    year: 2024\n"
        "    source_type: peer_reviewed_study\n"
        "    journal_or_publisher: Journal of Running Evidence\n"
        "    doi_or_url: https://doi.org/10.1234/example\n"
        "    population: Recreational runners\n"
        "    finding: Training decisions should match athlete state.\n"
        "    practical_application: Use evidence tags to gate recommendations.\n"
        "    limits: Example-only fixture.\n"
        "    tags:\n"
        "      - threshold\n"
        "    approved: true\n"
        "    approved_date: 2026-05-29\n"
        "    notes: Fixture for pipeline tests.\n",
        encoding="utf-8",
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_pipeline_writes_core_outputs(tmp_path):
    garmin_csv = tmp_path / "Activities.csv"
    repo_root = tmp_path / "repo"
    write_garmin_csv(garmin_csv)

    run_pipeline(garmin_csv=garmin_csv, repo_root=repo_root, after_workout=True)

    for output in [
        repo_root / "data/processed/activities.csv",
        repo_root / "data/processed/workouts.csv",
        repo_root / "data/processed/decisions.csv",
        repo_root / "data/processed/plan_status.csv",
        repo_root / "data/processed/science_refs.csv",
        repo_root / "docs/state.md",
        repo_root / "docs/decisions.md",
        repo_root / "reports/latest-summary.md",
    ]:
        assert output.exists(), f"missing output: {output}"


def test_pipeline_incremental_csv_preserves_existing_activity_history(tmp_path):
    repo_root = tmp_path / "repo"
    full_csv = tmp_path / "Activities-full.csv"
    full_csv.write_text(
        "Tipo de atividade,Data,Título,Distância,Tempo,FC Média,FC máxima\n"
        "Corrida,2026-05-28 16:17:36,Santo Angelo Corrida,7.47,00:50:39,147,164\n"
        "Corrida,2026-05-28 17:14:17,Matheus Solo,1.33,00:05:49,189,192\n",
        encoding="utf-8",
    )
    run_pipeline(garmin_csv=full_csv, repo_root=repo_root, after_workout=True)

    incremental_csv = tmp_path / "Activities-incremental.csv"
    activity_id = make_activity_id(
        "2026-05-28 16:17:36", 7.47, 3039.0, "Santo Angelo Corrida"
    )
    incremental_csv.write_text(
        "activity_id,Tipo de atividade,Data,Título,Distância,Tempo,Ritmo médio\n"
        f"{activity_id},Corrida,2026-05-28 16:17:36,Santo Angelo Corrida,7.47,00:50:39,6:47\n",
        encoding="utf-8",
    )
    run_pipeline(garmin_csv=incremental_csv, repo_root=repo_root, after_workout=True)

    activities = read_csv(repo_root / "data/processed/activities.csv")
    assert len(activities) == 2
    assert any(row["title"] == "Matheus Solo" for row in activities)


def test_pipeline_does_not_overwrite_science_registry(tmp_path):
    garmin_csv = tmp_path / "Activities.csv"
    repo_root = tmp_path / "repo"
    registry = repo_root / "data/knowledge/science_refs.yaml"
    sentinel = "refs: []\n# sentinel: do not overwrite\n"
    write_garmin_csv(garmin_csv)
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(sentinel, encoding="utf-8")

    run_pipeline(garmin_csv=garmin_csv, repo_root=repo_root, after_workout=True)

    assert registry.read_text(encoding="utf-8") == sentinel


def test_pipeline_marks_missing_checkin_evidence(tmp_path):
    garmin_csv = tmp_path / "Activities.csv"
    repo_root = tmp_path / "repo"
    write_garmin_csv(garmin_csv)

    run_pipeline(garmin_csv=garmin_csv, repo_root=repo_root, after_workout=True)

    workouts = read_csv(repo_root / "data/processed/workouts.csv")
    assert workouts[0]["confidence"] == "low"
    assert "checkin" in json.loads(workouts[0]["missing_evidence"])


def test_pipeline_matches_existing_checkin_by_activity_id(tmp_path):
    garmin_csv = tmp_path / "Activities.csv"
    repo_root = tmp_path / "repo"
    write_garmin_csv(garmin_csv)
    activity_id = make_activity_id(
        "2026-05-28 16:17:36", 7.47, 3039.0, "Santo Angelo Corrida"
    )
    write_matching_checkin(
        repo_root / "data/manual/checkins/2026-05-28-quality.yaml", activity_id
    )

    run_pipeline(garmin_csv=garmin_csv, repo_root=repo_root, after_workout=True)

    workouts = read_csv(repo_root / "data/processed/workouts.csv")
    missing_evidence = json.loads(workouts[0]["missing_evidence"])
    assert "checkin" not in missing_evidence
    assert {"bruna_avg_hr", "bruna_max_hr", "bruna_hr_screenshot"}.issubset(
        missing_evidence
    )
    assert json.loads(workouts[0]["participants"]) == ["matheus", "bruna"]
    assert workouts[0]["shared_run"] == "true"
    assert workouts[0]["bruna_present"] == "true"
    assert workouts[0]["matheus_role"] == "pacer"
    assert workouts[0]["bruna_pse"] == "7"
    assert workouts[0]["volleyball_previous_day"] == "true"
    assert workouts[0]["decision_after_workout"] == "Manter polimento conservador."


def test_pipeline_matches_checkin_by_human_activity_keys(tmp_path):
    garmin_csv = tmp_path / "Activities.csv"
    repo_root = tmp_path / "repo"
    write_garmin_csv(garmin_csv)
    write_human_matched_checkin(repo_root / "data/manual/checkins/2026-05-28-quality.yaml")

    run_pipeline(garmin_csv=garmin_csv, repo_root=repo_root, after_workout=True)

    workouts = read_csv(repo_root / "data/processed/workouts.csv")
    assert workouts[0]["athlete_context"] == "shared_run_with_manual_checkin"
    assert workouts[0]["shared_run"] == "true"
    assert workouts[0]["bruna_pse"] == "7"
    assert workouts[0]["match_confidence"] == "high"


def test_pipeline_marks_planned_workout_completed_with_evidence(tmp_path):
    garmin_csv = tmp_path / "Activities.csv"
    repo_root = tmp_path / "repo"
    write_garmin_csv(garmin_csv)
    write_human_matched_checkin(repo_root / "data/manual/checkins/2026-05-28-quality.yaml")
    (repo_root / "data/plan").mkdir(parents=True)
    (repo_root / "data/plan/planned_workouts.csv").write_text(
        "planned_workout_id,week_number,date,phase,intended_category,status\n"
        "plan-20260528-cruise,1,2026-05-28,ten_k_polish,cruise_intervals,planned\n",
        encoding="utf-8",
    )

    run_pipeline(garmin_csv=garmin_csv, repo_root=repo_root, after_workout=True)

    workouts = read_csv(repo_root / "data/processed/workouts.csv")
    plan_status = read_csv(repo_root / "data/processed/plan_status.csv")
    assert workouts[0]["planned_workout_id"] == "plan-20260528-cruise"
    assert plan_status[0]["derived_status"] == "completed_with_evidence"
    assert plan_status[0]["matched_workout_id"] == workouts[0]["workout_id"]


def test_pipeline_fails_closed_when_human_checkin_does_not_match_activity(tmp_path):
    garmin_csv = tmp_path / "Activities.csv"
    repo_root = tmp_path / "repo"
    write_garmin_csv(garmin_csv)
    write_human_matched_checkin(repo_root / "data/manual/checkins/2026-05-28-quality.yaml")
    checkin_path = repo_root / "data/manual/checkins/2026-05-28-quality.yaml"
    checkin_path.write_text(
        checkin_path.read_text(encoding="utf-8").replace(
            "2026-05-28 16:17:36", "2026-05-28 18:00:00"
        ),
        encoding="utf-8",
    )

    with pytest.raises(CheckInLoadError, match="No Garmin activity matched check-in"):
        run_pipeline(garmin_csv=garmin_csv, repo_root=repo_root, after_workout=True)


def test_pipeline_calls_and_applies_deterministic_recommendation(tmp_path, monkeypatch):
    garmin_csv = tmp_path / "Activities.csv"
    repo_root = tmp_path / "repo"
    write_garmin_csv(garmin_csv)
    activity_id = make_activity_id(
        "2026-05-28 16:17:36", 7.47, 3039.0, "Santo Angelo Corrida"
    )
    write_matching_checkin(
        repo_root / "data/manual/checkins/2026-05-28-quality.yaml", activity_id
    )
    calls = []

    def deterministic_recommendation(input_data):
        calls.append(input_data)
        return RecommendationResult(
            action=RecommendationAction.REPLACE_WITH_EASY,
            decision=DecisionType.RECOVER,
            selected_fallback=RecommendationAction.REPLACE_WITH_EASY,
            confidence=Confidence.HIGH,
            blocked_by_red_flag=False,
            reasons=["bruna_pse_ge_9"],
            science_refs=["load-management-recovery"],
            rule_refs=["load-management-recovery"],
            missing_evidence=[],
            assumptions=[],
            phase=input_data.phase,
            week_number=input_data.week_number,
            planned_workout_id=input_data.planned_workout_id,
        )

    monkeypatch.setattr(
        "running_coach.pipeline.recommend_next_action", deterministic_recommendation
    )

    run_pipeline(garmin_csv=garmin_csv, repo_root=repo_root, after_workout=True)

    workouts = read_csv(repo_root / "data/processed/workouts.csv")
    decisions = read_csv(repo_root / "data/processed/decisions.csv")
    assert len(calls) == 1
    assert calls[0].bruna_pse == 7
    assert workouts[0]["recommendation_action"] == "replace_with_easy"
    assert decisions[0]["recommendation_action"] == "replace_with_easy"
    assert decisions[0]["decision_type"] == "recover"
    assert json.loads(decisions[0]["science_refs"]) == ["load-management-recovery"]


def test_workouts_and_decisions_have_required_contract_columns(tmp_path):
    garmin_csv = tmp_path / "Activities.csv"
    repo_root = tmp_path / "repo"
    write_garmin_csv(garmin_csv)

    run_pipeline(garmin_csv=garmin_csv, repo_root=repo_root, after_workout=True)

    workouts = read_csv(repo_root / "data/processed/workouts.csv")
    decisions = read_csv(repo_root / "data/processed/decisions.csv")
    assert REQUIRED_WORKOUT_COLUMNS.issubset(workouts[0].keys())
    assert REQUIRED_DECISION_COLUMNS.issubset(decisions[0].keys())
    assert decisions[0]["timezone"] == "America/Sao_Paulo"
    assert decisions[0]["local_datetime"] == "2026-05-28 16:17:36"


def test_pipeline_fails_closed_on_duplicate_checkin_activity_ids(tmp_path):
    garmin_csv = tmp_path / "Activities.csv"
    repo_root = tmp_path / "repo"
    write_garmin_csv(garmin_csv)
    activity_id = make_activity_id(
        "2026-05-28 16:17:36", 7.47, 3039.0, "Santo Angelo Corrida"
    )
    write_matching_checkin(
        repo_root / "data/manual/checkins/2026-05-28-a.yaml", activity_id
    )
    write_matching_checkin(
        repo_root / "data/manual/checkins/2026-05-28-b.yaml", activity_id
    )

    try:
        run_pipeline(garmin_csv=garmin_csv, repo_root=repo_root, after_workout=True)
    except CheckInLoadError as exc:
        message = str(exc)
    else:
        raise AssertionError("duplicate check-ins should fail closed")

    assert "Duplicate check-ins reference activity_id" in message
    assert "2026-05-28-a.yaml" in message
    assert "2026-05-28-b.yaml" in message


def test_pipeline_checkin_validation_errors_include_file_path(tmp_path):
    garmin_csv = tmp_path / "Activities.csv"
    repo_root = tmp_path / "repo"
    checkin_path = repo_root / "data/manual/checkins/bad.yaml"
    write_garmin_csv(garmin_csv)
    checkin_path.parent.mkdir(parents=True, exist_ok=True)
    checkin_path.write_text("schema_version: 1\n", encoding="utf-8")

    with pytest.raises(CheckInLoadError, match="bad.yaml"):
        run_pipeline(garmin_csv=garmin_csv, repo_root=repo_root, after_workout=True)


def test_pipeline_derived_science_refs_from_registry(tmp_path):
    garmin_csv = tmp_path / "Activities.csv"
    repo_root = tmp_path / "repo"
    write_garmin_csv(garmin_csv)
    write_science_registry(repo_root / "data/knowledge/science_refs.yaml")

    run_pipeline(garmin_csv=garmin_csv, repo_root=repo_root, after_workout=True)

    science_refs = read_csv(repo_root / "data/processed/science_refs.csv")
    assert science_refs[0]["science_ref_id"] == "source-1"
    assert science_refs[0]["approved"] == "true"
    assert json.loads(science_refs[0]["tags"]) == ["threshold"]


def test_pipeline_writes_rich_state_decisions_plan_status_and_monthly_report(tmp_path):
    garmin_csv = tmp_path / "Activities.csv"
    repo_root = tmp_path / "repo"
    write_garmin_csv(garmin_csv)
    (repo_root / "data/plan").mkdir(parents=True)
    (repo_root / "data/plan/cycle.yaml").write_text(
        "current_phase: ten_k_polish\ncurrent_week_number: 1\n",
        encoding="utf-8",
    )
    (repo_root / "data/plan/planned_workouts.csv").write_text(
        "planned_workout_id,week_number,date,phase,intended_category,status\n"
        "plan-1,1,2026-05-31,ten_k_polish,diagnostic_race_10k,planned\n",
        encoding="utf-8",
    )

    run_pipeline(
        garmin_csv=garmin_csv,
        repo_root=repo_root,
        after_workout=True,
        monthly_report=True,
    )

    state = (repo_root / "docs/state.md").read_text(encoding="utf-8")
    decisions = (repo_root / "docs/decisions.md").read_text(encoding="utf-8")
    plan_status = read_csv(repo_root / "data/processed/plan_status.csv")
    monthly = (repo_root / "reports/monthly/latest.md").read_text(encoding="utf-8")

    for heading in [
        "## Last Update",
        "## Current Phase",
        "## Current Paces",
        "## Current Risks",
        "## Next Milestones",
        "## Active Decisions",
    ]:
        assert heading in state
    assert "ten_k_polish" in state
    assert "## Decision Log" in decisions
    assert "workout-garmin-" in decisions
    assert plan_status[0]["planned_workout_id"] == "plan-1"
    assert plan_status[0]["derived_status"] == "planned"
    assert "## Period" in monthly
    assert "## Next 30 Days" in monthly
