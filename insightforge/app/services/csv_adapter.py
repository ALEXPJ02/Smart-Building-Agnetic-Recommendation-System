from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

from app.schemas.domain import (
    DataSource,
    MetricName,
    MetricSeriesPoint,
    MetricValue,
    RecentWindow,
    SensorSnapshot,
)
from app.services.trend_calculator import clamp_trend_window_minutes, load_settings

DEFAULT_CSV_METRICS_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "csv_metrics.json"
)

_METRIC_NAME_BY_KEY: Dict[str, MetricName] = {
    "co2": MetricName.CO2,
    "pm25": MetricName.PM25,
    "temperature": MetricName.TEMPERATURE,
    "humidity": MetricName.HUMIDITY,
}


class CsvAdapterError(Exception):
    """Base error for CSV data adapter failures."""


class CsvFileNotFoundError(CsvAdapterError):
    """Required MVP metric CSV file is missing for a device."""


@dataclass(frozen=True)
class ParsedCsvRow:
    timestamp: datetime
    value: float
    unit: str


def load_csv_metrics_config(path: Path | None = None) -> dict:
    config_path = path or DEFAULT_CSV_METRICS_PATH
    if not config_path.is_file():
        raise FileNotFoundError(f"CSV metrics config not found: {config_path}")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config.get("metric_files"), dict):
        raise ValueError("csv_metrics.json must contain a metric_files object.")
    return config


def normalize_unit(unit: str) -> str:
    cleaned = unit.strip().replace("º", "")
    if cleaned in {"C", "c"}:
        return "C"
    return cleaned


def parse_timestamp(raw: str) -> datetime:
    parsed = datetime.fromisoformat(raw.strip())
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def read_metric_csv(path: Path) -> List[ParsedCsvRow]:
    if not path.is_file():
        raise CsvFileNotFoundError(f"CSV file not found: {path}")

    rows: List[ParsedCsvRow] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                ParsedCsvRow(
                    timestamp=parse_timestamp(row["timestamp"]),
                    value=float(row["value"]),
                    unit=normalize_unit(row["unit"]),
                )
            )

    rows.sort(key=lambda item: item.timestamp)
    return rows


def metric_csv_path(data_dir: Path, device_id: str, file_suffix: str) -> Path:
    return data_dir / f"{device_id}_{file_suffix}.csv"


class CsvDataAdapter:
    """Load Smart Citizen calibrated CSV exports into internal schemas."""

    def __init__(
        self,
        data_dir: Path,
        metrics_config: dict | None = None,
        settings: dict | None = None,
        metrics_config_path: Path | None = None,
        settings_path: Path | None = None,
    ) -> None:
        self.data_dir = data_dir
        self.metrics_config = (
            metrics_config
            if metrics_config is not None
            else load_csv_metrics_config(metrics_config_path)
        )
        self.settings = (
            settings if settings is not None else load_settings(settings_path)
        )
        self._metric_files: Dict[MetricName, str] = {
            _METRIC_NAME_BY_KEY[key]: suffix
            for key, suffix in self.metrics_config["metric_files"].items()
        }

    @classmethod
    def from_settings(
        cls,
        data_dir: Path | None = None,
        settings_path: Path | None = None,
    ) -> CsvDataAdapter:
        settings = load_settings(settings_path)
        resolved_dir = data_dir or _resolve_csv_data_dir(settings)
        if resolved_dir is None:
            raise CsvAdapterError(
                "CSV data directory is not configured. Set csv_data_dir in "
                "settings.json or SMARTCITIZEN_CSV_DIR in the environment."
            )
        return cls(resolved_dir, settings=settings, settings_path=settings_path)

    def load_snapshot(
        self, device_id: str, location_name: str
    ) -> SensorSnapshot:
        metric_rows = self._load_all_metrics(device_id)
        metrics: Dict[MetricName, MetricValue] = {}
        latest_timestamp: datetime | None = None

        for metric, rows in metric_rows.items():
            if not rows:
                continue
            latest = rows[-1]
            metrics[metric] = MetricValue(value=latest.value, unit=latest.unit)
            if latest_timestamp is None or latest.timestamp > latest_timestamp:
                latest_timestamp = latest.timestamp

        if latest_timestamp is None:
            raise CsvAdapterError(f"No CSV readings found for device '{device_id}'.")

        return SensorSnapshot(
            device_id=device_id,
            location_name=location_name,
            timestamp=latest_timestamp,
            source=DataSource.CSV,
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
        metric_rows = self._load_all_metrics(device_id)

        end_time = max(rows[-1].timestamp for rows in metric_rows.values() if rows)
        start_time = end_time - timedelta(minutes=window_minutes)

        series: Dict[MetricName, List[MetricSeriesPoint]] = {}
        for metric, rows in metric_rows.items():
            points = [
                MetricSeriesPoint(timestamp=row.timestamp, value=row.value)
                for row in rows
                if start_time <= row.timestamp <= end_time
            ]
            series[metric] = points

        return RecentWindow(
            device_id=device_id,
            location_name=location_name,
            window_minutes=window_minutes,
            series=series,
        )

    def _load_all_metrics(
        self, device_id: str
    ) -> Dict[MetricName, List[ParsedCsvRow]]:
        loaded: Dict[MetricName, List[ParsedCsvRow]] = {}
        for metric, suffix in self._metric_files.items():
            path = metric_csv_path(self.data_dir, device_id, suffix)
            loaded[metric] = read_metric_csv(path)
        return loaded


def _resolve_csv_data_dir(settings: dict) -> Path | None:
    env_dir = os.environ.get("SMARTCITIZEN_CSV_DIR")
    if env_dir:
        return Path(env_dir)

    configured = settings.get("csv_data_dir")
    if configured:
        return Path(configured)
    return None
