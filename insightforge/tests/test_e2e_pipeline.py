from pathlib import Path

from app.core import Orchestrator

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "data" / "samples" / "UTS_IAQ_1"


def test_full_pipeline_query_to_final_response() -> None:
    orchestrator = Orchestrator(csv_data_dir=SAMPLES_DIR)

    response = orchestrator.run_query(
        "What is the air quality at Simona's desk?"
    )

    assert response.location.device_id == "UTS_IAQ_1"
    assert response.status["overall"] in {"good", "moderate", "poor"}
    assert response.recommendation.summary
    assert len(response.explainability) >= 5


def test_full_pipeline_recommendation_query() -> None:
    """Uses Simona's desk — sample CSV fixtures exist only for UTS_IAQ_1."""
    orchestrator = Orchestrator(csv_data_dir=SAMPLES_DIR)

    response = orchestrator.run_query(
        "What should I do to improve air quality at Simona's desk?"
    )

    assert response.location.device_id == "UTS_IAQ_1"
    assert len(response.recommendation.actions) >= 1
