from __future__ import annotations

from typing import List

from app.schemas.domain import ConfidenceLevel, MetricName, StatusLevel, TrendDirection
from app.schemas.response import AnalysisResult, RecommendationResult, RiskAssessment
from app.services.rules_engine import PRIMARY_METRICS


class RecommendationService:
    """Generate deterministic, explainable recommendations from analysis and risk."""

    def recommend(
        self,
        analysis: AnalysisResult,
        risk: RiskAssessment,
        location_name: str = "",
    ) -> RecommendationResult:
        actions: List[str] = []
        rationale_parts: List[str] = []

        if risk.confidence == ConfidenceLevel.LOW:
            actions.append(
                "Verify sensor connectivity and data freshness before making operational changes."
            )
            rationale_parts.append(
                "Confidence is low due to data quality concerns."
            )

        actions.extend(_actions_for_primary_metrics(analysis))
        actions.extend(_actions_for_comfort_metrics(analysis))
        actions.extend(_actions_for_trends(analysis))

        if not actions and analysis.overall_status == StatusLevel.GOOD:
            actions.append("Maintain current ventilation and occupancy patterns.")
            rationale_parts.append("All primary metrics are in the good range.")

        actions = _dedupe(actions)
        summary = _build_summary(analysis, location_name)
        rationale = _build_rationale(analysis, risk, rationale_parts)

        return RecommendationResult(
            summary=summary,
            actions=actions,
            rationale=rationale,
        )


def _actions_for_primary_metrics(analysis: AnalysisResult) -> List[str]:
    actions: List[str] = []

    co2 = analysis.metric_assessments.get(MetricName.CO2)
    if co2 and co2.status in {StatusLevel.MODERATE, StatusLevel.POOR}:
        actions.append(
            "Increase fresh-air ventilation or reduce occupancy in this space."
        )
    if co2 and co2.status == StatusLevel.POOR:
        actions.append(
            "Investigate CO2 sources such as overcrowding or insufficient outdoor air intake."
        )

    pm25 = analysis.metric_assessments.get(MetricName.PM25)
    if pm25 and pm25.status in {StatusLevel.MODERATE, StatusLevel.POOR}:
        actions.append(
            "Check for particle sources (cooking, dust, nearby equipment) and improve filtration or ventilation."
        )
    if pm25 and pm25.status == StatusLevel.POOR:
        actions.append(
            "Consider portable air filtration or reducing activities that generate fine particles."
        )

    return actions


def _actions_for_comfort_metrics(analysis: AnalysisResult) -> List[str]:
    actions: List[str] = []

    temperature = analysis.metric_assessments.get(MetricName.TEMPERATURE)
    if temperature and temperature.status == StatusLevel.OUT_OF_COMFORT_BAND:
        if temperature.value < 20:
            actions.append("Raise heating or reduce drafts to bring temperature into the comfort band.")
        else:
            actions.append(
                "Increase cooling or shading to bring temperature into the comfort band."
            )

    humidity = analysis.metric_assessments.get(MetricName.HUMIDITY)
    if humidity and humidity.status == StatusLevel.OUT_OF_COMFORT_BAND:
        if humidity.value < 30:
            actions.append("Increase humidification if occupants report dryness or discomfort.")
        else:
            actions.append(
                "Improve dehumidification or ventilation to reduce excess humidity."
            )

    return actions


def _actions_for_trends(analysis: AnalysisResult) -> List[str]:
    actions: List[str] = []

    for metric in PRIMARY_METRICS:
        direction = analysis.trend.trends.get(metric, TrendDirection.INSUFFICIENT_DATA)
        if direction != TrendDirection.RISING:
            continue

        if metric == MetricName.CO2:
            actions.append(
                "CO2 is rising over the trend window — act on ventilation before conditions worsen."
            )
        if metric == MetricName.PM25:
            actions.append(
                "PM2.5 is rising over the trend window — identify and control particle sources promptly."
            )

    return actions


def _build_summary(analysis: AnalysisResult, location_name: str) -> str:
    location_prefix = f"For {location_name}, " if location_name else ""
    status_label = analysis.overall_status.value.replace("_", " ")

    if analysis.overall_status == StatusLevel.GOOD:
        return f"{location_prefix}air quality is good. Continue routine monitoring."

    if analysis.overall_status == StatusLevel.MODERATE:
        return (
            f"{location_prefix}air quality is moderate. "
            "Targeted ventilation or source control is recommended."
        )

    return (
        f"{location_prefix}air quality is poor. "
        "Prioritize ventilation and source reduction immediately."
    )


def _build_rationale(
    analysis: AnalysisResult,
    risk: RiskAssessment,
    extra_parts: List[str],
) -> str:
    parts: List[str] = [
        f"Overall status is {analysis.overall_status.value}.",
        f"Data confidence is {risk.confidence.value} ({risk.data_quality_status}).",
    ]

    for metric in PRIMARY_METRICS:
        assessment = analysis.metric_assessments.get(metric)
        if assessment and assessment.status != StatusLevel.UNKNOWN:
            parts.append(assessment.reason)

    if risk.flags:
        parts.append(f"Risk flags: {', '.join(risk.flags)}.")

    parts.extend(extra_parts)
    return " ".join(parts)


def _dedupe(actions: List[str]) -> List[str]:
    seen: set[str] = set()
    unique: List[str] = []
    for action in actions:
        if action not in seen:
            seen.add(action)
            unique.append(action)
    return unique
