#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
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
    parser = argparse.ArgumentParser(description="Call Amazon Bedrock for a validated coaching recommendation.")
    parser.add_argument("--repo-root", default=REPO_ROOT, type=Path)
    parser.add_argument("--output-dir", default=Path("reports/llm"), type=Path)
    parser.add_argument("--region", default=os.environ.get("BEDROCK_REGION", "us-east-1"))
    parser.add_argument(
        "--model-id",
        default=os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6"),
    )
    args = parser.parse_args()

    bearer_token = os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
    if not bearer_token:
        print("bedrock_status=skipped_missing_AWS_BEARER_TOKEN_BEDROCK")
        return 0

    repo_root = args.repo_root.resolve()
    output_dir = args.output_dir if args.output_dir.is_absolute() else repo_root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    request = build_llm_request(repo_root)
    response_text = _call_bedrock_converse(
        bearer_token=bearer_token,
        region=args.region,
        model_id=args.model_id,
        prompt=_prompt(request),
    )

    raw_path = output_dir / "latest-bedrock-response.json"
    parsed_response = _repair_bedrock_response(json.loads(_strip_json_fences(response_text)))
    raw_path.write_text(json.dumps(parsed_response, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    try:
        validated = validate_llm_response(parsed_response, request)
    except LlmResponseValidationError as exc:
        print(f"bedrock_status=invalid_response:{exc}", file=sys.stderr)
        return 2

    (output_dir / "latest-recommendation.json").write_text(
        json.dumps(validated, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "latest-recommendation.md").write_text(
        render_validated_recommendation(validated),
        encoding="utf-8",
    )
    print(f"bedrock_status=validated model={args.model_id} region={args.region}")
    return 0


def _prompt(request: dict[str, Any]) -> str:
    return (
        "Você é o motor de recomendação do runnercoach. Responda somente com JSON válido, "
        "sem Markdown, sem cercas de código, seguindo exatamente o schema solicitado. "
        "Não inclua propriedades extras. Preserve todos os contratos de dados. "
        "decision_type deve ser exatamente um destes valores: maintain, reduce, alter, defer, "
        "recover, hold_phase, advance_phase, race_strategy. next_workout_action deve ser "
        "exatamente um destes valores: maintain_next_workout, reduce_next_workout, "
        "replace_with_easy, replace_with_off, replace_with_cross_training, defer_quality, "
        "bruna_without_matheus, request_manual_resolution. science_refs, evidence_used e "
        "missing_evidence devem ser arrays JSON, mesmo quando houver apenas um item.\n\n"
        f"{render_llm_request_markdown(request)}"
    )


def _call_bedrock_converse(*, bearer_token: str, region: str, model_id: str, prompt: str) -> str:
    encoded_model = urllib.parse.quote(model_id, safe="")
    url = f"https://bedrock-runtime.{region}.amazonaws.com/model/{encoded_model}/converse"
    body = {
        "messages": [
            {
                "role": "user",
                "content": [{"text": prompt}],
            }
        ],
        "inferenceConfig": {
            "maxTokens": 2400,
            "temperature": 0.2,
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Bedrock API HTTP {exc.code}: {detail}") from exc

    text = _extract_bedrock_text(payload)
    if not text:
        raise RuntimeError("Bedrock response did not contain text output")
    return text


def _extract_bedrock_text(payload: dict[str, Any]) -> str:
    chunks: list[str] = []
    message = (payload.get("output") or {}).get("message") or {}
    for content in message.get("content", []):
        text = content.get("text")
        if isinstance(text, str):
            chunks.append(text)
    return "\n".join(chunks).strip()


def _strip_json_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    if stripped.lower().startswith("json\n"):
        stripped = stripped[5:].strip()
    return stripped


def _repair_bedrock_response(response: dict[str, Any]) -> dict[str, Any]:
    repaired = dict(response)
    for key in ("science_refs", "evidence_used", "missing_evidence"):
        value = repaired.get(key)
        if isinstance(value, str):
            repaired[key] = [item.strip() for item in value.split(",") if item.strip()]

    decision_aliases = {
        "pre_workout_recommendation": "race_strategy",
        "pre_race_taper_confirmation": "race_strategy",
    }
    decision_type = repaired.get("decision_type")
    if isinstance(decision_type, str) and decision_type in decision_aliases:
        repaired["decision_type"] = decision_aliases[decision_type]

    return repaired


if __name__ == "__main__":
    raise SystemExit(main())
