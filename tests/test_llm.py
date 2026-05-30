import json
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from running_coach.llm import (
    LlmResponseValidationError,
    build_llm_request,
    render_llm_request_markdown,
    validate_llm_response,
    write_llm_request,
)


def test_llm_request_separates_shared_evidence_from_matheus_solo():
    request = build_llm_request(Path("."))

    assert request["schema_version"] == 1
    assert request["latest_shared_workout"]["athlete_context"] == (
        "shared_run_with_manual_checkin"
    )
    assert request["latest_shared_workout"]["avg_pace"] == "6:47"
    assert request["latest_matheus_solo"]["avg_pace"] == "4:22"
    assert request["latest_matheus_solo"]["bruna_evidence"] == "not_applicable"
    assert "Garmin physiology is Matheus-only" in request["data_contract"]
    assert "Do not use Matheus solo pace as Bruna evolution" in request["forbidden_claims"]


def test_llm_request_markdown_contains_response_schema_and_safety_rules():
    request = build_llm_request(Path("."))
    markdown = render_llm_request_markdown(request)

    assert "## Required Response Schema" in markdown
    assert "## Forbidden Claims" in markdown
    assert "replace_with_easy" in markdown
    assert "safety-red-flag-conservative" in markdown


def test_write_llm_request_creates_json_and_markdown(tmp_path):
    output_dir = tmp_path / "reports/llm"

    written = write_llm_request(Path("."), output_dir)

    assert written["json"].name == "latest-request.json"
    assert written["markdown"].name == "latest-request.md"
    payload = json.loads(written["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert "Latest Shared Workout" in written["markdown"].read_text(encoding="utf-8")


def test_write_llm_request_is_deterministic(tmp_path):
    output_dir = tmp_path / "reports/llm"

    written = write_llm_request(Path("."), output_dir)
    first_json_hash = hashlib.sha256(written["json"].read_bytes()).hexdigest()
    first_markdown_hash = hashlib.sha256(written["markdown"].read_bytes()).hexdigest()
    written = write_llm_request(Path("."), output_dir)
    second_json_hash = hashlib.sha256(written["json"].read_bytes()).hexdigest()
    second_markdown_hash = hashlib.sha256(written["markdown"].read_bytes()).hexdigest()

    assert second_json_hash == first_json_hash
    assert second_markdown_hash == first_markdown_hash


def test_generate_recommendation_cli_writes_request_artifacts(tmp_path):
    output_dir = tmp_path / "llm"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/generate_recommendation.py",
            "--output-dir",
            str(output_dir),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert (output_dir / "latest-request.json").exists()
    assert (output_dir / "latest-request.md").exists()
    assert "llm_request_json=" in result.stdout


def test_generate_recommendation_cli_validates_response(tmp_path):
    output_dir = tmp_path / "llm"
    response_path = tmp_path / "response.json"
    response_path.write_text(
        json.dumps(_valid_response(), ensure_ascii=False),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/generate_recommendation.py",
            "--output-dir",
            str(output_dir),
            "--response",
            str(response_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert (output_dir / "latest-recommendation.json").exists()
    assert (output_dir / "latest-recommendation.md").exists()


def test_validate_llm_response_accepts_safe_structured_response():
    request = build_llm_request(Path("."))
    response = {
        "schema_version": 1,
        "recommendation_id": "llm-20260529-001",
        "next_workout_action": "reduce_next_workout",
        "decision_type": "reduce",
        "confidence": "medium",
        "summary": "Manter conservador porque ainda faltam evidencias de FC da Bruna.",
        "what_workout_showed": "Treino compartilhado teve check-in e pace medio 6:47.",
        "risk_assessment": "Risco moderado por evidencia incompleta.",
        "next_workout": "30-40 minutos leve, sem buscar 5:50/km.",
        "science_refs": ["load-management-recovery"],
        "evidence_used": [
            "workout-garmin-20260528T161736-7p47km-3039s-17b463bc"
        ],
        "missing_evidence": ["bruna_avg_hr", "bruna_max_hr"],
        "athlete_scope": "shared_run",
    }

    validated = validate_llm_response(response, request)

    assert validated["next_workout_action"] == "reduce_next_workout"
    assert validated["science_refs"] == ["load-management-recovery"]


def test_validate_llm_response_rejects_unapproved_science_refs():
    request = build_llm_request(Path("."))
    response = _valid_response(science_refs=["blog-post"])

    with pytest.raises(LlmResponseValidationError, match="unapproved science_refs"):
        validate_llm_response(response, request)


def test_validate_llm_response_rejects_matheus_solo_as_bruna_scope():
    request = build_llm_request(Path("."))
    response = _valid_response(
        evidence_used=["workout-garmin-20260528T171417-1p33km-349s-245ee321"],
        athlete_scope="bruna",
    )

    with pytest.raises(LlmResponseValidationError, match="Matheus solo"):
        validate_llm_response(response, request)


def test_validate_llm_response_rejects_unknown_evidence_ids():
    request = build_llm_request(Path("."))
    response = _valid_response(evidence_used=["workout-does-not-exist"])

    with pytest.raises(LlmResponseValidationError, match="unknown evidence_used"):
        validate_llm_response(response, request)


def test_validate_llm_response_rejects_action_against_high_pse_and_achilles_guardrail():
    request = build_llm_request(Path("."))
    request["latest_shared_workout"]["bruna_pse"] = "9"
    request["latest_shared_workout"]["matheus_achilles_after"] = "5"
    response = _valid_response(
        next_workout_action="maintain_next_workout",
        decision_type="maintain",
        evidence_used=[request["latest_shared_workout"]["workout_id"]],
    )

    with pytest.raises(LlmResponseValidationError, match="deterministic guardrail"):
        validate_llm_response(response, request)


def test_validate_llm_response_rejects_unknown_fields():
    request = build_llm_request(Path("."))
    response = _valid_response()
    response["invented_metric"] = "Bruna VO2max 60"

    with pytest.raises(LlmResponseValidationError, match="unknown fields"):
        validate_llm_response(response, request)


def _valid_response(**overrides):
    response = {
        "schema_version": 1,
        "recommendation_id": "llm-20260529-001",
        "next_workout_action": "reduce_next_workout",
        "decision_type": "reduce",
        "confidence": "medium",
        "summary": "Manter o plano com cautela.",
        "what_workout_showed": "Ha evidencia compartilhada, mas ainda falta FC da Bruna.",
        "risk_assessment": "Risco controlado com evidencia incompleta.",
        "next_workout": "Executar proximo treino por faixa e PSE.",
        "science_refs": ["volleyball-neuromuscular-load"],
        "evidence_used": [
            "workout-garmin-20260528T161736-7p47km-3039s-17b463bc"
        ],
        "missing_evidence": [],
        "athlete_scope": "shared_run",
    }
    response.update(overrides)
    return response


def test_prose_lint_rejects_fabricated_study_citation():
    request = build_llm_request(Path("."))
    bad = _valid_response(
        next_workout="10x400m at 5k pace based on Smith 2024 meta-analysis"
    )
    with pytest.raises(LlmResponseValidationError, match="prose must not cite"):
        validate_llm_response(bad, request)


def test_prose_lint_rejects_doi_in_prose():
    request = build_llm_request(Path("."))
    bad = _valid_response(risk_assessment="Risco alto conforme 10.1136/bjsports-2016-096581.")
    with pytest.raises(LlmResponseValidationError, match="prose must not cite"):
        validate_llm_response(bad, request)


def test_prose_lint_allows_clean_portuguese_prose():
    request = build_llm_request(Path("."))
    ok = _valid_response()
    # Clean PT-BR prose with no author-year/DOI must pass.
    validate_llm_response(ok, request)


_LINT_SHOULD_BLOCK = [
    "Segundo Seiler, vamos manter 80% leve.",
    "Conforme o estudo de 2016, a carga deve subir com cautela.",
    "Meta-analise de Bosquet sugere respeitar recuperacao.",
    "De acordo com a IOC, sintomas no tendao pedem cautela.",
    "Pfitzinger recomenda manter o facil facil.",
    "O consenso do ACSM reforca controlar volume.",
    "Veja www.bjsm.com para a discussao.",
    "Como descrito por Foster e colegas, monitore PSE.",
    "Segundo Laursen & Buchheit, mantenha controlado.",
    "10x400m based on Smith 2024 meta-analysis",
    "Risco conforme doi:10.1136/bjsports-2016-096581.",
]

_LINT_SHOULD_ALLOW = [
    "Em 2027 voce corre a meia com mais seguranca.",
    "Semana 2024 do ciclo deve priorizar sono.",
    "Sessao Janeiro 2027 deve ser leve.",
    "24 de janeiro de 2027 e a prova.",
    "Mantenha o ritmo em 5:30/km e o longao leve.",
    "Reduza o volume nesta semana e priorize sono.",
]


@pytest.mark.parametrize("prose", _LINT_SHOULD_BLOCK)
def test_prose_lint_blocks_citations(prose):
    request = build_llm_request(Path("."))
    with pytest.raises(LlmResponseValidationError, match="prose must not cite"):
        validate_llm_response(_valid_response(summary=prose), request)


@pytest.mark.parametrize("prose", _LINT_SHOULD_ALLOW)
def test_prose_lint_allows_legit_ptbr(prose):
    request = build_llm_request(Path("."))
    validate_llm_response(_valid_response(summary=prose), request)


def test_prose_lint_rejects_english_prose():
    request = build_llm_request(Path("."))
    bad = _valid_response(summary="Keep the planned workout because the risk is low.")
    with pytest.raises(LlmResponseValidationError, match="Portuguese"):
        validate_llm_response(bad, request)
