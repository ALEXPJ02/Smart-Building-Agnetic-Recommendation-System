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
    TrendDirection,
)
from app.services.analysis_service import AnalysisService
from app.services.risk_service import RiskService

BASE = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)


def _full_metrics() -> dict[MetricName, MetricValue]:
    return {
        MetricName.CO2: MetricValue(value=900, unit="ppm"),
        MetricName.PM25: MetricValue(value=4, unit="ug/m3"),
        MetricName.TEMPERATURE: MetricValue(value=22, unit="C"),
        MetricName.HUMIDITY: MetricValue(value=45, unit="%"),
    }


def _full_window() -> RecentWindow:
    series = {
        metric: [
            MetricSeriesPoint(timestamp=BASE + timedelta(minutes=index * 5), value=400 + index)
            for index in range(4)
        ]
        for metric in MetricName
    }
    return RecentWindow(
        device_id="UTS_IAQ_1",
        location_name="Simona's UTS desk",
        window_minutes=30,
        series=series,
    )


def test_high_confidence_for_complete_fresh_data() -> None:
    snapshot = SensorSnapshot(
        device_id="UTS_IAQ_1",
        location_name="Simona's UTS desk",
        timestamp=BASE,
        source=DataSource.MOCK,
        metrics=_full_metrics(),
    )
    window = _full_window()
    analysis = AnalysisService().analyze(snapshot, window)

    risk = RiskService().assess(snapshot, analysis, window, reference_time=BASE)

    assert risk.confidence == ConfidenceLevel.HIGH
    assert risk.data_quality_status == "good"
    assert risk.flags == []


def test_stale_data_reduces_confidence_to_low() -> None:
    snapshot = SensorSnapshot(
        device_id="UTS_IAQ_1",
        location_name="Simona's UTS desk",
        timestamp=BASE - timedelta(minutes=30),
        source=DataSource.MOCK,
        metrics=_full_metrics(),
    )
    window = _full_window()
    analysis = AnalysisService().analyze(snapshot, window)

    risk = RiskService().assess(snapshot, analysis, window, reference_time=BASE)

    assert "stale_data" in risk.flags
    assert risk.confidence == ConfidenceLevel.LOW
    assert risk.data_quality_status == "poor"


def test_missing_primary_metric_is_low_confidence() -> None:
    metrics = _full_metrics()
    del metrics[MetricName.CO2]
    snapshot = SensorSnapshot(
        device_id="UTS_IAQ_1",
        location_name="Simona's UTS desk",
        timestamp=BASE,
        source=DataSource.MOCK,
        metrics=metrics,
    )
    window = _full_window()
    analysis = AnalysisService().analyze(snapshot, window)

    risk = RiskService().assess(snapshot, analysis, window, reference_time=BASE)

    assert "missing_metric:co2" in risk.flags
    assert risk.confidence == ConfidenceLevel.LOW


def test_invalid_unit_on_context_metric_is_medium_confidence() -> None:
    metrics = _full_metrics()
    metrics[MetricName.HUMIDITY] = MetricValue(value=45, unit="pct")
    snapshot = SensorSnapshot(
        device_id="UTS_IAQ_1",
        location_name="Simona's UTS desk",
        timestamp=BASE,
        source=DataSource.MOCK,
        metrics=metrics,
    )
    window = _full_window()
    analysis = AnalysisService().analyze(snapshot, window)

    risk = RiskService().assess(snapshot, analysis, window, reference_time=BASE)

    assert "invalid_unit:humidity" in risk.flags
    assert risk.confidence == ConfidenceLevel.MEDIUM
    assert risk.data_quality_status == "degraded"


def test_insufficient_trend_data_is_medium_confidence() -> None:
    snapshot = SensorSnapshot(
        device_id="UTS_IAQ_1",
        location_name="Simona's UTS desk",
        timestamp=BASE,
        source=DataSource.MOCK,
        metrics=_full_metrics(),
    )
    window = RecentWindow(
        device_id="UTS_IAQ_1",
        location_name="Simona's UTS desk",
        window_minutes=30,
        series={MetricName.CO2: [MetricSeriesPoint(timestamp=BASE, value=900)]},
    )
    analysis = AnalysisService().analyze(snapshot, window)

    risk = RiskService().assess(snapshot, analysis, window, reference_time=BASE)

    assert any(flag.startswith("insufficient_trend_data:") for flag in risk.flags)
    assert risk.confidence == ConfidenceLevel.MEDIUM


def test_impossible_co2_value_is_low_confidence() -> None:
    metrics = _full_metrics()
    metrics[MetricName.CO2] = MetricValue(value=-5, unit="ppm")
    snapshot = SensorSnapshot(
        device_id="UTS_IAQ_1",
        location_name="Simona's UTS desk",
        timestamp=BASE,
        source=DataSource.MOCK,
        metrics=metrics,
    )
    window = _full_window()
    analysis = AnalysisService().analyze(snapshot, window)

    risk = RiskService().assess(snapshot, analysis, window, reference_time=BASE)

    assert "impossible_value:co2" in risk.flags
    assert risk.confidence == ConfidenceLevel.LOW
