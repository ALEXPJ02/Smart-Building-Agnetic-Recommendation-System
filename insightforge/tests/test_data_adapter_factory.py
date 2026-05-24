from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.services.csv_adapter import CsvDataAdapter
from app.services.data_adapter_factory import build_data_adapter
from app.services.smartcitizen_api_adapter import SmartCitizenApiAdapter

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "data" / "samples" / "UTS_IAQ_1"


def test_factory_falls_back_to_csv_when_api_unavailable() -> None:
    settings = {
        "data_source_primary": "smartcitizen_api",
        "data_source_fallback": "csv",
        "trend_window_minutes": 30,
        "trend_window_min": 15,
        "trend_window_max": 60,
    }

    with patch(
        "app.services.data_adapter_factory.SmartCitizenApiAdapter.from_env",
        side_effect=ValueError("no api key"),
    ):
        adapter = build_data_adapter(settings, csv_data_dir=SAMPLES_DIR)

    assert isinstance(adapter, CsvDataAdapter)


def test_factory_uses_api_when_available() -> None:
    settings = {
        "data_source_primary": "smartcitizen_api",
        "data_source_fallback": "csv",
    }
    fake_adapter = object()

    with patch(
        "app.services.data_adapter_factory.SmartCitizenApiAdapter.from_env",
        return_value=fake_adapter,
    ):
        adapter = build_data_adapter(settings)

    assert adapter is fake_adapter
