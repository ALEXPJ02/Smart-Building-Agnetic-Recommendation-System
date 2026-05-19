from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Dict, List

from app.schemas.domain import MetricName, MetricSeriesPoint, RecentWindow, TrendDirection
from app.schemas.response import TrendResult

DEFAULT_SETTINGS_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "settings.json"
)
DEFAULT_RULES_PATH = Path(__file__).resolve().parents[2] / "config" / "rules.json"

_TREND_METRICS = (
    MetricName.CO2,
    MetricName.PM25,
    MetricName.TEMPERATURE,
    MetricName.HUMIDITY,
)

_METRIC_RULE_KEYS: Dict[MetricName, str] = {
    MetricName.CO2: "co2",
    MetricName.PM25: "pm25",
    MetricName.TEMPERATURE: "temperature",
    MetricName.HUMIDITY: "humidity",
}


def load_settings(path: Path | None = None) -> dict:
    settings_path = path or DEFAULT_SETTINGS_PATH
    if not settings_path.is_file():
        raise FileNotFoundError(f"Settings file not found: {settings_path}")

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    if not isinstance(settings, dict):
        raise ValueError("Settings file must contain a JSON object.")
    return settings


def clamp_trend_window_minutes(requested: int, settings: dict) -> int:
    minimum = settings["trend_window_min"]
    maximum = settings["trend_window_max"]
    return max(minimum, min(requested, maximum))


def trend_for_series(
    points: List[MetricSeriesPoint], deadband: float
) -> TrendDirection:
    if len(points) < 2:
        return TrendDirection.INSUFFICIENT_DATA

    ordered = sorted(points, key=lambda point: point.timestamp)
    midpoint = len(ordered) // 2
    earlier = ordered[:midpoint]
    recent = ordered[midpoint:]

    if not earlier or not recent:
        return TrendDirection.INSUFFICIENT_DATA

    earlier_avg = mean(point.value for point in earlier)
    recent_avg = mean(point.value for point in recent)
    delta = recent_avg - earlier_avg

    if abs(delta) <= deadband:
        return TrendDirection.STABLE
    if delta > deadband:
        return TrendDirection.RISING
    return TrendDirection.FALLING


def deadband_for_metric(metric: MetricName, rules: dict) -> float:
    rule_key = _METRIC_RULE_KEYS[metric]
    return float(rules.get(rule_key, {}).get("trend_deadband", 0))


def compute_trends(window: RecentWindow, rules: dict) -> TrendResult:
    trends: Dict[MetricName, TrendDirection] = {}

    for metric in _TREND_METRICS:
        points = window.series.get(metric, [])
        deadband = deadband_for_metric(metric, rules)
        trends[metric] = trend_for_series(points, deadband)

    return TrendResult(window_minutes=window.window_minutes, trends=trends)
