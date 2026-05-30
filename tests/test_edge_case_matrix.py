import pytest

from running_coach.models import RecommendationAction as A, SymptomSeverity
from running_coach.recommendations import RecommendationInput, recommend_next_action


def _inp(**ov):
    base = dict(
        bruna_pse=6, symptom_severity=SymptomSeverity.NONE,
        matheus_achilles_morning=0, matheus_achilles_after=0,
        volleyball_previous_day=False, poor_sleep=False, all_out_race=False,
        planned_action=A.MAINTAIN_NEXT_WORKOUT, phase="half_base",
        week_number=5, planned_workout_id="p5",
    )
    base.update(ov)
    return RecommendationInput(**base)


MATRIX = [
    ("perfeito", dict(bruna_pse=5), A.MAINTAIN_NEXT_WORKOUT),
    ("perfeito_cansado", dict(bruna_pse=8), A.MAINTAIN_NEXT_WORKOUT),
    ("pse9", dict(bruna_pse=9), A.REPLACE_WITH_EASY),
    ("volei", dict(volleyball_previous_day=True), A.REDUCE_NEXT_WORKOUT),
    ("academia", dict(gym_previous_day=True), A.REDUCE_NEXT_WORKOUT),
    ("lower_body", dict(lower_body_load_previous_day=True), A.REDUCE_NEXT_WORKOUT),
    ("sono_ruim", dict(poor_sleep=True), A.REDUCE_NEXT_WORKOUT),
    ("sintoma_forte", dict(symptom_severity=SymptomSeverity.MODERATE), A.REDUCE_NEXT_WORKOUT),
    ("red_flag", dict(symptom_severity=SymptomSeverity.RED_FLAG), A.REPLACE_WITH_OFF),
    ("aquiles3", dict(matheus_achilles_after=3), A.DEFER_QUALITY),
    ("aquiles5", dict(matheus_achilles_after=5), A.BRUNA_WITHOUT_MATHEUS),
    ("all_out", dict(all_out_race=True), A.REDUCE_NEXT_WORKOUT),
    ("longao_quebrado", dict(workout_truncated=True), A.REDUCE_NEXT_WORKOUT),
    ("longao_rapido", dict(overpaced=True), A.REDUCE_NEXT_WORKOUT),
    ("longao_lento", dict(underpaced=True), A.REDUCE_NEXT_WORKOUT),
]


@pytest.mark.parametrize("name,ov,expected", MATRIX, ids=[m[0] for m in MATRIX])
def test_edge_case_matrix(name, ov, expected):
    result = recommend_next_action(_inp(**ov))
    assert result.action == expected, (name, result.action.value, result.reasons)


def test_no_edge_case_silently_maintains_when_it_should_reduce():
    # Every execution/load signal must move OFF maintain.
    for ov in [
        dict(gym_previous_day=True),
        dict(lower_body_load_previous_day=True),
        dict(workout_truncated=True),
        dict(overpaced=True),
        dict(underpaced=True),
    ]:
        r = recommend_next_action(_inp(**ov))
        assert r.action != A.MAINTAIN_NEXT_WORKOUT, ov
        assert r.science_refs  # cites a source


def test_execution_signals_only_lower_envelope():
    # With an already-conservative plan, execution signals never raise it.
    r = recommend_next_action(_inp(overpaced=True, planned_action=A.REPLACE_WITH_OFF))
    assert r.action == A.REPLACE_WITH_OFF
