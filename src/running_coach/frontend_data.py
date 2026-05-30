from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from running_coach.csv_utils import decode_json_cell


def build_frontend_payload(repo_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    workouts = _read_csv(root / "data/processed/workouts.csv")
    decisions = _read_csv(root / "data/processed/decisions.csv")
    science_refs = _read_csv(root / "data/processed/science_refs.csv")
    plan_status = _read_csv(root / "data/processed/plan_status.csv")
    _benchmark_zones = _load_benchmark_zones(root)
    # Build the LLM-context request fresh from current processed data so the
    # frontend never shows a stale 'latest shared workout' from an old artifact.
    try:
        from running_coach.llm import build_llm_request

        llm_request = build_llm_request(root)
        llm_request_source = "fresh"
    except (FileNotFoundError, KeyError, ValueError):
        llm_request = _read_json(root / "reports/llm/latest-request.json")
        llm_request_source = "fallback_artifact"
    latest_recommendation_path = root / "reports/llm/latest-recommendation.json"
    latest_recommendation = _read_json(latest_recommendation_path)

    recent_workouts = [_present_workout(row) for row in _latest_rows(workouts, 12)]
    next_workouts = [_present_plan(row) for row in plan_status if row.get("planned_status") == "planned"]
    latest_shared = _normalize_llm_workout(llm_request.get("latest_shared_workout", {}))
    latest_solo = _normalize_llm_workout(llm_request.get("latest_matheus_solo", {}))
    trends = _trends(workouts)
    risk_level = _risk_level(latest_shared, latest_solo)
    risk_summary = _risk_summary(risk_level, trends["risk"])
    request_generated_at = llm_request.get("generated_at") or _fallback_generated_at(workouts)
    presented_latest_recommendation = _present_llm_recommendation(
        latest_recommendation,
        latest_recommendation_path,
        root,
        request_generated_at,
    )
    if presented_latest_recommendation is not None:
        rec_action = presented_latest_recommendation.get("next_workout_action", "")
        evidence = set(presented_latest_recommendation.get("evidence_used", []))
        # Compare against the decision the recommendation actually covers (its
        # evidence workout), falling back to the latest decision. Avoids
        # false positives from an unrelated later decision.
        scoped = next(
            (
                row
                for row in _latest_rows(decisions, 20)
                if row.get("related_workout_id") in evidence
                or row.get("workout_id") in evidence
            ),
            (_latest_rows(decisions, 1) or [{}])[0],
        )
        current_action = scoped.get("recommendation_action", "")
        is_stale = bool(current_action and rec_action and current_action != rec_action)
        presented_latest_recommendation["stale"] = is_stale
        presented_latest_recommendation["current_decision_action"] = current_action
        if is_stale:
            presented_latest_recommendation["stale_message"] = (
                "Análise da IA desatualizada para o último treino. "
                "A decisão atual está em 'O que fazer hoje'. Rode a análise para atualizar."
            )

    return {
        "generated_at": request_generated_at,
        "today": _today_directive(decisions, next_workouts),
        "llm_request_source": llm_request_source,
        "mission": {
            "name": "Meia Forte Janeiro 2027",
            "target_race_window": "late January 2027",
            "primary_objective": "Correr uma meia maratona forte sem elevar risco de lesão desnecessariamente.",
            "short_term_focus": "Maximizar 10K com pacing conservador, recuperação e decisões auditáveis.",
            "interface_role": "Interface principal de leitura gerada a partir dos dados versionados do repositório.",
        },
        "athletes": _athletes(workouts),
        "current_state": {
            "phase": _phase_from_plan(plan_status),
            "status": _status_from_latest(latest_shared, latest_solo),
            "latest_shared_workout": latest_shared,
            "latest_matheus_solo": latest_solo,
            "summary_markdown": llm_request.get("current_state", ""),
            "risk_level": risk_level,
            "risk_drivers": risk_summary["drivers"],
            "risk_summary": risk_summary,
        },
        "next_workouts": next_workouts,
        "week": _week_view(
            plan_status,
            _date_obj(_fallback_generated_at(workouts)[:10]) or date.today(),
            _benchmark_zones,
        ),
        "pace_zones": _benchmark_zones,
        "recent_workouts": recent_workouts,
        "weekly_summary": _weekly_summary(workouts),
        "week_narrative": _week_narrative(_weekly_summary(workouts)),
        "readiness": _readiness(workouts),
        "progression_suggestion": _progression_suggestion(workouts),
        "trends": trends,
        "decisions": [_present_decision(row) for row in _latest_rows(decisions, 10)],
        "science_refs": [_present_science_ref(row) for row in science_refs if _truthy(row.get("approved"))],
        "llm_context": _llm_context(llm_request),
        "latest_llm_recommendation": presented_latest_recommendation,
        "recommendation_history": _recommendation_history(
            root / "reports/llm",
            root,
            presented_latest_recommendation,
            request_generated_at,
        ),
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


def _athletes(workouts: list[dict[str, str]] | None = None) -> dict[str, Any]:
    workouts = workouts or []
    matheus_signal, bruna_easy, bruna_strong = _derived_pace_signals(workouts)
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
                "latest_speed_signal": matheus_signal,
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
                "easy_long": bruna_easy,
                "strong_sustainable": bruna_strong,
                "estimated_threshold": "~6:00/km (estimativa até prova)",
                "short_max_current": "~5:50/km (teto curto, não contínuo)",
                "current_10k_projection": "calibrar com prova real",
            },
        },
    }


def _derived_pace_signals(workouts: list[dict[str, str]]) -> tuple[str, str, str]:
    """Latest Matheus solo signal + Bruna easy/strong shared paces from real data.
    Falls back to honest placeholders when there is no matching evidence."""
    chrono = sorted(workouts, key=lambda r: r.get("local_datetime") or r.get("local_date") or "")
    solo = [r for r in chrono if r.get("athlete_context") == "matheus_garmin_only" and r.get("avg_pace")]
    shared = [
        r for r in chrono
        if r.get("athlete_context") == "shared_run_with_manual_checkin" and r.get("avg_pace")
    ]
    matheus_signal = (
        f"{solo[-1].get('distance_km')} km @ {solo[-1].get('avg_pace')}/km"
        if solo
        else "sem corrida solo recente"
    )
    shared_paces = sorted(
        s for s in (_pace_to_seconds(r.get("avg_pace")) for r in shared) if s
    )
    if len(shared_paces) >= 2:
        bruna_easy = f"{_fmt_pace(shared_paces[-1])}/km (compartilhado)"
        bruna_strong = f"{_fmt_pace(shared_paces[0])}/km (compartilhado)"
    elif len(shared_paces) == 1:
        bruna_easy = f"{_fmt_pace(shared_paces[0])}/km (amostra única)"
        bruna_strong = "amostra insuficiente"
    else:
        bruna_easy = "6:40-7:00/km (estimativa)"
        bruna_strong = "6:10-6:20/km (estimativa)"
    return matheus_signal, bruna_easy, bruna_strong


def _fmt_pace(sec: int) -> str:
    return f"{sec // 60}:{sec % 60:02d}"


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


def _benchmark_candidates(repo_root: Path) -> list[Any]:
    """Hard efforts that can calibrate BRUNA's zones: recent done races + recent
    Bruna-present quality/threshold/race runs (last ~120d, dist>=5km). Easy runs,
    Matheus-only runs, sprints, and stale efforts never qualify — a zone is a
    capacity ceiling proven by a recent hard Bruna effort."""
    from running_coach.pacing import Benchmark

    cutoff = (date.today() - timedelta(days=120)).isoformat()
    cands: list[Benchmark] = []
    races = repo_root / "data/plan/races.yaml"
    if races.exists():
        try:
            import yaml

            data = yaml.safe_load(races.read_text(encoding="utf-8")) or {}
            today_str = date.today().isoformat()
            for r in data.get("races") or []:
                if (r.get("status") == "done" and r.get("time_seconds") and r.get("distance_km")
                        and cutoff <= str(r.get("date") or "") <= today_str):
                    cands.append(Benchmark(float(r["distance_km"]), int(r["time_seconds"]),
                                           str(r.get("conditions", "normal"))))
        except Exception:
            pass

    workouts = repo_root / "data/processed/workouts.csv"
    if workouts.exists():
        try:
            import csv

            from running_coach.pacing import classify_effort, select_best, zones_from_benchmark

            # First pass: zones from races only, to classify training efforts against.
            base_zones = zones_from_benchmark(select_best(cands)) if cands else {}
            for row in csv.DictReader(workouts.open(encoding="utf-8")):
                if (row.get("local_date") or "") < cutoff:
                    continue
                # Bruna evidence is mandatory: never calibrate her from Matheus-only data.
                if not (_truthy(row.get("shared_run")) and _truthy(row.get("bruna_present"))):
                    continue
                dist = _number(row.get("distance_km")) or 0.0
                secs = _pace_to_seconds(row.get("avg_pace") or "")
                if dist < 5.0 or not secs:
                    continue
                cat = (row.get("category") or "").strip().lower()
                pse = _number(row.get("bruna_pse"))
                labelled_hard = cat in {"race", "quality", "threshold"} or _truthy(row.get("all_out_race"))
                # Auto-detect a strong effort, but a hard effort must FEEL hard:
                # require PSE>=7 corroboration and never accept an easy-category run.
                # This blocks a fast downhill/GPS-glitch easy day from tightening zones.
                auto = (
                    bool(base_zones)
                    and cat != "easy"
                    and pse is not None and pse >= 7
                    and classify_effort(secs, base_zones, int(pse)) in {"race", "threshold"}
                )
                if labelled_hard or auto:
                    cands.append(Benchmark(dist, int(secs * dist), "normal"))
        except Exception:
            pass
    return cands


def _load_benchmark_zones(repo_root: Path) -> dict[str, str]:
    """Calibrated PT-BR pace zones from the strongest recent effort (race or hard
    training run). Auto-tightens as fitness improves; never loosens on easy days."""
    from running_coach.pacing import select_best, zones_from_benchmark

    best = select_best(_benchmark_candidates(repo_root))
    return zones_from_benchmark(best) if best else {}


_DAY_KIND_TO_SESSION = {
    "Corrida leve": "easy",
    "Longo leve": "long_easy",
    "Longo progressivo": "long_progressive_finish",
    "Tempo (ritmo de meia)": "tempo_hmp",
    "Tiros em ritmo de meia": "hmp_intervals",
    "Tiros 5-10K": "intervals_5_10k",
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

_TODAY_ACTION_PT = {
    "maintain_next_workout": "Manter o treino planejado",
    "reduce_next_workout": "Reduzir o proximo treino",
    "replace_with_easy": "Trocar por corrida leve",
    "replace_with_off": "Folga / descanso",
    "replace_with_cross_training": "Trocar por treino alternativo",
    "defer_quality": "Adiar a qualidade; manter leve",
    "bruna_without_matheus": "Bruna treina sem o Matheus (Aquiles em alerta)",
    "request_manual_resolution": "Registrar check-in para liberar recomendacao",
}


def _today_directive(
    decisions: list[dict[str, str]], next_workouts: list[dict[str, Any]]
) -> dict[str, Any]:
    """Single PT-BR 'o que fazer hoje + por que', from the latest engine decision."""
    latest = _latest_rows(decisions, 1)
    decision = latest[0] if latest else {}
    action = decision.get("recommendation_action", "")
    next_cat = next_workouts[0]["intended_category"] if next_workouts else ""
    raw_reason = decision.get("reason") or ""
    why = _reason_to_ptbr(raw_reason)
    return {
        "headline": _TODAY_ACTION_PT.get(action, "Aguardando dados para recomendar"),
        "why": why,
        "next_planned": next_cat,
        "confidence": decision.get("confidence", ""),
        "science_refs": _as_list(decision.get("science_refs")),
        "date": decision.get("local_date") or decision.get("date", ""),
    }


def _reason_to_ptbr(reason: str) -> str:
    if not reason:
        return "Sem evidencia suficiente; registre o check-in."
    if "check-in" in reason.lower() or "checkin" in reason.lower():
        return "Falta o check-in manual do treino; registre para liberar a recomendacao."
    # Engine reason tags joined with '; ' -> PT-BR labels when known.
    parts = [p.strip() for p in reason.split(";") if p.strip()]
    labels = [_TODAY_REASON_PT.get(p, p) for p in parts]
    return "; ".join(labels)


_TODAY_REASON_PT = {
    "weekly_load_spike": "salto de carga semanal acima do seguro",
    "post_race_recovery": "janela de recuperacao pos-prova",
    "achilles_trend_rising": "Aquiles em tendencia de piora",
    "matheus_achilles_ge_5": "Aquiles do Matheus >= 5/10",
    "matheus_achilles_ge_3": "Aquiles do Matheus >= 3/10",
    "bruna_pse_ge_9": "PSE da Bruna muito alto",
    "bruna_strong_symptoms": "sintomas fortes da Bruna",
    "volleyball_previous_day": "volei no dia anterior",
    "poor_sleep": "sono ruim",
    "all_out_race": "esforco maximo recente",
    "red_flag_symptom": "sintoma de alerta",
    "within_guardrails": "dentro das margens de seguranca",
}



_WEEK_DAYS_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]

_CATEGORY_PT = {
    "easy_run": ("Corrida leve", "easy"),
    "long_run": ("Longo leve", "easy"),
    "long_progressive": ("Longo progressivo", "quality"),
    "tempo_hmp": ("Tempo (ritmo de meia)", "quality"),
    "hmp_intervals": ("Tiros em ritmo de meia", "quality"),
    "intervals_5_10k": ("Tiros 5-10K", "quality"),
    "diagnostic_race_10k": ("Prova diagnostica 10K", "quality"),
    "off": ("Descanso", "rest"),
}

# cycle.yaml baseline non-run days (Mon/Fri strength, Wed volleyball)
_DEFAULT_WEEKLY_PATTERN = {
    0: ("Forca (academia)", "support"),
    2: ("Volei", "support"),
    4: ("Forca (academia)", "support"),
}


def _date_obj(value: str):
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


_LABEL_TO_SESSION = {
    "Corrida leve": "EASY",
    "Longo leve": "LONG_EASY",
    "Longo progressivo": "LONG_PROGRESSIVE",
    "Tempo (ritmo de meia)": "TEMPO_HMP",
    "Tiros em ritmo de meia": "HMP_INTERVALS",
    "Tiros 5-10K": "INTERVALS_5_10K",
}


def _workout_for_label(label: str, zones: dict[str, str]) -> str:
    """Full PT-BR session structure (reps/distance/duration) for a week-day label."""
    if not zones:
        return ""
    name = _LABEL_TO_SESSION.get(label)
    if not name:
        return ""
    from running_coach.pacing import prescribe_workout
    from running_coach.periodization import SessionType
    return prescribe_workout(getattr(SessionType, name), zones)


def _pace_for_label(label: str, zones: dict[str, str]) -> str:
    if not zones:
        return ""
    zone = _DAY_KIND_TO_SESSION.get(label)
    if zone == "long_progressive_finish":
        fin = zones.get("long_progressive_finish", "")
        return f"leve, final em {fin}" if fin else ""
    return zones.get(zone, "") if zone else ""


def _week_view(plan_rows: list[dict[str, str]], reference_date: date, zones: dict[str, str] | None = None) -> dict[str, Any]:
    """7-day (Seg-Dom) week-ahead view in PT-BR from planned rows; honest empty state."""
    planned = [
        {"date": _date_obj(r.get("date", "")), "category": r.get("intended_category", "")}
        for r in plan_rows
        if r.get("planned_status") == "planned" and _date_obj(r.get("date", ""))
    ]
    monday = reference_date - timedelta(days=reference_date.weekday())
    week_end = monday + timedelta(days=6)
    has_future = any(p["date"] and monday <= p["date"] <= week_end for p in planned)

    # Priority so a real run beats an off/support row on the same date.
    _priority = {"quality": 0, "easy": 1, "rest": 2}

    days = []
    for i in range(7):
        d = monday + timedelta(days=i)
        matches = [p for p in planned if p["date"] == d]
        chosen = None
        for p in matches:
            label, kind = _CATEGORY_PT.get(
                p["category"], (p["category"].replace("_", " ").capitalize(), "easy")
            )
            if chosen is None or _priority.get(kind, 1) < _priority.get(chosen[1], 1):
                chosen = (label, kind)
        if chosen:
            label, kind = chosen
        elif i in _DEFAULT_WEEKLY_PATTERN:
            label, kind = _DEFAULT_WEEKLY_PATTERN[i]
        else:
            label, kind = "Descanso", "rest"
        days.append({"day": _WEEK_DAYS_PT[i], "date": d.isoformat(), "label": label, "kind": kind,
                     "pace": _pace_for_label(label, zones or {}),
                     "workout": _workout_for_label(label, zones or {})})

    return {
        "generated": has_future,
        "week_of": monday.isoformat(),
        "days": days,
        "empty_message": (
            ""
            if has_future
            else "Semana ainda não atualizada. Registre o último treino em Operar para gerar a semana."
        ),
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


def _progression_suggestion(workouts: list[dict[str, str]]) -> dict[str, Any]:
    """Advisory 'add a 4th easy day' nudge when readiness is sustained green.
    Never alters safety — purely additive coach voice."""
    from running_coach.accumulation import WorkoutHistoryPoint, build_athlete_state
    from running_coach.progression import suggest_fourth_day

    running = [w for w in workouts if (w.get("local_date") or w.get("date"))
               and (w.get("activity_type") or "").strip().casefold() == "corrida"]
    if not running:
        return {"should_suggest": False}
    # Sort chronologically so the streak reflects the LATEST evidence, not input order.
    running.sort(key=lambda w: w.get("local_date") or w.get("date") or "")

    # consecutive recent weeks with no Achilles flare and tolerable PSE. Suggesting
    # MORE training is conservative: a row missing PSE/Achilles evidence breaks the
    # streak (fail-closed — we never propose more on unknown readiness).
    green = 0
    for w in reversed(running[-8:]):
        ach_a = _number(w.get("matheus_achilles_after"))
        ach_m = _number(w.get("matheus_achilles_morning"))
        pse = _number(w.get("bruna_pse"))
        if ach_a is None and ach_m is None and pse is None:
            break  # no readiness evidence -> cannot count this as a proven-green week
        ach = max(ach_a or 0, ach_m or 0)
        if ach <= 2 and (pse or 0) <= 7:
            green += 1
        else:
            break

    points = []
    for w in running:
        d = w.get("local_date") or w.get("date")
        try:
            points.append(WorkoutHistoryPoint(
                date.fromisoformat(d), _number(w.get("distance_km")) or 0.0, True,
                int(_number(w.get("bruna_pse")) or 0),
                int(_number(w.get("matheus_achilles_morning")) or 0),
                int(_number(w.get("matheus_achilles_after")) or 0), False, False))
        except (ValueError, TypeError):
            continue
    if not points:
        return {"should_suggest": False}

    # approximate current weekly frequency from the last 7 days
    last = max(p.local_date for p in points)
    runs_per_week = sum(1 for p in points if (last - p.local_date).days < 7)
    state = build_athlete_state(points, last + timedelta(days=1))
    s = suggest_fourth_day(state, runs_per_week, green)
    return {"should_suggest": s.should_suggest, "message": s.message,
            "science_refs": list(s.science_refs)}


def _readiness(workouts: list[dict[str, str]]) -> dict[str, Any]:
    """Deterministic PT-BR readiness read from the most recent evidence."""
    recent = [w for w in workouts if (w.get("local_date") or w.get("date"))][-5:]
    if not recent:
        return {"level": "indefinido", "message": "Sem dados recentes para avaliar prontidão."}
    last = recent[-1]
    ach_after = _number(last.get("matheus_achilles_after"))
    ach_morning = _number(last.get("matheus_achilles_morning"))
    pse_val = _number(last.get("bruna_pse"))
    symptoms = (last.get("bruna_symptoms") or "").strip()
    # No readiness evidence at all -> unknown, not "good" (fail-closed honesty).
    if ach_after is None and ach_morning is None and pse_val is None and not symptoms:
        return {"level": "indefinido", "message": "Sem evidência de prontidão no último registro."}
    ach = max(ach_after or 0, ach_morning or 0)
    pse = pse_val or 0
    if ach >= 5 or pse >= 9:
        return {"level": "recuperar",
                "message": "Sinais de fadiga/dor altos: priorize recuperação antes de qualquer qualidade."}
    if ach >= 3 or pse >= 8 or symptoms:
        return {"level": "cautela",
                "message": "Prontidão parcial: mantenha leve e observe a resposta antes de subir a carga."}
    return {"level": "boa", "message": "Prontidão boa: pode seguir o plano na intensidade prevista."}


def _week_narrative(summary: list[dict[str, Any]]) -> str:
    """Coach's plain PT-BR recap of the most recent completed week."""
    if not summary:
        return ""
    w = summary[-1]
    runs = int(_number(w.get("runs")) or 0)
    km = round(_number(w.get("distance_km")) or 0.0, 1)
    quality = int(_number(w.get("quality_runs")) or 0)
    shared = int(_number(w.get("shared_runs")) or 0)
    if runs == 0:
        return "Semana sem corridas registradas."
    parts = [f"Semana: {runs} corrida(s), {km} km no total"]
    parts.append(f"{quality} de qualidade" if quality else "sem sessão de qualidade")
    if shared:
        parts.append(f"{shared} com a Bruna")
    consist = "consistência boa" if runs >= 3 else "volume baixo, priorize regularidade"
    parts.append(consist)
    return ", ".join(parts) + "."


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
                "workout_id": row.get("workout_id", ""),
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


def _present_llm_recommendation(
    recommendation: dict[str, Any],
    source_path: Path | None = None,
    repo_root: Path | None = None,
    fallback_generated_at: str = "",
) -> dict[str, Any] | None:
    if not recommendation:
        return None
    source_modified_at = _source_modified_at(source_path)
    generated_at = recommendation.get("generated_at") or source_modified_at or fallback_generated_at
    timestamp_source = "payload_generated_at"
    if not recommendation.get("generated_at") and source_modified_at:
        timestamp_source = "source_modified_at"
    elif not recommendation.get("generated_at"):
        timestamp_source = "fallback_generated_at"
    return {
        "recommendation_id": recommendation.get("recommendation_id", ""),
        "generated_at": generated_at,
        "timestamp_source": timestamp_source,
        "source_path": _relative_source_path(source_path, repo_root),
        "source_modified_at": source_modified_at,
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


def _recommendation_history(
    llm_dir: Path,
    repo_root: Path,
    latest_recommendation: dict[str, Any] | None,
    fallback_generated_at: str,
) -> list[dict[str, Any]]:
    history = []
    if llm_dir.exists():
        for path in sorted(llm_dir.glob("*.json")):
            recommendation = _read_json(path)
            if not recommendation.get("recommendation_id"):
                continue
            presented = _present_llm_recommendation(
                recommendation,
                path,
                repo_root,
                fallback_generated_at,
            )
            if presented:
                history.append(presented)

    if latest_recommendation and latest_recommendation not in history:
        history.append(latest_recommendation)

    return sorted(
        history,
        key=lambda item: (item.get("generated_at", ""), item.get("source_path", "")),
        reverse=True,
    )


def _source_modified_at(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _relative_source_path(path: Path | None, repo_root: Path | None) -> str:
    if path is None:
        return ""
    if repo_root is None:
        return path.as_posix()
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


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


def _risk_summary(risk_level: str, risk_trend: list[dict[str, Any]]) -> dict[str, Any]:
    source = next((item for item in reversed(risk_trend) if item.get("reasons")), risk_trend[-1] if risk_trend else {})
    drivers = [
        _risk_driver(code, source)
        for code in source.get("reasons", [])
    ]
    return {
        "level": risk_level,
        "latest_score": source.get("score", 1),
        "source": "trends.risk",
        "source_date": source.get("date", ""),
        "source_workout_id": source.get("workout_id", ""),
        "drivers": drivers,
    }


def _risk_driver(code: str, source: dict[str, Any]) -> dict[str, str]:
    labels = {
        "volleyball_previous_day": "Vôlei no dia anterior aumenta carga neuromuscular; evitar trabalho máximo.",
        "bruna_high_pse": "PSE da Bruna em 9/10 ou mais exige redução da próxima sessão.",
        "achilles_above_3": "Aquiles do Matheus acima de 3/10 remove velocidade, subidas e descidas.",
        "sleep_risk": "Sono ruim aumenta risco de fadiga; reduzir volume ou intensidade.",
    }
    return {
        "code": code,
        "label": labels.get(code, code.replace("_", " ")),
        "source_date": source.get("date", ""),
        "source_workout_id": source.get("workout_id", ""),
    }


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
        num = float(value)
        if num != num or num in (float("inf"), float("-inf")):
            return None
        return round(num, 2)
    except ValueError:
        return None


def _pace_to_seconds(value: str | None) -> int | None:
    if not value or ":" not in value:
        return None
    minutes, seconds = value.split(":", 1)
    try:
        m, s = int(minutes), int(seconds)
    except ValueError:
        return None
    if m < 0 or not (0 <= s < 60):
        return None
    total = m * 60 + s
    # Plausibility guard: ignore sprints/walks that would distort training bands.
    return total if 180 <= total <= 900 else None
