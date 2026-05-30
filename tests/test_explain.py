from running_coach.explain import ChangeExplanation, explain_change
from running_coach.models import RecommendationAction, SymptomSeverity
from running_coach.recommendations import RecommendationInput, recommend_next_action


def _input(**ov):
    base = dict(
        bruna_pse=6,
        symptom_severity=SymptomSeverity.NONE,
        matheus_achilles_morning=0,
        matheus_achilles_after=0,
        volleyball_previous_day=False,
        poor_sleep=False,
        all_out_race=False,
        planned_action=RecommendationAction.MAINTAIN_NEXT_WORKOUT,
        phase="half_base",
        week_number=5,
        planned_workout_id="plan-5",
    )
    base.update(ov)
    return RecommendationInput(**base)


def test_no_change_explained_as_maintained():
    res = recommend_next_action(_input())
    exp = explain_change(res, planned_action="maintain_next_workout")
    assert exp.changed is False
    assert "mantido" in exp.what_changed.lower()
    assert exp.micro_objective and exp.macro_objective


def test_change_carries_trigger_source_and_objectives():
    # Volleyball yesterday -> reduce; must explain with a PT-BR trigger + source.
    res = recommend_next_action(_input(volleyball_previous_day=True))
    exp = explain_change(res, planned_action="maintain_next_workout")
    assert exp.changed is True
    assert any("volei" in t for t in exp.triggers)
    assert exp.sources  # at least one science_ref
    assert exp.why
    assert exp.micro_objective and exp.macro_objective
    assert "janeiro" in exp.macro_objective.lower()


def test_red_flag_change_is_explained():
    res = recommend_next_action(_input(symptom_severity=SymptomSeverity.RED_FLAG))
    exp = explain_change(res, planned_action="maintain_next_workout")
    assert exp.changed is True
    assert any("alerta" in t for t in exp.triggers)
    assert exp.why


def test_every_changed_recommendation_has_nonempty_explanation():
    # No silent change: any change yields triggers OR an explicit why + objectives.
    for ov in [
        {"volleyball_previous_day": True},
        {"poor_sleep": True},
        {"bruna_pse": 9},
        {"matheus_achilles_after": 5},
        {"symptom_severity": SymptomSeverity.RED_FLAG},
    ]:
        res = recommend_next_action(_input(**ov))
        exp = explain_change(res, planned_action="maintain_next_workout")
        assert isinstance(exp, ChangeExplanation)
        assert exp.what_changed and exp.why
        assert exp.micro_objective and exp.macro_objective
        if exp.changed:
            assert exp.triggers and exp.sources
