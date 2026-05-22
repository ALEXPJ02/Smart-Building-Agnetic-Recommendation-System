from pathlib import Path

import pytest

from app.core.orchestrator import Orchestrator, OrchestratorError
from app.schemas.domain import MetricName
from app.schemas.planner import IntentType, PlannerOutput

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "data" / "samples" / "UTS_IAQ_1"


def _plan(location_text: str = "simona's desk") -> PlannerOutput:
    return PlannerOutput(
        intent=IntentType.AIR_QUALITY_ASSESSMENT,
        location_text=location_text,
    )


def test_orchestrator_end_to_end_with_sample_data() -> None:
    orchestrator = Orchestrator(csv_data_dir=SAMPLES_DIR)

    response = orchestrator.run(
        query="What is the air quality at Simona's desk?",
        plan=_plan(),
    )

    assert response.query.startswith("What is the air quality")
    assert response.location.device_id == "UTS_IAQ_1"
    assert response.status["overall"] in {"good", "moderate", "poor"}
    assert MetricName.CO2 in response.current_readings
    assert response.analysis.overall_status
    assert response.risk.confidence
    assert len(response.recommendation.actions) >= 1
    assert any("Location resolution" in line for line in response.explainability)


def test_orchestrator_unknown_location_raises() -> None:
    orchestrator = Orchestrator(csv_data_dir=SAMPLES_DIR)

    with pytest.raises(OrchestratorError, match="Could not resolve location"):
        orchestrator.run(
            query="Air quality in unknown room",
            plan=_plan("nonexistent room xyz"),
        )


def test_orchestrator_rejects_empty_location_text() -> None:
    orchestrator = Orchestrator(csv_data_dir=SAMPLES_DIR)
    plan = PlannerOutput(
        intent=IntentType.AIR_QUALITY_ASSESSMENT,
        location_text="   ",
    )

    with pytest.raises(OrchestratorError, match="location_text is empty"):
        orchestrator.run(query="test", plan=plan)


def test_orchestrator_skips_recommendation_when_not_required() -> None:
    orchestrator = Orchestrator(csv_data_dir=SAMPLES_DIR)
    plan = PlannerOutput(
        intent=IntentType.AIR_QUALITY_ASSESSMENT,
        location_text="simona's desk",
        requires_recommendation=False,
    )

    response = orchestrator.run(query="Status only", plan=plan)

    assert response.recommendation.actions == []
    assert "disabled" in response.recommendation.rationale.lower()
