import pytest

from running_coach.models import RecommendationAction, SymptomSeverity
from running_coach.pipeline import _classify_symptom_severity
from running_coach.recommendations import RecommendationInput, recommend_next_action


def _input(severity: SymptomSeverity) -> RecommendationInput:
    return RecommendationInput(
        bruna_pse=6,
        symptom_severity=severity,
        matheus_achilles_morning=0,
        matheus_achilles_after=0,
        volleyball_previous_day=False,
        poor_sleep=False,
        all_out_race=False,
        planned_action=RecommendationAction.MAINTAIN_NEXT_WORKOUT,
        phase="ten_k_polish",
        week_number=1,
        planned_workout_id="plan-1",
    )


# Injury-bearing / acute phrases (incl. accent + ASCII variants) must be RED_FLAG.
RED_FLAG_PHRASES = [
    "dor aguda no tendao",
    "dor aguda no tendão",
    "dor pontual no aquiles com dor aguda",
    "mancando",
    "nao consegue apoiar",
    "não consegue apoiar",
    "estalo no joelho",
    "dormencia no pe",
    "formigamento na perna",
    "torceu o tornozelo",
    "dor no peito",
    "tontura",
]

# Non-benign but unrecognized text must fail closed to at least MODERATE.
UNKNOWN_NONBENIGN = [
    "cansaco nas pernas",
    "desconforto no joelho",
    "rigidez lombar",
    "queimacao na canela",
    "incomodo no quadril",
    "pernas pesadas",
]

BENIGN = ["", "sem sintomas", "none", "no symptoms", "assintomatica", "nenhum", "n/a"]


@pytest.mark.parametrize("phrase", RED_FLAG_PHRASES)
def test_acute_injury_phrases_are_red_flag(phrase):
    assert _classify_symptom_severity([phrase]) == SymptomSeverity.RED_FLAG


@pytest.mark.parametrize("phrase", UNKNOWN_NONBENIGN)
def test_unknown_nonbenign_fails_closed_to_at_least_moderate(phrase):
    severity = _classify_symptom_severity([phrase])
    assert severity in {SymptomSeverity.MODERATE, SymptomSeverity.RED_FLAG}
    # And the engine must NOT maintain on such a symptom.
    assert recommend_next_action(_input(severity)).action != RecommendationAction.MAINTAIN_NEXT_WORKOUT


@pytest.mark.parametrize("phrase", BENIGN)
def test_benign_stays_none(phrase):
    assert _classify_symptom_severity([phrase]) == SymptomSeverity.NONE


def test_empty_list_is_none():
    assert _classify_symptom_severity([]) == SymptomSeverity.NONE


def test_no_unknown_symptom_yields_maintain():
    for phrase in RED_FLAG_PHRASES + UNKNOWN_NONBENIGN:
        severity = _classify_symptom_severity([phrase])
        action = recommend_next_action(_input(severity)).action
        assert action != RecommendationAction.MAINTAIN_NEXT_WORKOUT, phrase


# --- Codex adversarial review regressions ---

@pytest.mark.parametrize("phrase", ["manca", "estou manca", "dor ao mancar", "mancou ontem"])
def test_limp_variants_are_red_flag(phrase):
    assert _classify_symptom_severity([phrase]) == SymptomSeverity.RED_FLAG


@pytest.mark.parametrize("phrase", ["sem dor no peito", "sem tontura", "sem torcao"])
def test_negated_absence_does_not_hard_stop(phrase):
    assert _classify_symptom_severity([phrase]) != SymptomSeverity.RED_FLAG


def test_substring_collision_does_not_fire(phrase="distorcao visual leve"):
    # 'torcao' must not match inside 'distorcao'
    assert _classify_symptom_severity([phrase]) != SymptomSeverity.RED_FLAG


def test_negation_does_not_mask_a_real_red_flag():
    # A pure-absence clause must NOT neutralize a genuine red flag elsewhere.
    assert _classify_symptom_severity(["sem tontura mas com dor aguda no tendao"]) == SymptomSeverity.RED_FLAG
