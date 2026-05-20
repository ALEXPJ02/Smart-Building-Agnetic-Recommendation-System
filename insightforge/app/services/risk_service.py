from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

from app.schemas.domain import (
    ConfidenceLevel,
    MetricName,
    RecentWindow,
    SensorSnapshot,
    TrendDirection,
)
from app.schemas.response import AnalysisResult, RiskAssessment
from app.services.rules_engine import PRIMARY_METRICS, load_rules
from app.services.trend_calculator import load_settings

CONTEXT_METRICS = (MetricName.TEMPERATURE, MetricName.HUMIDITY)

_METRIC_RULE_KEYS: Dict[MetricName, str] = {
    MetricName.CO2: "co2",
    MetricName.PM25: "pm25",
    MetricName.TEMPERATURE: "temperature",
    MetricName.HUMIDITY: "humidity",
}

_VALUE_BOUNDS: Dict[MetricName, Tuple[float, float]] = {
    MetricName.CO2: (0, 10000),
    MetricName.PM25: (0, 1000),
    MetricName.TEMPERATURE: (-10, 50),
    MetricName.HUMIDITY: (0, 100),
}


class RiskService:
    """Assess data quality and confidence for analysis outputs."""

    def __init__(self, rules: dict | None = None, settings: dict | None = None) -> None:
        self.rules = rules if rules is not None else load_rules()
        self.settings = settings if settings is not None else load_settings()

    def assess(
        self,
        snapshot: SensorSnapshot,
        analysis: AnalysisResult,
        window: RecentWindow | None = None,
        reference_time: datetime | None = None,
    ) -> RiskAssessment:
        now = reference_time or datetime.now(timezone.utc)
        flags: List[str] = []

        flags.extend(self._check_missing_metrics(snapshot))
        flags.extend(self._check_stale_data(snapshot, now))
        flags.extend(self._check_units(snapshot))
        flags.extend(self._check_impossible_values(snapshot))
        flags.extend(self._check_trend_data(analysis))

        confidence = self._confidence_from_flags(flags)
        data_quality_status = _data_quality_status(confidence)

        return RiskAssessment(
            confidence=confidence,
            flags=flags,
            data_quality_status=data_quality_status,
        )

    def _check_missing_metrics(self, snapshot: SensorSnapshot) -> List[str]:
        flags: List[str] = []
        for metric in MetricName:
            if metric not in snapshot.metrics:
                flags.append(f"missing_metric:{metric.value}")
        return flags

    def _check_stale_data(
        self, snapshot: SensorSnapshot, reference_time: datetime
    ) -> List[str]:
        stale_after = timedelta(minutes=self.settings["stale_reading_minutes"])
        timestamp = snapshot.timestamp
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        if reference_time - timestamp > stale_after:
            return ["stale_data"]
        return []

    def _check_units(self, snapshot: SensorSnapshot) -> List[str]:
        flags: List[str] = []
        for metric, reading in snapshot.metrics.items():
            rule_key = _METRIC_RULE_KEYS[metric]
            expected = self.rules[rule_key]["unit"]
            if reading.unit != expected:
                flags.append(f"invalid_unit:{metric.value}")
        return flags

    def _check_impossible_values(self, snapshot: SensorSnapshot) -> List[str]:
        flags: List[str] = []
        for metric, reading in snapshot.metrics.items():
            lower, upper = _VALUE_BOUNDS[metric]
            if reading.value < lower or reading.value > upper:
                flags.append(f"impossible_value:{metric.value}")
        return flags

    def _check_trend_data(self, analysis: AnalysisResult) -> List[str]:
        flags: List[str] = []
        for metric in MetricName:
            direction = analysis.trend.trends.get(metric, TrendDirection.INSUFFICIENT_DATA)
            if direction == TrendDirection.INSUFFICIENT_DATA:
                flags.append(f"insufficient_trend_data:{metric.value}")
        return flags

    def _confidence_from_flags(self, flags: List[str]) -> ConfidenceLevel:
        if not flags:
            return ConfidenceLevel.HIGH

        if _has_low_confidence_flag(flags):
            return ConfidenceLevel.LOW

        if _has_medium_confidence_flag(flags):
            return ConfidenceLevel.MEDIUM

        return ConfidenceLevel.HIGH


def _has_low_confidence_flag(flags: List[str]) -> bool:
    for flag in flags:
        if flag in {"stale_data"}:
            return True
        if flag.startswith("missing_metric:"):
            metric = flag.split(":", 1)[1]
            if metric in {item.value for item in PRIMARY_METRICS}:
                return True
        if flag.startswith("invalid_unit:"):
            metric = flag.split(":", 1)[1]
            if metric in {item.value for item in PRIMARY_METRICS}:
                return True
        if flag.startswith("impossible_value:"):
            metric = flag.split(":", 1)[1]
            if metric in {item.value for item in PRIMARY_METRICS}:
                return True
    return False


def _has_medium_confidence_flag(flags: List[str]) -> bool:
    for flag in flags:
        if flag.startswith("missing_metric:"):
            metric = flag.split(":", 1)[1]
            if metric in {item.value for item in CONTEXT_METRICS}:
                return True
        if flag.startswith("invalid_unit:"):
            metric = flag.split(":", 1)[1]
            if metric in {item.value for item in CONTEXT_METRICS}:
                return True
        if flag.startswith("impossible_value:"):
            metric = flag.split(":", 1)[1]
            if metric in {item.value for item in CONTEXT_METRICS}:
                return True
        if flag.startswith("insufficient_trend_data:"):
            return True
    return False


def _data_quality_status(confidence: ConfidenceLevel) -> str:
    if confidence == ConfidenceLevel.HIGH:
        return "good"
    if confidence == ConfidenceLevel.MEDIUM:
        return "degraded"
    return "poor"
