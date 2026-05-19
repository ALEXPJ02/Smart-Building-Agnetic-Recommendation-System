from pathlib import Path

import pytest

from app.schemas.domain import DataSource, MetricName, MetricValue, SensorSnapshot, StatusLevel
from app.services.rules_engine import (
    DEFAULT_RULES_PATH,
    assess_snapshot,
    classify_comfort,
    classify_primary,
    load_rules,
    overall_status,
)

RULES = load_rules(DEFAULT_RULES_PATH)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (750, StatusLevel.GOOD),
        (800, StatusLevel.GOOD),
        (950, StatusLevel.MODERATE),
        (1200, StatusLevel.MODERATE),
        (1201, StatusLevel.POOR),
    ],
)
def test_classify_co2(value: float, expected: StatusLevel) -> None:
    status, _ = classify_primary(value, RULES, "co2")
    assert status == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (4, StatusLevel.GOOD),
        (5, StatusLevel.GOOD),
        (10, StatusLevel.MODERATE),
        (15, StatusLevel.MODERATE),
        (16, StatusLevel.POOR),
    ],
)
def test_classify_pm25(value: float, expected: StatusLevel) -> None:
    status, _ = classify_primary(value, RULES, "pm25")
    assert status == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (22, StatusLevel.COMFORTABLE),
        (19, StatusLevel.OUT_OF_COMFORT_BAND),
        (25, StatusLevel.OUT_OF_COMFORT_BAND),
    ],
)
def test_classify_temperature_comfort(value: float, expected: StatusLevel) -> None:
    status, _ = classify_comfort(value, RULES, "temperature")
    assert status == expected


def test_overall_status_uses_worst_primary_metric() -> None:
    statuses = {
        MetricName.CO2: StatusLevel.POOR,
        MetricName.PM25: StatusLevel.GOOD,
    }
    assert overall_status(statuses) == StatusLevel.POOR


def test_load_rules_from_project_config() -> None:
    rules = load_rules(Path(__file__).resolve().parents[1] / "config" / "rules.json")
    assert rules["co2"]["good_max"] == 800


def test_assess_snapshot_produces_all_metrics() -> None:
    from datetime import datetime, timezone

    snapshot = SensorSnapshot(
        device_id="UTS_IAQ_11",
        location_name="Big Kitchen Level 11",
        timestamp=datetime.now(timezone.utc),
        source=DataSource.MOCK,
        metrics={
            MetricName.CO2: MetricValue(value=1300, unit="ppm"),
            MetricName.PM25: MetricValue(value=3, unit="ug/m3"),
            MetricName.TEMPERATURE: MetricValue(value=22, unit="C"),
            MetricName.HUMIDITY: MetricValue(value=45, unit="%"),
        },
    )

    assessments = assess_snapshot(snapshot, RULES)

    assert assessments[MetricName.CO2].status == StatusLevel.POOR
    assert assessments[MetricName.PM25].status == StatusLevel.GOOD
    assert assessments[MetricName.TEMPERATURE].status == StatusLevel.COMFORTABLE
