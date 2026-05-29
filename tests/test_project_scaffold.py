from pathlib import Path


def test_required_directories_exist():
    required = [
        "data/raw/garmin",
        "data/manual/checkins",
        "data/manual/screenshots",
        "data/plan",
        "data/knowledge",
        "data/processed",
        "docs",
        "reports/monthly",
        "scripts",
        "src/running_coach",
    ]
    for item in required:
        assert Path(item).is_dir(), item


def test_raw_garmin_csvs_are_ignored_but_gitkeep_is_allowed():
    gitignore = Path(".gitignore").read_text()
    assert "data/raw/garmin/*" in gitignore
    assert "!data/raw/garmin/.gitkeep" in gitignore
    assert "data/manual/screenshots/*" not in gitignore
