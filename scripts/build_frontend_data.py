#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from running_coach.frontend_data import write_frontend_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the GitHub Pages frontend data payload.")
    parser.add_argument("--repo-root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON path. Defaults to web/public/data/app-data.json.",
    )
    args = parser.parse_args()

    output = Path(args.output) if args.output else None
    written = write_frontend_payload(Path(args.repo_root), output)
    print(f"Wrote frontend payload: {written}")


if __name__ == "__main__":
    main()
