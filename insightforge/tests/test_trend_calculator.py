from datetime import datetime, timedelta, timezone

import pytest

from app.schemas.domain import (
    DataSource,
    MetricName,
    MetricSeriesPoint,
    RecentWindow,
    TrendDirection,
)
from app.services.rules_engine import load_rules, DEFAULT_RULES_PATH
from app.services.trend_calculator import (
    compute_trends,
    load_settings,
    trend_for_series,
)

RULES = load_rules(DEFAULT_RULES_PATH)
BASE = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)


def _points(values: list[float]) -> list[MetricSeriesPoint]:
    return [
        MetricSeriesPoint(timestamp=BASE + timedelta(minutes=index * 5), value=value)
        for index, value in enumerate(values)
    ]


def test_trend_stable_within_deadband() -> None:
    points = _points([800, 820, 810, 830])
    assert trend_for_series(points, deadband=50) == TrendDirection.STABLE


def test_trend_rising_above_deadband() -> None:
    points = _points([800, 850, 900, 950])
    assert trend_for_series(points, deadband=50) == TrendDirection.RISING


def test_trend_falling_above_deadband() -> None:
    points = _points([1200, 1100, 1000, 900])
    assert trend_for_series(points, deadband=50) == TrendDirection.FALLING


def test_trend_insufficient_data() -> None:
    assert trend_for_series(_points([900]), deadband=50) == TrendDirection.INSUFFICIENT_DATA


def test_compute_trends_for_recent_window() -> None:
    window = RecentWindow(
        device_id="UTS_IAQ_11",
        location_name="Big Kitchen Level 11",
        window_minutes=30,
        series={
            MetricName.CO2: _points([800, 850, 900, 950]),
            MetricName.PM25: _points([4, 4, 4, 4]),
        },
    )

    result = compute_trends(window, RULES)

    assert result.window_minutes == 30
    assert result.trends[MetricName.CO2] == TrendDirection.RISING
    assert result.trends[MetricName.PM25] == TrendDirection.STABLE


def test_load_settings_from_project_config() -> None:
    settings = load_settings()
    assert settings["trend_window_minutes"] == 30
