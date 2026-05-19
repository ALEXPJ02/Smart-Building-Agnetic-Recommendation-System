from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class MetricName(str, Enum):
    CO2 = "co2"
    PM25 = "pm25"
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"


class StatusLevel(str, Enum):
    GOOD = "good"
    MODERATE = "moderate"
    POOR = "poor"
    UNKNOWN = "unknown"
    COMFORTABLE = "comfortable"
    OUT_OF_COMFORT_BAND = "out_of_comfort_band"


class TrendDirection(str, Enum):
    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"
    INSUFFICIENT_DATA = "insufficient_data"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DataSource(str, Enum):
    SMARTCITIZEN_API = "smartcitizen_api"
    CSV = "csv"
    MOCK = "mock"


class LocationMappingEntry(BaseModel):
    device_id: str
    location_name: str
    aliases: List[str] = Field(default_factory=list)
    building: Optional[str] = None
    floor: Optional[str] = None
    zone_type: Optional[str] = None
    active: bool = True
    notes: Optional[str] = None


class MetricValue(BaseModel):
    value: float
    unit: str
    status: Optional[StatusLevel] = None


class SensorSnapshot(BaseModel):
    device_id: str
    location_name: str
    timestamp: datetime
    source: DataSource
    metrics: Dict[MetricName, MetricValue]


class MetricSeriesPoint(BaseModel):
    timestamp: datetime
    value: float


class RecentWindow(BaseModel):
    device_id: str
    location_name: str
    window_minutes: int
    series: Dict[MetricName, List[MetricSeriesPoint]]


class LocationResolution(BaseModel):
    input_text: str
    canonical_location: str
    device_id: str
    match_type: str