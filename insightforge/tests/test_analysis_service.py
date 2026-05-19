from datetime import datetime, timedelta, timezone

from app.schemas.domain import (
    DataSource,
    MetricName,
    MetricSeriesPoint,
    MetricValue,
    RecentWindow,
    SensorSnapshot,
    StatusLevel,
    TrendDirection,
)
from app.services.analysis_service import AnalysisService

BASE = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)


def _series(values: list[float]) -> list[MetricSeriesPoint]:
    return [
        MetricSeriesPoint(timestamp=BASE + timedelta(minutes=index * 5), value=value)
        for index, value in enumerate(values)
    ]


def test_analysis_service_end_to_end() -> None:
    snapshot = SensorSnapshot(
        device_id="UTS_IAQ_11",
        location_name="Big Kitchen Level 11",
        timestamp=BASE,
        source=DataSource.MOCK,
        metrics={
            MetricName.CO2: MetricValue(value=1300, unit="ppm"),
            MetricName.PM25: MetricValue(value=3, unit="ug/m3"),
            MetricName.TEMPERATURE: MetricValue(value=22, unit="C"),
            MetricName.HUMIDITY: MetricValue(value=45, unit="%"),
        },
    )
    window = RecentWindow(
        device_id="UTS_IAQ_11",
        location_name="Big Kitchen Level 11",
        window_minutes=30,
        series={MetricName.CO2: _series([800, 850, 900, 950])},
    )

    result = AnalysisService().analyze(snapshot, window)

    assert result.overall_status == StatusLevel.POOR
    assert result.metric_assessments[MetricName.CO2].status == StatusLevel.POOR
    assert result.trend.trends[MetricName.CO2] == TrendDirection.RISING
    assert any("Overall air quality" in line for line in result.reason_summary)
