#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from running_coach.llm import (  # noqa: E402
    LlmResponseValidationError,
    build_llm_request,
    render_validated_recommendation,
    validate_llm_response,
    write_llm_request,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or validate an auditable LLM coach recommendation."
    )
    parser.add_argument("--repo-root", default=REPO_ROOT, type=Path)
    parser.add_argument("--output-dir", default=Path("reports/llm"), type=Path)
    parser.add_argument(
        "--response",
        type=Path,
        help="Validate a local JSON LLM response and write latest-recommendation.md.",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir

    written = write_llm_request(repo_root, output_dir)
    print(f"llm_request_json={written['json']}")
    print(f"llm_request_markdown={written['markdown']}")

    if args.response is None:
        return 0

    response_path = args.response
    if not response_path.is_absolute():
        response_path = repo_root / response_path
    response = json.loads(response_path.read_text(encoding="utf-8"))
    request = build_llm_request(repo_root)
    try:
        validated = validate_llm_response(response, request)
    except LlmResponseValidationError as exc:
        print(f"invalid_llm_response={exc}", file=sys.stderr)
        return 2

    recommendation_path = output_dir / "latest-recommendation.md"
    recommendation_path.write_text(
        render_validated_recommendation(validated), encoding="utf-8"
    )
    validated_path = output_dir / "latest-recommendation.json"
    validated_path.write_text(
        json.dumps(validated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"llm_recommendation_markdown={recommendation_path}")
    print(f"llm_recommendation_json={validated_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
