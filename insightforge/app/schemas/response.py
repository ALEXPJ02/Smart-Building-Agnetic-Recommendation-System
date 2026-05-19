from typing import Dict, List

from pydantic import BaseModel

from app.schemas.domain import (
    ConfidenceLevel,
    LocationResolution,
    MetricName,
    MetricValue,
    StatusLevel,
    TrendDirection,
)


class MetricAssessment(BaseModel):
    metric: MetricName
    value: float
    unit: str
    status: StatusLevel
    reason: str


class TrendResult(BaseModel):
    window_minutes: int
    trends: Dict[MetricName, TrendDirection]


class AnalysisResult(BaseModel):
    overall_status: StatusLevel
    metric_assessments: Dict[MetricName, MetricAssessment]
    trend: TrendResult
    reason_summary: List[str]


class RiskAssessment(BaseModel):
    confidence: ConfidenceLevel
    flags: List[str]
    data_quality_status: str


class RecommendationResult(BaseModel):
    summary: str
    actions: List[str]
    rationale: str


class FinalResponse(BaseModel):
    query: str
    location: LocationResolution
    status: Dict[str, str]
    current_readings: Dict[MetricName, MetricValue]
    analysis: AnalysisResult
    risk: RiskAssessment
    recommendation: RecommendationResult
    explainability: List[str]
