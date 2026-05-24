from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests

from app.services.csv_adapter import normalize_unit, parse_timestamp


class SmartCitizenClientError(Exception):
    """HTTP or parsing failure when talking to the Smart Citizen API."""


@dataclass(frozen=True)
class ApiSensor:
    sensor_id: str
    name: str
    unit: str
    value: Optional[float] = None


@dataclass(frozen=True)
class ApiReading:
    timestamp: datetime
    value: float


def api_v0_base_url(raw_base_url: str) -> str:
    base = raw_base_url.rstrip("/")
    if base.endswith("/v0"):
        return base
    return f"{base}/v0"


@dataclass
class SmartCitizenClient:
    """Thin wrapper around Smart Citizen REST endpoints used by InsightForge."""

    access_token: str
    base_url: str = "https://api.smartcitizen.me"
    timeout_seconds: int = 30

    @classmethod
    def from_env(cls) -> SmartCitizenClient:
        token = os.environ.get("SMART_CITIZEN_API_KEY", "").strip()
        if not token:
            raise SmartCitizenClientError(
                "SMART_CITIZEN_API_KEY is not set. Copy .env.example to .env and add your token."
            )
        base_url = os.environ.get(
            "SMART_CITIZEN_BASE_URL", "https://api.smartcitizen.me"
        ).strip()
        return cls(access_token=token, base_url=base_url)

    @property
    def _v0_root(self) -> str:
        return api_v0_base_url(self.base_url)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = urljoin(f"{self._v0_root}/", path.lstrip("/"))
        try:
            response = requests.get(
                url,
                headers=self._headers(),
                params=params,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SmartCitizenClientError(f"GET {url} failed: {exc}") from exc

        try:
            return response.json()
        except ValueError as exc:
            raise SmartCitizenClientError(f"GET {url} returned non-JSON body.") from exc

    def get_current_user(self) -> Dict[str, Any]:
        """GET /v0/me — current user profile (includes owned devices)."""
        payload = self._get("me")
        if not isinstance(payload, dict):
            raise SmartCitizenClientError("me did not return a JSON object.")
        return payload

    def list_my_devices(self) -> List[Dict[str, Any]]:
        """Devices owned by the authenticated user (from GET /v0/me)."""
        user = self.get_current_user()
        devices = user.get("devices")
        if not isinstance(devices, list):
            raise SmartCitizenClientError(
                "me response has no devices list. Check your API token."
            )
        return devices

    def get_device(self, api_device_id: int) -> Dict[str, Any]:
        return self._get(f"devices/{api_device_id}")

    def list_device_sensors(self, api_device_id: int) -> List[ApiSensor]:
        payload = self.get_device(api_device_id)
        return _parse_device_sensors(payload)

    def get_device_last_reading_at(self, api_device_id: int) -> Optional[datetime]:
        payload = self.get_device(api_device_id)
        last_at = payload.get("last_reading_at")
        if not last_at:
            return None
        return parse_timestamp(str(last_at))

    def get_sensor_readings(
        self,
        api_device_id: int,
        sensor_id: str,
        start: datetime,
        end: datetime,
        *,
        rollup: str = "1m",
        function: str = "avg",
    ) -> List[ApiReading]:
        params = {
            "sensor_id": sensor_id,
            "from": _to_api_time(start),
            "to": _to_api_time(end),
            "rollup": rollup,
            "function": function,
        }
        payload = self._get(f"devices/{api_device_id}/readings", params=params)
        readings = payload.get("readings")
        if not isinstance(readings, list):
            return []

        parsed: List[ApiReading] = []
        for item in readings:
            point = _parse_reading_item(item)
            if point is not None:
                parsed.append(point)
        parsed.sort(key=lambda row: row.timestamp)
        return parsed


def _parse_device_sensors(payload: Dict[str, Any]) -> List[ApiSensor]:
    raw_sensors: List[Dict[str, Any]] = []
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("sensors"), list):
        raw_sensors = data["sensors"]
    elif isinstance(payload.get("sensors"), list):
        raw_sensors = payload["sensors"]

    sensors: List[ApiSensor] = []
    for item in raw_sensors:
        sensor_id = item.get("id")
        if sensor_id is None:
            continue
        raw_value = item.get("value")
        sensors.append(
            ApiSensor(
                sensor_id=str(sensor_id),
                name=str(item.get("name", f"Sensor_{sensor_id}")),
                unit=normalize_unit(str(item.get("unit", ""))),
                value=float(raw_value) if raw_value is not None else None,
            )
        )
    return sensors


def _to_api_time(value: datetime) -> str:
    """Smart Citizen expects UTC timestamps with a Z suffix, not +00:00."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    utc = value.astimezone(timezone.utc)
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_reading_item(item: Any) -> Optional[ApiReading]:
    if isinstance(item, list) and len(item) >= 2:
        timestamp_raw, value_raw = item[0], item[1]
    elif isinstance(item, dict):
        timestamp_raw = item.get("recorded_at") or item.get("timestamp")
        value_raw = item.get("value")
    else:
        return None

    if timestamp_raw is None or value_raw is None:
        return None

    if isinstance(timestamp_raw, (int, float)):
        timestamp = datetime.fromtimestamp(timestamp_raw, tz=timezone.utc)
    else:
        timestamp = parse_timestamp(str(timestamp_raw))

    return ApiReading(timestamp=timestamp, value=float(value_raw))
