from datetime import datetime
from pathlib import Path

from running_coach.operational import process_frontend_intake, write_frontend_intake


def _race_payload(date, dist, secs, **extra):
    return {
        "schema_version": 1,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "source": "github_pages",
        "race": {"date": date, "distance_km": dist, "time_seconds": secs, **extra},
        "workflow": {"run_llm": False, "commit_results": True},
    }


def test_race_only_intake_writes_races_yaml(tmp_path):
    (tmp_path / "data/plan").mkdir(parents=True)
    p = write_frontend_intake(tmp_path, _race_payload("2026-06-14", 10.0, 3600, max_hr=190, notes="10k"))
    res = process_frontend_intake(tmp_path, p)
    assert res.race_path and res.race_path.name == "races.yaml"
    assert res.checkin_path is None and res.garmin_csv_path is None and res.run_llm is False
    import yaml
    data = yaml.safe_load((tmp_path / "data/plan/races.yaml").read_text())
    assert len(data["races"]) == 1
    r = data["races"][0]
    assert r["race_id"] == "10k-2026-06-14" and r["status"] == "done" and r["max_hr"] == 190


def test_race_dedup_same_id_replaces(tmp_path):
    (tmp_path / "data/plan").mkdir(parents=True)
    p1 = write_frontend_intake(tmp_path, _race_payload("2026-06-14", 10.0, 3600))
    process_frontend_intake(tmp_path, p1)
    p2 = write_frontend_intake(tmp_path, _race_payload("2026-06-14", 10.0, 3500))  # faster, same day+dist
    process_frontend_intake(tmp_path, p2)
    import yaml
    races = yaml.safe_load((tmp_path / "data/plan/races.yaml").read_text())["races"]
    assert len(races) == 1 and races[0]["time_seconds"] == 3500


def test_race_append_distinct_ids(tmp_path):
    (tmp_path / "data/plan").mkdir(parents=True)
    for d, dist, secs in [("2026-06-14", 10.0, 3600), ("2026-07-01", 5.0, 1750)]:
        process_frontend_intake(tmp_path, write_frontend_intake(tmp_path, _race_payload(d, dist, secs)))
    import yaml
    races = yaml.safe_load((tmp_path / "data/plan/races.yaml").read_text())["races"]
    assert len(races) == 2


def test_race_recalibrates_zones(tmp_path):
    (tmp_path / "data/plan").mkdir(parents=True)
    process_frontend_intake(tmp_path, write_frontend_intake(tmp_path, _race_payload("2026-06-14", 5.0, 1750)))
    from running_coach.frontend_data import _load_benchmark_zones
    # use a recent date so the 120d window includes it
    import yaml
    racefile = tmp_path / "data/plan/races.yaml"
    d = yaml.safe_load(racefile.read_text())
    from datetime import date
    d["races"][0]["date"] = date.today().isoformat()
    racefile.write_text(yaml.safe_dump(d))
    z = _load_benchmark_zones(tmp_path)
    assert z.get("intervals_5_10k") == "5:50/km"
