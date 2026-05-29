import subprocess
from pathlib import Path


def is_ignored(path):
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", "--no-index", path],
        check=False,
    )
    assert result.returncode in (0, 1), path
    return result.returncode == 0


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


def test_empty_scaffold_directories_have_tracked_markers():
    required_markers = [
        "data/raw/garmin/.gitkeep",
        "data/manual/checkins/.gitkeep",
        "data/manual/screenshots/.gitkeep",
        "data/plan/.gitkeep",
        "data/knowledge/.gitkeep",
        "data/processed/.gitkeep",
        "reports/monthly/.gitkeep",
        "scripts/.gitkeep",
    ]
    for item in required_markers:
        assert Path(item).is_file(), item


def test_raw_garmin_csvs_are_ignored_but_gitkeep_is_allowed():
    assert is_ignored("data/raw/garmin/Activities.csv")
    assert not is_ignored("data/raw/garmin/.gitkeep")
    assert is_ignored("logs/app.log")
    assert is_ignored(".env")
    assert not is_ignored("reports/dashboard.xlsx")
    assert not is_ignored("data/manual/screenshots/example.png")


def test_makefile_uses_configurable_python_interpreter():
    makefile = Path("Makefile").read_text()
    assert "PYTHON ?= python3" in makefile
    assert "$(PYTHON) -m pytest -q" in makefile
    assert "coach:" in makefile
    assert "$(PYTHON) scripts/generate_recommendation.py" in makefile
    assert "\n\tpython " not in makefile
