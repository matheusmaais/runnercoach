from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from running_coach.csv_utils import decode_json_cell


def build_frontend_payload(repo_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    workouts = _read_csv(root / "data/processed/workouts.csv")
    decisions = _read_csv(root / "data/processed/decisions.csv")
    science_refs = _read_csv(root / "data/processed/science_refs.csv")
    plan_status = _read_csv(root / "data/processed/plan_status.csv")
    llm_request = _read_json(root / "reports/llm/latest-request.json")
    latest_recommendation = _read_json(root / "reports/llm/latest-recommendation.json")

    recent_workouts = [_present_workout(row) for row in _latest_rows(workouts, 12)]
    next_workouts = [_present_plan(row) for row in plan_status if row.get("planned_status") == "planned"]
    latest_shared = _normalize_llm_workout(llm_request.get("latest_shared_workout", {}))
    latest_solo = _normalize_llm_workout(llm_request.get("latest_matheus_solo", {}))

    return {
        "generated_at": llm_request.get("generated_at") or _fallback_generated_at(workouts),
        "mission": {
            "name": "Meia Forte Janeiro 2027",
            "target_race_window": "late January 2027",
            "primary_objective": "Correr uma meia maratona forte sem elevar risco de lesão desnecessariamente.",
            "short_term_focus": "Maximizar 10K com pacing conservador, recuperação e decisões auditáveis.",
            "interface_role": "Interface principal de leitura gerada a partir dos dados versionados do repositório.",
        },
        "athletes": _athletes(),
        "current_state": {
            "phase": _phase_from_plan(plan_status),
            "status": _status_from_latest(latest_shared, latest_solo),
            "latest_shared_workout": latest_shared,
            "latest_matheus_solo": latest_solo,
            "summary_markdown": llm_request.get("current_state", ""),
            "risk_level": _risk_level(latest_shared, latest_solo),
        },
        "next_workouts": next_workouts,
        "recent_workouts": recent_workouts,
        "weekly_summary": _weekly_summary(workouts),
        "trends": _trends(workouts),
        "decisions": [_present_decision(row) for row in _latest_rows(decisions, 10)],
        "science_refs": [_present_science_ref(row) for row in science_refs if _truthy(row.get("approved"))],
        "llm_context": _llm_context(llm_request),
        "latest_llm_recommendation": _present_llm_recommendation(latest_recommendation),
        "evidence_contracts": _evidence_contracts(),
        "presentation_warnings": [
            "Pace solo do Matheus não pode ser renderizado como evolução da Bruna.",
            "FC, cadência, potência, contato com solo e passada do Garmin são apenas do Matheus.",
            "Zonas da Bruna são faixas conservadoras até aumentar evidência manual de FC/PSE.",
            "Treino perdido não deve ser compensado com volume extra.",
        ],
    }


def write_frontend_payload(repo_root: Path, output_path: Path | None = None) -> Path:
    root = repo_root.resolve()
    target = output_path or root / "web/public/data/app-data.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = build_frontend_payload(root)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_rows(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: row.get("local_datetime") or row.get("date") or "", reverse=True)[:limit]


def _athletes() -> dict[str, Any]:
    return {
        "matheus": {
            "age": 39,
            "role": "pacemaker saudável com velocidade residual",
            "strategic_limit": "left_achilles",
            "data_sources": {
                "physiology": "garmin_watch",
                "pace": "garmin_or_shared_run",
                "injury_risk": "manual_achilles_checkin",
            },
            "current_training_state": {
                "residual_speed": "alta",
                "latest_speed_signal": "1,33 km @ 4:22/km com Aquiles silencioso",
                "coaching_bias": "evitar máxima velocidade frequente; proteger Aquiles primeiro",
            },
        },
        "bruna": {
            "age": 32,
            "role": "atleta principal de performance",
            "strategic_limit": "progressão segura de 5K/10K para meia forte",
            "data_sources": {
                "pace": "shared_run",
                "heart_rate": "manual_galaxy_watch_when_provided",
                "subjective": "manual_pse_symptoms_recovery",
            },
            "current_training_state": {
                "easy_long": "6:40-7:00/km",
                "strong_sustainable": "6:10-6:20/km",
                "estimated_threshold": "~6:00/km",
                "short_max_current": "~5:50/km",
                "current_10k_projection": "6:10-6:20/km depending on course, weather, and pacing",
            },
        },
    }


def _normalize_llm_workout(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    normalized["shared_run"] = _truthy(normalized.get("shared_run"))
    normalized["bruna_present"] = _truthy(normalized.get("bruna_present"))
    normalized["participants"] = _as_list(normalized.get("participants"))
    normalized["missing_evidence"] = _as_list(normalized.get("missing_evidence"))
    normalized["bruna_symptoms"] = _as_list(normalized.get("bruna_symptoms"))
    normalized["evidence_confidence"] = _evidence_confidence(normalized)
    normalized["display_context"] = (
        "Pace compartilhado informa Bruna apenas com contexto manual/PSE."
        if normalized["shared_run"] and normalized["bruna_present"]
        else "Esforço Garmin apenas do Matheus; não usar como evolução da Bruna."
    )
    return normalized


def _present_workout(row: dict[str, str]) -> dict[str, Any]:
    shared = _truthy(row.get("shared_run"))
    bruna_present = _truthy(row.get("bruna_present"))
    missing = _as_list(row.get("missing_evidence"))
    badges = ["shared_pace" if shared and bruna_present else "garmin_matheus"]
    if row.get("bruna_pse"):
        badges.append("bruna_pse")
    if row.get("bruna_avg_hr") or row.get("bruna_max_hr"):
        badges.append("bruna_hr_manual")
    if "bruna_avg_hr" in missing or "bruna_max_hr" in missing:
        badges.append("bruna_hr_missing")
    if _truthy(row.get("volleyball_previous_day")):
        badges.append("volleyball_load")
    if row.get("matheus_achilles_after") and row.get("matheus_achilles_after") != "0":
        badges.append("achilles_watch")

    return {
        "workout_id": row.get("workout_id", ""),
        "date": row.get("local_date") or row.get("date", ""),
        "datetime": row.get("local_datetime", ""),
        "athlete_context": row.get("athlete_context", ""),
        "activity_type": row.get("activity_type", ""),
        "category": row.get("category", ""),
        "distance_km": _number(row.get("distance_km")),
        "duration_seconds": _number(row.get("duration")),
        "avg_pace": row.get("avg_pace", ""),
        "matheus_avg_hr": row.get("matheus_avg_hr", ""),
        "matheus_max_hr": row.get("matheus_max_hr", ""),
        "bruna_avg_hr": row.get("bruna_avg_hr", ""),
        "bruna_max_hr": row.get("bruna_max_hr", ""),
        "bruna_pse": row.get("bruna_pse", ""),
        "missing_evidence": missing,
        "evidence_level": row.get("evidence_level", ""),
        "evidence_confidence": row.get("confidence") or _evidence_confidence(row),
        "recommendation_action": row.get("recommendation_action", ""),
        "decision_after_workout": row.get("decision_after_workout", ""),
        "shared_run": shared,
        "bruna_present": bruna_present,
        "badges": badges,
        "bruna_usage": (
            "shared_pace_with_manual_context"
            if shared and bruna_present
            else "not_bruna_evidence"
        ),
    }


def _present_plan(row: dict[str, str]) -> dict[str, Any]:
    category = row.get("intended_category", "")
    return {
        "planned_workout_id": row.get("planned_workout_id", ""),
        "week_number": row.get("week_number", ""),
        "date": row.get("date", ""),
        "phase": row.get("phase", ""),
        "intended_category": category,
        "planned_status": row.get("planned_status", ""),
        "derived_status": row.get("derived_status", ""),
        "evidence": row.get("evidence", ""),
        "missing_evidence": _as_list(row.get("missing_evidence")),
        "decision_basis": _decision_basis(category),
        "safety_triggers": _safety_triggers(category),
    }


def _present_decision(row: dict[str, str]) -> dict[str, Any]:
    return {
        "date": row.get("local_date") or row.get("date", ""),
        "event": row.get("event", ""),
        "decision": row.get("decision", ""),
        "reason": row.get("reason", ""),
        "impact": row.get("impact", ""),
        "confidence": row.get("confidence", ""),
        "evidence": row.get("evidence", ""),
        "science_refs": _as_list(row.get("science_refs")),
        "recommendation_action": row.get("recommendation_action", ""),
        "related_workout_id": row.get("related_workout_id", ""),
    }


def _present_science_ref(row: dict[str, str]) -> dict[str, Any]:
    return {
        "science_ref_id": row.get("science_ref_id", ""),
        "title": row.get("title", ""),
        "authors": row.get("authors", ""),
        "year": row.get("year", ""),
        "journal_or_publisher": row.get("journal_or_publisher", ""),
        "doi_or_url": row.get("doi_or_url", ""),
        "finding": row.get("finding", ""),
        "practical_application": row.get("practical_application", ""),
        "limits": row.get("limits", ""),
        "tags": _as_list(row.get("tags")),
    }


def _weekly_summary(workouts: list[dict[str, str]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"week": "", "runs": 0, "distance_km": 0.0, "quality_runs": 0, "shared_runs": 0}
    )
    for row in workouts:
        local_date = row.get("local_date") or row.get("date")
        if not local_date:
            continue
        week = date.fromisoformat(local_date).isocalendar()
        key = f"{week.year}-W{week.week:02d}"
        bucket = buckets[key]
        bucket["week"] = key
        bucket["runs"] += 1
        bucket["distance_km"] += _number(row.get("distance_km")) or 0
        if row.get("category") in {"quality", "threshold", "race"} or "forte" in row.get("notes", "").lower():
            bucket["quality_runs"] += 1
        if _truthy(row.get("shared_run")) and _truthy(row.get("bruna_present")):
            bucket["shared_runs"] += 1
    return [
        {**bucket, "distance_km": round(bucket["distance_km"], 2)}
        for _, bucket in sorted(buckets.items(), reverse=True)[:8]
    ][::-1]


def _trends(workouts: list[dict[str, str]]) -> dict[str, Any]:
    chronological = sorted(workouts, key=lambda row: row.get("local_datetime") or row.get("date") or "")
    pace = [
        {
            "date": row.get("local_date") or row.get("date", ""),
            "pace_seconds": _pace_to_seconds(row.get("avg_pace")),
            "avg_pace": row.get("avg_pace", ""),
            "context": row.get("athlete_context", ""),
        }
        for row in chronological
        if _pace_to_seconds(row.get("avg_pace")) is not None
    ]
    long_runs = [
        {
            "date": row.get("local_date") or row.get("date", ""),
            "distance_km": _number(row.get("distance_km")),
            "avg_pace": row.get("avg_pace", ""),
        }
        for row in chronological
        if (_number(row.get("distance_km")) or 0) >= 8
    ]
    strong_shared = [
        item
        for item in pace
        if item["context"] == "shared_run_with_manual_checkin"
        and item["pace_seconds"] is not None
        and 350 <= item["pace_seconds"] <= 390
    ]
    return {
        "pace": pace,
        "long_runs": long_runs,
        "strong_sustainable": strong_shared,
        "risk": _risk_trend(chronological),
    }


def _risk_trend(workouts: list[dict[str, str]]) -> list[dict[str, Any]]:
    trend = []
    for row in workouts:
        score = 1
        reasons = []
        if _truthy(row.get("volleyball_previous_day")):
            score += 1
            reasons.append("volleyball_previous_day")
        if row.get("bruna_pse") and float(row["bruna_pse"]) >= 9:
            score += 2
            reasons.append("bruna_high_pse")
        if row.get("matheus_achilles_after") and float(row["matheus_achilles_after"]) > 3:
            score += 3
            reasons.append("achilles_above_3")
        if row.get("sleep_quality") in {"ruim", "bad", "poor"}:
            score += 1
            reasons.append("sleep_risk")
        trend.append(
            {
                "date": row.get("local_date") or row.get("date", ""),
                "score": min(score, 5),
                "reasons": reasons,
            }
        )
    return trend


def _llm_context(llm_request: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at": llm_request.get("generated_at", ""),
        "data_contract": llm_request.get("data_contract", ""),
        "forbidden_claims": llm_request.get("forbidden_claims", []),
        "required_response_schema": llm_request.get("required_response_schema", {}),
        "approved_science_ref_count": len(llm_request.get("approved_science_refs", [])),
    }


def _present_llm_recommendation(recommendation: dict[str, Any]) -> dict[str, Any] | None:
    if not recommendation:
        return None
    return {
        "recommendation_id": recommendation.get("recommendation_id", ""),
        "decision_type": recommendation.get("decision_type", ""),
        "next_workout_action": recommendation.get("next_workout_action", ""),
        "confidence": recommendation.get("confidence", ""),
        "summary": recommendation.get("summary", ""),
        "what_workout_showed": recommendation.get("what_workout_showed", ""),
        "risk_assessment": recommendation.get("risk_assessment", ""),
        "next_workout": recommendation.get("next_workout", ""),
        "science_refs": _as_list(recommendation.get("science_refs")),
        "evidence_used": _as_list(recommendation.get("evidence_used")),
        "missing_evidence": _as_list(recommendation.get("missing_evidence")),
    }


def _evidence_contracts() -> dict[str, Any]:
    return {
        "garmin_owner": "matheus",
        "shared_data": ["pace", "distance", "elapsed_time"],
        "bruna_manual_data": ["heart_rate_screenshot", "pse", "symptoms", "sleep", "recovery"],
        "hard_rules": [
            "Se Bruna PSE >= 9 em treino, próxima sessão deve ser leve ou off.",
            "Se Bruna tiver sintomas fortes, reduzir intensidade.",
            "Se Aquiles do Matheus > 3/10, remover velocidade, subidas e descidas.",
            "Se teve vôlei no dia anterior, evitar trabalho máximo.",
            "Nunca compensar treino perdido com volume extra.",
        ],
    }


def _phase_from_plan(plan_status: list[dict[str, str]]) -> str:
    for row in plan_status:
        if row.get("phase"):
            return row["phase"]
    return "ten_k_polish"


def _status_from_latest(latest_shared: dict[str, Any], latest_solo: dict[str, Any]) -> str:
    if latest_shared.get("bruna_evidence") == "available" and latest_solo.get("bruna_evidence") == "not_applicable":
        return "on_track_with_conservative_guardrails"
    return "needs_manual_evidence"


def _risk_level(latest_shared: dict[str, Any], latest_solo: dict[str, Any]) -> str:
    if latest_solo.get("matheus_achilles_after") and str(latest_solo["matheus_achilles_after"]) not in {"", "0"}:
        return "attention"
    if latest_shared.get("volleyball_previous_day") in {True, "true", "True"}:
        return "moderate"
    return "low"


def _decision_basis(category: str) -> str:
    basis = {
        "diagnostic_race_10k": "Usar como prova diagnóstica forte, depois proteger os próximos 2-4 dias para recuperação.",
        "easy_run": "Restaurar consistência e sinal aeróbico depois da prova sem compensar volume.",
    }
    return basis.get(category, "Manter coerência com a fase atual, última evidência e regras de segurança.")


def _safety_triggers(category: str) -> list[str]:
    common = [
        "bad_sleep_reduce_volume_or_intensity",
        "bruna_symptoms_reduce_intensity",
        "matheus_achilles_above_3_remove_speed",
    ]
    if category == "diagnostic_race_10k":
        return common + ["do_not_chase_pace_if_heat_or_course_raise_risk"]
    return common + ["keep_easy_even_if_previous_session_was_missed"]


def _fallback_generated_at(workouts: list[dict[str, str]]) -> str:
    latest = _latest_rows(workouts, 1)
    if latest:
        return latest[0].get("local_datetime") or latest[0].get("date") or ""
    return ""


def _evidence_confidence(row: dict[str, Any]) -> str:
    if _truthy(row.get("shared_run")) and _truthy(row.get("bruna_present")) and row.get("bruna_pse"):
        return "medium"
    if _truthy(row.get("shared_run")) and _truthy(row.get("bruna_present")):
        return "low"
    return "low"


def _as_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return decode_json_cell(value)
        except (json.JSONDecodeError, ValueError):
            return [value]
    return [value]


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "sim"}


def _number(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return round(float(value), 2)
    except ValueError:
        return None


def _pace_to_seconds(value: str | None) -> int | None:
    if not value or ":" not in value:
        return None
    minutes, seconds = value.split(":", 1)
    try:
        return int(minutes) * 60 + int(seconds)
    except ValueError:
        return None
