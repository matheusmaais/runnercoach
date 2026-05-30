"""Change explainability (#7): every recommendation that changes the plan carries
a deterministic, auditable explanation IN PT-BR for the frontend — what changed,
based on which source/study, why, and the micro (next session) + macro (January
half) objective. Facts come from the engine; the text is deterministic so there
is never a silent change, even when the LLM is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from running_coach.recommendations import RecommendationResult

# PT-BR labels for reason tags shown to the athlete.
_REASON_PT: dict[str, str] = {
    "red_flag_symptom": "sintoma de alerta (red flag)",
    "bruna_pse_ge_9": "PSE da Bruna muito alto (>= 9)",
    "bruna_strong_symptoms": "sintomas fortes da Bruna",
    "matheus_achilles_ge_5": "Aquiles do Matheus >= 5/10",
    "matheus_achilles_ge_3": "Aquiles do Matheus >= 3/10",
    "achilles_trend_rising": "Aquiles do Matheus em tendencia de piora",
    "weekly_load_spike": "salto de carga semanal acima do seguro",
    "post_race_recovery": "janela de recuperacao pos-prova",
    "volleyball_previous_day": "volei no dia anterior (carga neuromuscular)",
    "poor_sleep": "sono ruim",
    "all_out_race": "esforco maximo / prova recente",
    "within_guardrails": "dentro das margens de seguranca",
    "missing_checkin": "check-in manual ausente",
}

# Source (study/rule) shown per reason, with DOI/title pulled by the FE from the
# science registry. Here we record the ref id the engine actually used.
_REASON_PT_WHY: dict[str, str] = {
    "weekly_load_spike": (
        "Sua carga dos ultimos 7 dias subiu rapido demais frente as semanas "
        "anteriores; adicionar estimulo agora aumenta risco sem ganho proporcional."
    ),
    "post_race_recovery": (
        "Voce esta na janela de recuperacao apos um esforco forte; priorizar "
        "recuperacao protege as proximas semanas de treino."
    ),
    "achilles_trend_rising": (
        "O Aquiles vem incomodando em sessoes recentes; reduzir velocidade/qualidade "
        "agora evita virar lesao."
    ),
    "matheus_achilles_ge_5": (
        "Aquiles do Matheus alto: ele nao deve puxar ritmo; a Bruna pode treinar sem ele."
    ),
    "matheus_achilles_ge_3": "Aquiles do Matheus elevado: remover velocidade e descidas.",
    "bruna_pse_ge_9": "Esforco percebido muito alto pede sessao leve ou folga.",
    "bruna_strong_symptoms": "Sintomas fortes pedem reducao de intensidade.",
    "volleyball_previous_day": "Volei no dia anterior conta como carga; evitar trabalho maximo.",
    "poor_sleep": "Sono ruim reduz a prontidao; reduzir volume ou intensidade.",
    "all_out_race": "Apos esforco maximo, tratar os proximos dias como recuperacao.",
    "red_flag_symptom": "Sinal de alerta: parar de buscar performance e priorizar saude.",
}

_DECISION_PT: dict[str, str] = {
    "maintain": "manter o treino planejado",
    "reduce": "reduzir o proximo treino",
    "alter": "alterar o treino",
    "defer": "adiar a qualidade",
    "recover": "priorizar recuperacao",
    "hold_phase": "segurar a fase atual",
    "advance_phase": "avancar de fase",
    "race_strategy": "estrategia de prova",
}


@dataclass(frozen=True)
class ChangeExplanation:
    changed: bool
    what_changed: str          # PT-BR
    triggers: list[str]        # PT-BR reason labels
    sources: list[str]         # science_ref_id / rule ids (EN, FE resolves to PT title+DOI)
    why: str                   # PT-BR
    micro_objective: str       # PT-BR — gain for the next session
    macro_objective: str       # PT-BR — gain for the January half
    what_to_do_different: str = ""  # PT-BR — actionable coach advice
    confidence: str = ""
    missing_evidence: list[str] = field(default_factory=list)


_MACRO = (
    "Proteger a progressao rumo a meia forte de janeiro: consistencia vale mais "
    "que heroismo, e treino perdido nao se compensa com volume extra."
)


_DIFFERENT_PT: dict[str, str] = {
    "weekly_load_spike": "Segure o volume nesta semana; só volte a subir quando a carga estabilizar.",
    "post_race_recovery": "Priorize recuperação 2-4 dias; nada de qualidade antes de sentir as pernas leves.",
    "achilles_trend_rising": "Tire velocidade/descidas e monitore a dor 24h; se piorar, é folga.",
    "matheus_achilles_ge_5": "Matheus não puxa ritmo; Bruna treina sozinha se necessário.",
    "matheus_achilles_ge_3": "Sem tiros nem descidas; mantenha leve e observe o tendão.",
    "bruna_pse_ge_9": "Próxima sessão leve ou off; o corpo pediu recuperação.",
    "bruna_strong_symptoms": "Reduza intensidade e registre os sintomas; não force.",
    "volleyball_previous_day": "Evite trabalho máximo no dia seguinte ao vôlei.",
    "lower_body_load_previous_day": "Pernas pesadas da academia: mantenha o treino leve.",
    "poor_sleep": "Sono ruim: corte volume ou intensidade hoje.",
    "all_out_race": "Trate os próximos dias como recuperação; não compense com volume.",
    "workout_truncated": "Treino encurtou: investigue o motivo antes de retomar a carga cheia.",
    "overpaced": "Você correu mais rápido que o alvo; segure o ritmo pra não acumular fadiga.",
    "underpaced": "Ritmo bem abaixo do alvo pode ser fadiga; uma sessão leve ajuda a recuperar.",
    "red_flag_symptom": "Pare de buscar performance; procure avaliação se persistir.",
}


def explain_change(
    result: RecommendationResult, planned_action: str
) -> ChangeExplanation:
    """Build the PT-BR explanation. No silent change: when the action differs
    from the plan, an explanation with triggers + sources is always produced."""
    changed = result.action.value != planned_action
    reason_tags = [r for r in result.reasons if r != "within_guardrails"]
    triggers = [_REASON_PT.get(r, r) for r in reason_tags]

    if not changed and not reason_tags:
        what = "Treino mantido conforme o plano."
        why = "Estado dentro das margens de seguranca; sem motivo para alterar."
        micro = "Executar a sessao planejada na intensidade prevista."
        different = "Siga o plano; está tudo dentro das margens."
    else:
        what = f"Decisao: {_DECISION_PT.get(result.decision.value, result.decision.value)}."
        primary = reason_tags[0] if reason_tags else "within_guardrails"
        why = _REASON_PT_WHY.get(primary, "Ajuste por seguranca com base na evidencia atual.")
        micro = "Absorver a carga e chegar inteiro a proxima sessao de qualidade."
        different = _DIFFERENT_PT.get(primary, "Ajuste conservador; reavalie no próximo check-in.")

    return ChangeExplanation(
        changed=changed,
        what_changed=what,
        triggers=triggers,
        sources=list(result.science_refs),
        why=why,
        micro_objective=micro,
        macro_objective=_MACRO,
        what_to_do_different=different,
        confidence=result.confidence.value,
        missing_evidence=list(result.missing_evidence),
    )
