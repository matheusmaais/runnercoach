import csv
import json
from pathlib import Path

from running_coach.pipeline import run_pipeline


def write_garmin_csv(path: Path) -> None:
    path.write_text(
        "Tipo de atividade,Data,Título,Distância,Tempo,FC Média,FC máxima\n"
        "Corrida,2026-05-28 16:17:36,Santo Angelo Corrida,7.47,00:50:39,147,164\n",
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
        repo_root / "data/processed/science_refs.csv",
        repo_root / "docs/state.md",
        repo_root / "docs/decisions.md",
        repo_root / "reports/latest-summary.md",
    ]:
        assert output.exists(), f"missing output: {output}"


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


def test_pipeline_derived_science_refs_from_registry(tmp_path):
    garmin_csv = tmp_path / "Activities.csv"
    repo_root = tmp_path / "repo"
    write_garmin_csv(garmin_csv)
    write_science_registry(repo_root / "data/knowledge/science_refs.yaml")

    run_pipeline(garmin_csv=garmin_csv, repo_root=repo_root, after_workout=True)

    science_refs = read_csv(repo_root / "data/processed/science_refs.csv")
    assert science_refs[0]["science_ref_id"] == "source-1"
    assert science_refs[0]["approved"] == "True"
    assert json.loads(science_refs[0]["tags"]) == ["threshold"]
