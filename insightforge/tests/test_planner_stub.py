import pytest

from app.agents.planner_stub import StubPlanner
from app.schemas.planner import IntentType


@pytest.fixture
def planner() -> StubPlanner:
    return StubPlanner()


def test_stub_planner_assessment_intent(planner: StubPlanner) -> None:
    plan = planner.plan("What is the air quality in the big kitchen?")

    assert plan.intent == IntentType.AIR_QUALITY_ASSESSMENT
    assert plan.location_text == "Big Kitchen Level 11"


def test_stub_planner_recommendation_intent(planner: StubPlanner) -> None:
    plan = planner.plan("What should I do to improve air quality at reception?")

    assert plan.intent == IntentType.AIR_QUALITY_RECOMMENDATION
    assert plan.requires_recommendation is True
    assert "reception" in plan.location_text.lower()


def test_stub_planner_explanation_intent(planner: StubPlanner) -> None:
    plan = planner.plan("Why is the air quality poor in the meeting room?")

    assert plan.intent == IntentType.AIR_QUALITY_EXPLANATION
    assert plan.location_text == "Small meeting room CB02.11.153"


def test_stub_planner_rejects_empty_query(planner: StubPlanner) -> None:
    with pytest.raises(ValueError):
        planner.plan("   ")
