from datetime import datetime, timedelta, timezone

import pytest

from app.schemas.domain import (
    ConfidenceLevel,
    DataSource,
    MetricName,
    MetricSeriesPoint,
    MetricValue,
    RecentWindow,
    SensorSnapshot,
    StatusLevel,
)
from app.schemas.response import RiskAssessment
from app.services.analysis_service import AnalysisService
from app.services.recommendation_service import RecommendationService
from app.services.risk_service import RiskService

BASE = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)


def _snapshot(
    co2: float = 900,
    pm25: float = 4,
    temperature: float = 22,
    humidity: float = 45,
) -> SensorSnapshot:
    return SensorSnapshot(
        device_id="UTS_IAQ_1",
        location_name="Simona's UTS desk",
        timestamp=BASE,
        source=DataSource.MOCK,
        metrics={
            MetricName.CO2: MetricValue(value=co2, unit="ppm"),
            MetricName.PM25: MetricValue(value=pm25, unit="ug/m3"),
            MetricName.TEMPERATURE: MetricValue(value=temperature, unit="C"),
            MetricName.HUMIDITY: MetricValue(value=humidity, unit="%"),
        },
    )


def _window(co2_values: list[float] | None = None) -> RecentWindow:
    values = co2_values or [800, 850, 900, 950]
    return RecentWindow(
        device_id="UTS_IAQ_1",
        location_name="Simona's UTS desk",
        window_minutes=30,
        series={
            MetricName.CO2: [
                MetricSeriesPoint(timestamp=BASE + timedelta(minutes=index * 5), value=value)
                for index, value in enumerate(values)
            ]
        },
    )


def test_good_air_quality_recommends_monitoring() -> None:
    snapshot = _snapshot(co2=750, pm25=3)
    window = _window([750, 740, 745, 748])
    analysis = AnalysisService().analyze(snapshot, window)
    risk = RiskService().assess(snapshot, analysis, window, reference_time=BASE)

    result = RecommendationService().recommend(
        analysis, risk, location_name="Simona's UTS desk"
    )

    assert "good" in result.summary.lower()
    assert len(result.actions) >= 1
    assert result.rationale


def test_poor_co2_recommends_ventilation() -> None:
    snapshot = _snapshot(co2=1300, pm25=3)
    window = _window([800, 950, 1100, 1300])
    analysis = AnalysisService().analyze(snapshot, window)
    risk = RiskService().assess(snapshot, analysis, window, reference_time=BASE)

    result = RecommendationService().recommend(analysis, risk)

    assert "poor" in result.summary.lower()
    assert any("ventilation" in action.lower() for action in result.actions)
    assert any("CO2" in result.rationale or "co2" in result.rationale.lower() for _ in [1])


def test_low_confidence_adds_data_verification_action() -> None:
    snapshot = _snapshot()
    snapshot.timestamp = BASE - timedelta(minutes=30)
    window = _window()
    analysis = AnalysisService().analyze(snapshot, window)
    risk = RiskService().assess(snapshot, analysis, window, reference_time=BASE)

    result = RecommendationService().recommend(analysis, risk)

    assert risk.confidence == ConfidenceLevel.LOW
    assert any("sensor" in action.lower() or "data" in action.lower() for action in result.actions)


def test_out_of_comfort_temperature_recommends_heating_or_cooling() -> None:
    snapshot = _snapshot(temperature=18)
    window = _window()
    analysis = AnalysisService().analyze(snapshot, window)
    risk = RiskAssessment(
        confidence=ConfidenceLevel.HIGH,
        flags=[],
        data_quality_status="good",
    )

    result = RecommendationService().recommend(analysis, risk)

    assert any(
        "heating" in action.lower() or "cooling" in action.lower()
        for action in result.actions
    )


@pytest.mark.parametrize(
    ("humidity", "keyword"),
    [(65, "dehumid"), (25, "humid")],
)
def test_out_of_comfort_humidity(humidity: float, keyword: str) -> None:
    snapshot = _snapshot(humidity=humidity)
    window = _window()
    analysis = AnalysisService().analyze(snapshot, window)
    risk = RiskAssessment(
        confidence=ConfidenceLevel.HIGH,
        flags=[],
        data_quality_status="good",
    )

    result = RecommendationService().recommend(analysis, risk)

    assert any(keyword in action.lower() for action in result.actions)
