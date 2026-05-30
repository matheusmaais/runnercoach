from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from running_coach.csv_utils import decode_json_cell
from running_coach.models import Confidence, DecisionType, RecommendationAction, SymptomSeverity
from running_coach.recommendations import RecommendationInput, recommend_next_action
from running_coach.science import load_science_refs


REQUIRED_RESPONSE_FIELDS = {
    "schema_version",
    "recommendation_id",
    "next_workout_action",
    "decision_type",
    "confidence",
    "summary",
    "what_workout_showed",
    "risk_assessment",
    "next_workout",
    "science_refs",
    "evidence_used",
    "missing_evidence",
    "athlete_scope",
}


class LlmResponseValidationError(ValueError):
    pass


class LlmRecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(ge=1, le=1)
    recommendation_id: str = Field(min_length=1)
    next_workout_action: RecommendationAction
    decision_type: DecisionType
    confidence: Confidence
    summary: str = Field(min_length=1)
    what_workout_showed: str = Field(min_length=1)
    risk_assessment: str = Field(min_length=1)
    next_workout: str = Field(min_length=1)
    science_refs: list[str] = Field(min_length=1)
    evidence_used: list[str] = Field(min_length=1)
    missing_evidence: list[str] = Field(default_factory=list)
    athlete_scope: str = Field(pattern="^(shared_run|bruna|matheus|both)$")


def build_llm_request(repo_root: Path | str) -> dict[str, Any]:
    repo_root = Path(repo_root)
    workouts = _read_csv(repo_root / "data/processed/workouts.csv")
    decisions = _read_csv(repo_root / "data/processed/decisions.csv")
    plan_status = _read_csv(repo_root / "data/processed/plan_status.csv")
    science_refs = load_science_refs(repo_root / "data/knowledge/science_refs.yaml")

    latest_shared = _latest(
        row for row in workouts if _is_shared_workout_with_checkin(row)
    )
    latest_matheus_solo = _latest(
        row for row in workouts if row.get("athlete_context") == "matheus_garmin_only"
    )

    request = {
        "schema_version": 1,
        "generated_at": _deterministic_generated_at(
            latest_shared, latest_matheus_solo, workouts
        ),
        "athletes": {
            "matheus": "39, pacer priority, Achilles risk is strategic limiter.",
            "bruna": "32, strong sports background, evaluated by shared pace plus manual PSE/symptoms/recovery/HR when provided.",
        },
        "data_contract": (
            "Garmin physiology is Matheus-only. Shared pace/distance/time can be "
            "used for Bruna only when shared_run=true and bruna_present=true."
        ),
        "forbidden_claims": [
            "Do not use Matheus solo pace as Bruna evolution",
            "Do not infer Bruna heart rate from Garmin heart rate",
            "Do not prescribe all-out speed when evidence is missing",
            "Do not cite science outside approved_science_refs",
            "Do not diagnose injury or medical conditions",
        ],
        "current_state": _read_text(repo_root / "docs/state.md"),
        "latest_shared_workout": _llm_workout(latest_shared, bruna_evidence="available")
        if latest_shared
        else {},
        "latest_matheus_solo": _llm_workout(
            latest_matheus_solo, bruna_evidence="not_applicable"
        )
        if latest_matheus_solo
        else {},
        "recent_decisions": decisions[:5],
        "next_planned_workouts": [
            row for row in plan_status if row.get("derived_status") == "planned"
        ][:3],
        "approved_science_refs": sorted(
            science_ref_id
            for science_ref_id, science_ref in science_refs.items()
            if science_ref.approved
        ),
        "required_response_schema": {
            field: _schema_hint(field) for field in sorted(REQUIRED_RESPONSE_FIELDS)
        },
    }
    request["deterministic_guardrail"] = _deterministic_guardrail_for_request(request)
    return request


def render_llm_request_markdown(request: dict[str, Any]) -> str:
    lines = [
        "# Running Coach LLM Recommendation Request",
        "",
        "## Data Contract",
        "",
        request["data_contract"],
        "",
        "## Forbidden Claims",
        "",
    ]
    lines.extend(f"- {claim}" for claim in request["forbidden_claims"])
    lines.extend(
        [
            "",
            "## Current State",
            "",
            request.get("current_state") or "No state document available.",
            "",
            "## Latest Shared Workout",
            "",
            "```json",
            json.dumps(request.get("latest_shared_workout", {}), ensure_ascii=False, indent=2),
            "```",
            "",
            "## Latest Matheus Solo Workout",
            "",
            "```json",
            json.dumps(request.get("latest_matheus_solo", {}), ensure_ascii=False, indent=2),
            "```",
            "",
            "## Next Planned Workouts",
            "",
            "```json",
            json.dumps(request.get("next_planned_workouts", []), ensure_ascii=False, indent=2),
            "```",
            "",
            "## Deterministic Guardrail",
            "",
            "```json",
            json.dumps(request.get("deterministic_guardrail", {}), ensure_ascii=False, indent=2),
            "```",
            "",
            "## Approved Science Refs",
            "",
        ]
    )
    lines.extend(f"- `{science_ref}`" for science_ref in request["approved_science_refs"])
    lines.extend(
        [
            "",
            "## Required Response Schema",
            "",
            "Return only JSON with these fields:",
            "",
            "```json",
            json.dumps(request["required_response_schema"], ensure_ascii=False, indent=2),
            "```",
            "",
            "Allowed next_workout_action values include:",
            "",
        ]
    )
    lines.extend(f"- `{action.value}`" for action in RecommendationAction)
    return "\n".join(lines).rstrip() + "\n"


def write_llm_request(repo_root: Path | str, output_dir: Path | str) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    request = build_llm_request(repo_root)
    json_path = output_dir / "latest-request.json"
    markdown_path = output_dir / "latest-request.md"
    json_path.write_text(
        json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(render_llm_request_markdown(request), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}


def _prose_fields(response: dict[str, Any]) -> list[str]:
    return [
        str(response.get(key, ""))
        for key in ("summary", "what_workout_showed", "risk_assessment", "next_workout")
    ]


# Anti-hallucination prose lint. Prose is shown to the user in PT-BR and must
# NOT cite studies/authors/orgs/DOIs/URLs directly; science is referenced only
# via science_refs. We require a CITATION CUE (not a bare year), so legitimate
# calendar/pace prose ("Em 2027 voce corre a meia", "5:30/km") is allowed.
_CITATION_CUES = (
    r"segundo|conforme|de acordo com|recomenda|sugere|consenso|"
    r"meta[\s-]?analise|estudo de|artigo|revisao|publicacao|"
    r"according to|recommends|suggests|consensus|study|meta[\s-]?analysis|et al|"
    r"based on|per "
)
_PUBLICATION_NOUN = r"estudo|artigo|revisao|meta[\s-]?analise|consenso|publicacao|study|meta[\s-]?analysis|consensus"

_CITATION_PATTERNS = [
    re.compile(r"\bet al\.?", re.IGNORECASE),
    re.compile(r"\b10\.\d{4,9}/\S+"),                 # DOI
    re.compile(r"\bdoi:\s*\S+", re.IGNORECASE),       # doi: ...
    re.compile(r"https?://|\bwww\.\S+", re.IGNORECASE),  # URL / bare domain
    # citation cue followed (within a few words) by a Capitalized name or ACRONYM
    re.compile(rf"(?:{_CITATION_CUES})\b[^.]{{0,40}}?\b([A-Z][a-zA-Z]+|[A-Z]{{2,}})", re.IGNORECASE),
    # publication noun + "de <ProperName>" (e.g. "meta-analise de Bosquet")
    re.compile(rf"(?:{_PUBLICATION_NOUN})\b[^.]{{0,20}}?\bde\s+[A-Z][a-zA-Z]+"),
    # "<ProperName> et al" / "<ProperName> & <ProperName>" / "<ProperName> e colegas"
    re.compile(r"\b[A-Z][a-zA-Z]+\s*(?:&|\be colegas\b)\s*[A-Z]?[a-zA-Z]*"),
    # "<ProperName> YYYY" adjacent to a publication noun (e.g. "Smith 2024 meta-analysis")
    re.compile(rf"\b[A-Z][a-zA-Z]+\s+\d{{4}}\b[^.]{{0,20}}?(?:{_PUBLICATION_NOUN})", re.IGNORECASE),
    re.compile(rf"(?:{_PUBLICATION_NOUN})[^.]{{0,20}}?\b[A-Z][a-zA-Z]+\s+\d{{4}}\b", re.IGNORECASE),
    # "<ProperName> YYYY" only when an author cue word is present nearby handled above;
    # keep explicit "(YYYY)" parenthetical citation form
    re.compile(r"\([^)]*\b\d{4}\b[^)]*\)"),
]


def _lint_prose_citations(response: dict[str, Any]) -> None:
    for text in _prose_fields(response):
        for pat in _CITATION_PATTERNS:
            if pat.search(text):
                raise LlmResponseValidationError(
                    "prose must not cite studies/authors/DOIs directly; "
                    "reference science only via science_refs"
                )
    _lint_prose_language(response)


# Frontend prose must be PT-BR. Reject obvious English leakage via common English
# function words that do not occur in Portuguese.
_ENGLISH_MARKERS = re.compile(
    r"\b(the|workout|keep|because|should|next|with|your|training|easy|"
    r"risk|maintain|reduce|recovery|week|run)\b",
    re.IGNORECASE,
)


def _lint_prose_language(response: dict[str, Any]) -> None:
    for text in _prose_fields(response):
        if len(_ENGLISH_MARKERS.findall(text)) >= 2:
            raise LlmResponseValidationError(
                "prose must be in Portuguese (PT-BR); detected English text"
            )


def validate_llm_response(
    response: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    unknown = sorted(set(response) - REQUIRED_RESPONSE_FIELDS)
    if unknown:
        raise LlmResponseValidationError(f"unknown fields: {unknown}")
    missing = sorted(REQUIRED_RESPONSE_FIELDS - set(response))
    if missing:
        raise LlmResponseValidationError(f"missing fields: {missing}")

    try:
        parsed = LlmRecommendationResponse.model_validate(response)
    except ValidationError as exc:
        raise LlmResponseValidationError(str(exc)) from exc

    _lint_prose_citations(response)

    approved_refs = set(request.get("approved_science_refs", []))
    unapproved_refs = sorted(set(parsed.science_refs) - approved_refs)
    if unapproved_refs:
        raise LlmResponseValidationError(f"unapproved science_refs: {unapproved_refs}")

    solo_workout_id = _workout_id(request.get("latest_matheus_solo", {}))
    if parsed.athlete_scope == "bruna" and solo_workout_id in parsed.evidence_used:
        raise LlmResponseValidationError(
            "Matheus solo workout cannot be used as Bruna evidence"
        )

    known_evidence_ids = _known_evidence_ids(request)
    unknown_evidence = sorted(set(parsed.evidence_used) - known_evidence_ids)
    if known_evidence_ids and unknown_evidence:
        raise LlmResponseValidationError(f"unknown evidence_used ids: {unknown_evidence}")

    guardrail = _deterministic_guardrail_for_request(request)
    guardrail_action = RecommendationAction(guardrail["action"])
    if not _action_allowed_by_guardrail(parsed.next_workout_action, guardrail_action):
        raise LlmResponseValidationError(
            "deterministic guardrail forbids action "
            f"{parsed.next_workout_action.value}; required envelope is "
            f"{guardrail_action.value}"
        )
    required_missing = set(guardrail.get("missing_evidence", []))
    omitted_missing = sorted(required_missing - set(parsed.missing_evidence))
    if omitted_missing:
        raise LlmResponseValidationError(
            f"missing evidence omitted from response: {omitted_missing}"
        )

    return parsed.model_dump(mode="json")


def render_validated_recommendation(response: dict[str, Any]) -> str:
    return (
        "# LLM Running Coach Recommendation\n\n"
        f"- Recommendation ID: {response['recommendation_id']}\n"
        f"- Action: {response['next_workout_action']}\n"
        f"- Decision type: {response['decision_type']}\n"
        f"- Confidence: {response['confidence']}\n"
        f"- Science refs: {', '.join(response['science_refs'])}\n\n"
        "## Summary\n\n"
        f"{response['summary']}\n\n"
        "## What The Workout Showed\n\n"
        f"{response['what_workout_showed']}\n\n"
        "## Risk Assessment\n\n"
        f"{response['risk_assessment']}\n\n"
        "## Next Workout\n\n"
        f"{response['next_workout']}\n"
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _latest(rows: Any) -> dict[str, str]:
    return max(
        list(rows),
        key=lambda row: row.get("local_datetime") or row.get("local_date") or "",
        default={},
    )


def _is_shared_workout_with_checkin(row: dict[str, str]) -> bool:
    missing = decode_json_cell(row.get("missing_evidence"))
    return (
        row.get("athlete_context") == "shared_run_with_manual_checkin"
        and row.get("shared_run") == "true"
        and row.get("bruna_present") == "true"
        and "checkin" not in missing
    )


def _llm_workout(row: dict[str, str], bruna_evidence: str) -> dict[str, Any]:
    keys = [
        "workout_id",
        "activity_id",
        "local_date",
        "local_datetime",
        "athlete_context",
        "participants",
        "shared_run",
        "bruna_present",
        "distance_km",
        "avg_pace",
        "bruna_pse",
        "bruna_symptoms",
        "matheus_achilles_after",
        "volleyball_previous_day",
        "sleep_quality",
        "category",
        "symptom_severity",
        "matheus_achilles_morning",
        "missing_evidence",
    ]
    payload = {key: row.get(key, "") for key in keys}
    payload["participants"] = decode_json_cell(payload.get("participants"))
    payload["bruna_symptoms"] = decode_json_cell(payload.get("bruna_symptoms"))
    payload["missing_evidence"] = decode_json_cell(payload.get("missing_evidence"))
    payload["bruna_evidence"] = bruna_evidence
    return payload


def _workout_id(payload: dict[str, Any]) -> str:
    return str(payload.get("workout_id") or "")


def _known_evidence_ids(request: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for section in ("latest_shared_workout", "latest_matheus_solo"):
        payload = request.get(section, {})
        if isinstance(payload, dict):
            ids.update(
                str(payload.get(key))
                for key in ("workout_id", "activity_id")
                if payload.get(key)
            )
    for planned in request.get("next_planned_workouts", []):
        if isinstance(planned, dict) and planned.get("planned_workout_id"):
            ids.add(str(planned["planned_workout_id"]))
    for decision in request.get("recent_decisions", []):
        if isinstance(decision, dict):
            ids.update(
                str(decision.get(key))
                for key in ("decision_id", "workout_id", "activity_id", "related_workout_id")
                if decision.get(key)
            )
    return ids


def _deterministic_guardrail_for_request(request: dict[str, Any]) -> dict[str, Any]:
    workout = request.get("latest_shared_workout", {})
    if not isinstance(workout, dict) or not workout:
        return {
            "action": RecommendationAction.REQUEST_MANUAL_RESOLUTION.value,
            "decision": DecisionType.DEFER.value,
            "confidence": Confidence.LOW.value,
            "reasons": ["missing_shared_workout"],
            "science_refs": [],
            "rule_refs": [],
            "missing_evidence": ["latest_shared_workout"],
            "planned_workout_id": "unplanned-next-workout",
        }

    planned = _first_planned_workout(request)
    result = recommend_next_action(
        RecommendationInput(
            bruna_pse=_optional_int(workout.get("bruna_pse")),
            symptom_severity=_symptom_severity(workout.get("symptom_severity")),
            matheus_achilles_morning=_optional_int(
                workout.get("matheus_achilles_morning")
            )
            or 0,
            matheus_achilles_after=_optional_int(workout.get("matheus_achilles_after"))
            or 0,
            volleyball_previous_day=_bool_value(workout.get("volleyball_previous_day")),
            poor_sleep=_is_poor_sleep(workout.get("sleep_quality")),
            all_out_race=_is_all_out_race(workout),
            planned_action=RecommendationAction.MAINTAIN_NEXT_WORKOUT,
            phase=str(planned.get("phase") or "unknown"),
            week_number=_optional_int(planned.get("week_number")) or 1,
            planned_workout_id=str(
                planned.get("planned_workout_id") or "unplanned-next-workout"
            ),
        )
    )
    return result.model_dump(mode="json")


def _first_planned_workout(request: dict[str, Any]) -> dict[str, Any]:
    planned = request.get("next_planned_workouts", [])
    if isinstance(planned, list) and planned and isinstance(planned[0], dict):
        return planned[0]
    return {}


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


def _is_poor_sleep(value: Any) -> bool:
    if not value:
        return False
    return str(value).strip().lower() in {"poor", "bad", "ruim", "pessima", "péssima"}


def _is_all_out_race(workout: dict[str, Any]) -> bool:
    haystack = " ".join(
        str(workout.get(key) or "").lower() for key in ("category", "next_workout")
    )
    return any(
        token in haystack
        for token in ("all_out", "all-out", "maximo", "máximo", "race")
    )


def _symptom_severity(value: Any) -> SymptomSeverity:
    if not value:
        return SymptomSeverity.NONE
    return SymptomSeverity(str(value))


def _action_allowed_by_guardrail(
    llm_action: RecommendationAction, guardrail_action: RecommendationAction
) -> bool:
    allowed = {
        RecommendationAction.MAINTAIN_NEXT_WORKOUT: set(RecommendationAction),
        RecommendationAction.REDUCE_NEXT_WORKOUT: {
            RecommendationAction.REDUCE_NEXT_WORKOUT,
            RecommendationAction.REPLACE_WITH_EASY,
            RecommendationAction.REPLACE_WITH_OFF,
            RecommendationAction.DEFER_QUALITY,
        },
        RecommendationAction.REPLACE_WITH_EASY: {
            RecommendationAction.REPLACE_WITH_EASY,
            RecommendationAction.REPLACE_WITH_OFF,
        },
        RecommendationAction.REPLACE_WITH_OFF: {
            RecommendationAction.REPLACE_WITH_OFF,
        },
        RecommendationAction.REPLACE_WITH_CROSS_TRAINING: {
            RecommendationAction.REPLACE_WITH_CROSS_TRAINING,
            RecommendationAction.REPLACE_WITH_OFF,
        },
        RecommendationAction.DEFER_QUALITY: {
            RecommendationAction.DEFER_QUALITY,
            RecommendationAction.REDUCE_NEXT_WORKOUT,
            RecommendationAction.REPLACE_WITH_EASY,
            RecommendationAction.REPLACE_WITH_OFF,
        },
        RecommendationAction.BRUNA_WITHOUT_MATHEUS: {
            RecommendationAction.BRUNA_WITHOUT_MATHEUS,
            RecommendationAction.REPLACE_WITH_CROSS_TRAINING,
            RecommendationAction.REPLACE_WITH_OFF,
        },
        RecommendationAction.REQUEST_MANUAL_RESOLUTION: {
            RecommendationAction.REQUEST_MANUAL_RESOLUTION,
        },
    }
    return llm_action in allowed[guardrail_action]


def _deterministic_generated_at(
    latest_shared: dict[str, str],
    latest_matheus_solo: dict[str, str],
    workouts: list[dict[str, str]],
) -> str:
    candidates = [
        latest_shared.get("local_datetime", ""),
        latest_matheus_solo.get("local_datetime", ""),
        *(row.get("local_datetime", "") for row in workouts),
    ]
    return max(candidate for candidate in candidates if candidate) if candidates else "unknown"


def _schema_hint(field: str) -> str:
    hints = {
        "schema_version": "integer, must be 1",
        "recommendation_id": "stable string id",
        "next_workout_action": "RecommendationAction enum value",
        "decision_type": "DecisionType enum value",
        "confidence": "high|medium|low",
        "summary": "short coaching summary",
        "what_workout_showed": "evidence-based interpretation",
        "risk_assessment": "risk and fatigue assessment",
        "next_workout": "specific next workout recommendation",
        "science_refs": "approved science_ref_id list",
        "evidence_used": "workout_id or document ids used",
        "missing_evidence": "missing evidence list",
        "athlete_scope": "shared_run|bruna|matheus|both",
    }
    return hints[field]
