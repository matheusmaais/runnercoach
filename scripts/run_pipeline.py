from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from running_coach.pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--garmin", default="data/raw/garmin/Activities.csv")
    parser.add_argument("--after-workout", action="store_true")
    parser.add_argument("--analyze-only", action="store_true")
    parser.add_argument("--monthly-report", action="store_true")
    parser.add_argument("--no-plan-refresh", action="store_true",
                        help="skip regenerating the living plan")
    args = parser.parse_args()

    if not args.no_plan_refresh:
        from datetime import date

        from build_plan import regenerate

        try:
            count = regenerate(REPO_ROOT, date.today())
            print(f"living plan refreshed: {count} rows")
        except Exception as exc:  # fail-open: never block the pipeline on plan refresh
            print(f"plan refresh skipped ({type(exc).__name__}: {exc})")

    run_pipeline(
        garmin_csv=Path(args.garmin),
        repo_root=REPO_ROOT,
        after_workout=args.after_workout,
        monthly_report=args.monthly_report,
    )


if __name__ == "__main__":
    main()
