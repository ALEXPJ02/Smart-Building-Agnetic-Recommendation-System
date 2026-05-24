from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.schemas.domain import DataSource, MetricName
from app.services.smartcitizen_api_adapter import (
    SmartCitizenApiAdapter,
    SmartCitizenApiAdapterError,
    load_api_metric_patterns,
    load_device_api_ids,
)
from app.services.smartcitizen_client import ApiReading, ApiSensor

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures" / "smartcitizen"
NOW = datetime(2025, 10, 5, 0, 0, tzinfo=timezone.utc)


def _reading(minutes_ago: int, value: float) -> ApiReading:
    return ApiReading(
        timestamp=NOW - timedelta(minutes=minutes_ago),
        value=value,
    )


@pytest.fixture
def mock_client() -> MagicMock:
    device_payload = json.loads((FIXTURES / "device_18774.json").read_text())
    client = MagicMock()
    client.list_device_sensors.return_value = [
        ApiSensor(
            sensor_id="co2-sensor",
            name="Sensirion SCD30 - CO2",
            unit="ppm",
            value=412.0,
        ),
        ApiSensor(
            sensor_id="pm-sensor",
            name="Sensirion SEN5X - PM2.5",
            unit="ug/m3",
            value=9.0,
        ),
        ApiSensor(
            sensor_id="temp-sensor",
            name="Sensirion SHT31 - Temperature",
            unit="C",
            value=22.5,
        ),
        ApiSensor(
            sensor_id="hum-sensor",
            name="Sensirion SHT31 - Humidity",
            unit="%",
            value=46.0,
        ),
    ]
    client.get_device_last_reading_at.return_value = NOW
    client.get_device.return_value = device_payload

    def readings_side_effect(api_device_id, sensor_id, start, end, **kwargs):
        values = {
            "co2-sensor": [_reading(2, 410.0), _reading(1, 412.0)],
            "pm-sensor": [_reading(2, 8.0), _reading(1, 9.0)],
            "temp-sensor": [_reading(2, 22.0), _reading(1, 22.5)],
            "hum-sensor": [_reading(2, 45.0), _reading(1, 46.0)],
        }
        return values.get(sensor_id, [])

    client.get_sensor_readings.side_effect = readings_side_effect
    return client


def test_load_device_api_ids() -> None:
    mapping = load_device_api_ids()
    assert mapping["UTS_IAQ_1"] == 18774


def test_api_adapter_load_snapshot(mock_client: MagicMock) -> None:
    adapter = SmartCitizenApiAdapter(
        client=mock_client,
        device_api_ids={"UTS_IAQ_1": 18774},
        metric_sensor_patterns=load_api_metric_patterns(),
        settings={
            "trend_window_minutes": 30,
            "trend_window_min": 15,
            "trend_window_max": 60,
        },
    )

    snapshot = adapter.load_snapshot("UTS_IAQ_1", "Simona's UTS desk")

    assert snapshot.source == DataSource.SMARTCITIZEN_API
    assert snapshot.timestamp == NOW
    assert snapshot.metrics[MetricName.CO2].value == 412.0
    mock_client.get_sensor_readings.assert_not_called()
    assert snapshot.metrics[MetricName.PM25].unit == "ug/m3"


def test_api_adapter_unknown_device_raises(mock_client: MagicMock) -> None:
    adapter = SmartCitizenApiAdapter(
        client=mock_client,
        device_api_ids={"UTS_IAQ_1": 18774},
        metric_sensor_patterns=load_api_metric_patterns(),
        settings={
            "trend_window_minutes": 30,
            "trend_window_min": 15,
            "trend_window_max": 60,
        },
    )

    with pytest.raises(SmartCitizenApiAdapterError):
        adapter.load_snapshot("UTS_IAQ_99", "Unknown")
