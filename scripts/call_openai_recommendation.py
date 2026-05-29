#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from running_coach.llm import (  # noqa: E402
    LlmResponseValidationError,
    build_llm_request,
    render_llm_request_markdown,
    render_validated_recommendation,
    validate_llm_response,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Call OpenAI for a validated coaching recommendation.")
    parser.add_argument("--repo-root", default=REPO_ROOT, type=Path)
    parser.add_argument("--output-dir", default=Path("reports/llm"), type=Path)
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-4.1"))
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("openai_status=skipped_missing_OPENAI_API_KEY")
        return 0

    repo_root = args.repo_root.resolve()
    output_dir = args.output_dir if args.output_dir.is_absolute() else repo_root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    request = build_llm_request(repo_root)
    prompt = _prompt(request)
    response_text = _call_responses_api(api_key=api_key, model=args.model, prompt=prompt)

    raw_path = output_dir / "latest-openai-response.json"
    parsed_response = json.loads(response_text)
    raw_path.write_text(json.dumps(parsed_response, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    try:
        validated = validate_llm_response(parsed_response, request)
    except LlmResponseValidationError as exc:
        print(f"openai_status=invalid_response:{exc}", file=sys.stderr)
        return 2

    (output_dir / "latest-recommendation.json").write_text(
        json.dumps(validated, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "latest-recommendation.md").write_text(
        render_validated_recommendation(validated),
        encoding="utf-8",
    )
    print(f"openai_status=validated model={args.model}")
    return 0


def _prompt(request: dict[str, Any]) -> str:
    return (
        "Você é o motor de recomendação do runnercoach. Responda somente com JSON válido, "
        "sem Markdown, seguindo exatamente o schema abaixo. Preserve todos os contratos de dados.\n\n"
        f"{render_llm_request_markdown(request)}"
    )


def _call_responses_api(*, api_key: str, model: str, prompt: str) -> str:
    body = {
        "model": model,
        "input": prompt,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "running_coach_recommendation",
                "strict": True,
                "schema": _response_json_schema(),
            }
        },
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API HTTP {exc.code}: {detail}") from exc

    text = _extract_response_text(payload)
    if not text:
        raise RuntimeError("OpenAI response did not contain text output")
    return text


def _extract_response_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    chunks: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "\n".join(chunks).strip()


def _response_json_schema() -> dict[str, Any]:
    fields = {
        "schema_version": {"type": "integer", "const": 1},
        "recommendation_id": {"type": "string"},
        "next_workout_action": {"type": "string"},
        "decision_type": {"type": "string"},
        "confidence": {"type": "string"},
        "summary": {"type": "string"},
        "what_workout_showed": {"type": "string"},
        "risk_assessment": {"type": "string"},
        "next_workout": {"type": "string"},
        "science_refs": {"type": "array", "items": {"type": "string"}},
        "evidence_used": {"type": "array", "items": {"type": "string"}},
        "missing_evidence": {"type": "array", "items": {"type": "string"}},
        "athlete_scope": {"type": "string"},
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": fields,
        "required": list(fields),
    }


if __name__ == "__main__":
    raise SystemExit(main())
