from __future__ import annotations

from typing import List

from app.schemas.domain import (
    LocationResolution,
    MetricName,
    SensorSnapshot,
    TrendDirection,
)
from app.schemas.response import (
    AnalysisResult,
    RecommendationResult,
    RiskAssessment,
)
from app.services.rules_engine import PRIMARY_METRICS


class ExplainabilityEngine:
    """Build a structured, human-readable explainability trace from pipeline outputs."""

    def build_trace(
        self,
        query: str,
        location: LocationResolution,
        snapshot: SensorSnapshot,
        analysis: AnalysisResult,
        risk: RiskAssessment,
        recommendation: RecommendationResult,
    ) -> List[str]:
        trace: List[str] = []

        trace.append(f"Query: {query}")
        trace.extend(_location_lines(location))
        trace.extend(_provenance_lines(snapshot))
        trace.extend(_reading_lines(snapshot))
        trace.extend(_rule_lines(analysis))
        trace.extend(_trend_lines(analysis))
        trace.extend(_overall_lines(analysis))
        trace.extend(_risk_lines(risk))
        trace.extend(_recommendation_lines(recommendation))

        return trace


def _location_lines(location: LocationResolution) -> List[str]:
    return [
        "Location resolution:",
        (
            f"  Input '{location.input_text}' matched "
            f"{location.canonical_location} via {location.match_type} "
            f"(device {location.device_id})."
        ),
    ]


def _provenance_lines(snapshot: SensorSnapshot) -> List[str]:
    return [
        "Data provenance:",
        f"  Source: {snapshot.source.value}.",
        f"  Latest reading timestamp: {snapshot.timestamp.isoformat()}.",
        f"  Device: {snapshot.device_id} at {snapshot.location_name}.",
    ]


def _reading_lines(snapshot: SensorSnapshot) -> List[str]:
    lines = ["Current readings:"]
    for metric in MetricName:
        reading = snapshot.metrics.get(metric)
        if reading is None:
            lines.append(f"  {metric.value.upper()}: not available.")
            continue
        lines.append(
            f"  {metric.value.upper()}: {reading.value:g} {reading.unit}."
        )
    return lines


def _rule_lines(analysis: AnalysisResult) -> List[str]:
    lines = ["Triggered rules:"]
    for metric in MetricName:
        assessment = analysis.metric_assessments.get(metric)
        if assessment is None:
            continue
        lines.append(f"  {assessment.reason}")
    return lines


def _trend_lines(analysis: AnalysisResult) -> List[str]:
    lines = [f"Trend analysis ({analysis.trend.window_minutes} minute window):"]
    for metric in MetricName:
        direction = analysis.trend.trends.get(
            metric, TrendDirection.INSUFFICIENT_DATA
        )
        if direction == TrendDirection.INSUFFICIENT_DATA:
            lines.append(f"  {metric.value.upper()}: insufficient data for trend.")
        else:
            lines.append(f"  {metric.value.upper()}: {direction.value}.")
    return lines


def _overall_lines(analysis: AnalysisResult) -> List[str]:
    primary_summary = ", ".join(
        f"{metric.value.upper()}={analysis.metric_assessments[metric].status.value}"
        for metric in PRIMARY_METRICS
        if metric in analysis.metric_assessments
    )
    return [
        "Overall assessment:",
        f"  Primary metrics ({primary_summary}) drive overall status.",
        f"  Overall air quality: {analysis.overall_status.value}.",
    ]


def _risk_lines(risk: RiskAssessment) -> List[str]:
    lines = [
        "Risk and confidence:",
        f"  Confidence: {risk.confidence.value}.",
        f"  Data quality: {risk.data_quality_status}.",
    ]
    if risk.flags:
        lines.append(f"  Flags: {', '.join(risk.flags)}.")
    else:
        lines.append("  Flags: none.")
    return lines


def _recommendation_lines(recommendation: RecommendationResult) -> List[str]:
    lines = [
        "Recommendation rationale:",
        f"  Summary: {recommendation.summary}",
        f"  Rationale: {recommendation.rationale}",
        "  Recommended actions:",
    ]
    if recommendation.actions:
        for index, action in enumerate(recommendation.actions, start=1):
            lines.append(f"    {index}. {action}")
    else:
        lines.append("    None.")
    return lines
