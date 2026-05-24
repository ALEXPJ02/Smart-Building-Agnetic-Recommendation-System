from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.schemas.domain import (
    DataSource,
    MetricName,
    MetricSeriesPoint,
    MetricValue,
    RecentWindow,
    SensorSnapshot,
)
from app.services.smartcitizen_client import ApiSensor, SmartCitizenClient
from app.services.trend_calculator import clamp_trend_window_minutes, load_settings

DEFAULT_DEVICE_API_IDS_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "device_api_ids.json"
)
DEFAULT_API_METRICS_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "api_metrics.json"
)

_METRIC_NAME_BY_KEY: Dict[str, MetricName] = {
    "co2": MetricName.CO2,
    "pm25": MetricName.PM25,
    "temperature": MetricName.TEMPERATURE,
    "humidity": MetricName.HUMIDITY,
}


class SmartCitizenApiAdapterError(Exception):
    """API adapter could not produce InsightForge sensor schemas."""


class SmartCitizenApiAdapter:
    """Fetch live Smart Citizen readings and map them to internal schemas."""

    def __init__(
        self,
        client: SmartCitizenClient,
        device_api_ids: Dict[str, int],
        metric_sensor_patterns: Dict[MetricName, str],
        settings: dict | None = None,
        settings_path: Path | None = None,
    ) -> None:
        self.client = client
        self.device_api_ids = device_api_ids
        self.metric_sensor_patterns = metric_sensor_patterns
        self.settings = (
            settings if settings is not None else load_settings(settings_path)
        )

    @classmethod
    def from_env(
        cls,
        settings: dict | None = None,
        settings_path: Path | None = None,
        device_api_ids_path: Path | None = None,
        api_metrics_path: Path | None = None,
    ) -> SmartCitizenApiAdapter:
        return cls(
            client=SmartCitizenClient.from_env(),
            device_api_ids=load_device_api_ids(device_api_ids_path),
            metric_sensor_patterns=load_api_metric_patterns(api_metrics_path),
            settings=settings,
            settings_path=settings_path,
        )

    def load_snapshot(
        self, device_id: str, location_name: str
    ) -> SensorSnapshot:
        api_device_id = self._resolve_api_device_id(device_id)
        sensors = self.client.list_device_sensors(api_device_id)
        latest_timestamp = self.client.get_device_last_reading_at(api_device_id)

        metrics: Dict[MetricName, MetricValue] = {}
        for metric, pattern in self.metric_sensor_patterns.items():
            sensor = _match_sensor(sensors, pattern)
            if sensor is None or sensor.value is None:
                continue
            unit = sensor.unit or _default_unit(metric)
            metrics[metric] = MetricValue(value=sensor.value, unit=unit)

        if not metrics:
            raise SmartCitizenApiAdapterError(
                f"No live sensor values found for device '{device_id}'."
            )

        if latest_timestamp is None:
            latest_timestamp = datetime.now(timezone.utc)

        return SensorSnapshot(
            device_id=device_id,
            location_name=location_name,
            timestamp=latest_timestamp,
            source=DataSource.SMARTCITIZEN_API,
            metrics=metrics,
        )

    def load_recent_window(
        self,
        device_id: str,
        location_name: str,
        window_minutes: int | None = None,
    ) -> RecentWindow:
        requested = window_minutes or self.settings["trend_window_minutes"]
        window_minutes = clamp_trend_window_minutes(requested, self.settings)

        api_device_id = self._resolve_api_device_id(device_id)
        sensors = self.client.list_device_sensors(api_device_id)
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=window_minutes)

        series: Dict[MetricName, List[MetricSeriesPoint]] = {}
        for metric, pattern in self.metric_sensor_patterns.items():
            sensor = _match_sensor(sensors, pattern)
            if sensor is None:
                series[metric] = []
                continue
            readings = self.client.get_sensor_readings(
                api_device_id, sensor.sensor_id, start, end
            )
            series[metric] = [
                MetricSeriesPoint(timestamp=row.timestamp, value=row.value)
                for row in readings
            ]

        return RecentWindow(
            device_id=device_id,
            location_name=location_name,
            window_minutes=window_minutes,
            series=series,
        )

    def _resolve_api_device_id(self, device_id: str) -> int:
        api_id = self.device_api_ids.get(device_id)
        if api_id is None:
            raise SmartCitizenApiAdapterError(
                f"No API device id configured for '{device_id}'. "
                "Add it to config/device_api_ids.json."
            )
        return int(api_id)


def load_device_api_ids(path: Path | None = None) -> Dict[str, int]:
    config_path = path or DEFAULT_DEVICE_API_IDS_PATH
    if not config_path.is_file():
        raise FileNotFoundError(f"Device API id config not found: {config_path}")

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("device_api_ids.json must be a JSON object.")
    return {str(key): int(value) for key, value in raw.items()}


def load_api_metric_patterns(path: Path | None = None) -> Dict[MetricName, str]:
    config_path = path or DEFAULT_API_METRICS_PATH
    if not config_path.is_file():
        raise FileNotFoundError(f"API metrics config not found: {config_path}")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    metric_sensors = config.get("metric_sensors")
    if not isinstance(metric_sensors, dict):
        raise ValueError("api_metrics.json must contain a metric_sensors object.")

    return {
        _METRIC_NAME_BY_KEY[key]: pattern
        for key, pattern in metric_sensors.items()
        if key in _METRIC_NAME_BY_KEY
    }


def _match_sensor(sensors: List[ApiSensor], pattern: str) -> Optional[ApiSensor]:
    needle = pattern.casefold()
    for sensor in sensors:
        if needle in sensor.name.casefold():
            return sensor
    return None


def _default_unit(metric: MetricName) -> str:
    defaults = {
        MetricName.CO2: "ppm",
        MetricName.PM25: "ug/m3",
        MetricName.TEMPERATURE: "C",
        MetricName.HUMIDITY: "%",
    }
    return defaults[metric]
