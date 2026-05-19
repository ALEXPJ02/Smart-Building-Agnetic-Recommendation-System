from enum import Enum
from typing import List

from pydantic import BaseModel, Field

from app.schemas.domain import MetricName


class IntentType(str, Enum):
    AIR_QUALITY_ASSESSMENT = "air_quality_assessment"
    AIR_QUALITY_EXPLANATION = "air_quality_explanation"
    AIR_QUALITY_RECOMMENDATION = "air_quality_recommendation"


class PlannerRequest(BaseModel):
    query: str = Field(..., min_length=1)


class PlannerOutput(BaseModel):
    intent: IntentType
    location_text: str = Field(..., min_length=1)
    canonical_metrics: List[MetricName] = Field(
        default=[
            MetricName.CO2,
            MetricName.PM25,
            MetricName.TEMPERATURE,
            MetricName.HUMIDITY,
        ]
    )
    trend_window_minutes: int = 30
    requires_explanation: bool = True
    requires_recommendation: bool = True