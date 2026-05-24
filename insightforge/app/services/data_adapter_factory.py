from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

from app.config.env import load_local_env
from app.services.csv_adapter import CsvAdapterError, CsvDataAdapter
from app.services.smartcitizen_api_adapter import (
    SmartCitizenApiAdapter,
    SmartCitizenApiAdapterError,
)

logger = logging.getLogger(__name__)

DataAdapter = Union[CsvDataAdapter, SmartCitizenApiAdapter]


def build_data_adapter(settings: dict, csv_data_dir: Path | None = None) -> DataAdapter:
    """Pick API or CSV adapter using settings.json primary/fallback flags."""
    primary = settings.get("data_source_primary", "csv")
    fallback = settings.get("data_source_fallback")

    if primary == "smartcitizen_api":
        load_local_env()
        try:
            return SmartCitizenApiAdapter.from_env(settings=settings)
        except (SmartCitizenApiAdapterError, FileNotFoundError, ValueError) as exc:
            logger.warning("Smart Citizen API adapter unavailable: %s", exc)
            if fallback == "csv":
                return _build_csv_adapter(settings, csv_data_dir)
            raise

    return _build_csv_adapter(settings, csv_data_dir)


def _build_csv_adapter(settings: dict, csv_data_dir: Path | None) -> CsvDataAdapter:
    if csv_data_dir is not None:
        return CsvDataAdapter(data_dir=csv_data_dir, settings=settings)
    return CsvDataAdapter.from_settings(settings_path=None)
