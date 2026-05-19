from __future__ import annotations

from pathlib import Path
from typing import List

from app.schemas.domain import (
    MetricName,
    RecentWindow,
    SensorSnapshot,
    StatusLevel,
    TrendDirection,
)
from app.schemas.response import AnalysisResult, MetricAssessment
from app.services.rules_engine import (
    PRIMARY_METRICS,
    assess_snapshot,
    load_rules,
    overall_status,
)
from app.services.trend_calculator import compute_trends, load_settings

DEFAULT_RULES_PATH = Path(__file__).resolve().parents[2] / "config" / "rules.json"
DEFAULT_SETTINGS_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "settings.json"
)


class AnalysisService:
    def __init__(
        self,
        rules: dict | None = None,
        settings: dict | None = None,
        rules_path: Path | None = None,
        settings_path: Path | None = None,
    ) -> None:
        self.rules = rules if rules is not None else load_rules(rules_path)
        self.settings = (
            settings if settings is not None else load_settings(settings_path)
        )

    def analyze(self, snapshot: SensorSnapshot, window: RecentWindow) -> AnalysisResult:
        assessments = assess_snapshot(snapshot, self.rules)
        trends = compute_trends(window, self.rules)
        overall = overall_status(
            {metric: assessments[metric].status for metric in PRIMARY_METRICS}
        )
        reason_summary = _build_reason_summary(assessments, trends, overall)

        return AnalysisResult(
            overall_status=overall,
            metric_assessments=assessments,
            trend=trends,
            reason_summary=reason_summary,
        )


def _build_reason_summary(
    assessments: dict[MetricName, MetricAssessment],
    trends,
    overall: StatusLevel,
) -> List[str]:
    lines: List[str] = [f"Overall air quality status is {overall.value}."]

    for metric in PRIMARY_METRICS:
        assessment = assessments[metric]
        if assessment.status != StatusLevel.UNKNOWN:
            lines.append(assessment.reason)

    for metric in (MetricName.TEMPERATURE, MetricName.HUMIDITY):
        assessment = assessments[metric]
        if assessment.status == StatusLevel.OUT_OF_COMFORT_BAND:
            lines.append(assessment.reason)

    for metric, direction in trends.trends.items():
        if direction == TrendDirection.INSUFFICIENT_DATA:
            continue
        if direction != TrendDirection.STABLE:
            lines.append(
                f"{metric.value.upper()} trend is {direction.value} "
                f"over the last {trends.window_minutes} minutes."
            )

    return lines
