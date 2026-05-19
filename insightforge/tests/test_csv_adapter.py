from pathlib import Path

import pytest

from app.schemas.domain import DataSource, MetricName
from app.services.analysis_service import AnalysisService
from app.services.csv_adapter import (
    CsvDataAdapter,
    CsvFileNotFoundError,
    load_csv_metrics_config,
    normalize_unit,
    read_metric_csv,
)
from app.services.location_resolver import LocationResolver

SAMPLES_DIR = (
    Path(__file__).resolve().parents[1] / "data" / "samples" / "UTS_IAQ_1"
)
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config"


@pytest.fixture
def adapter() -> CsvDataAdapter:
    return CsvDataAdapter(data_dir=SAMPLES_DIR)


def test_load_csv_metrics_config() -> None:
    config = load_csv_metrics_config(CONFIG_PATH / "csv_metrics.json")
    assert config["metric_files"]["co2"] == "Sensirion_SCD30_-_CO2"


def test_normalize_temperature_unit() -> None:
    assert normalize_unit("ºC") == "C"


def test_read_metric_csv_sorts_oldest_to_newest(adapter: CsvDataAdapter) -> None:
    path = SAMPLES_DIR / "UTS_IAQ_1_Sensirion_SCD30_-_CO2.csv"
    rows = read_metric_csv(path)

    assert len(rows) == 40
    assert rows[0].timestamp < rows[-1].timestamp
    assert rows[-1].value == 397.0


def test_load_snapshot_from_sample_csv(adapter: CsvDataAdapter) -> None:
    snapshot = adapter.load_snapshot("UTS_IAQ_1", "Simona's UTS desk")

    assert snapshot.source == DataSource.CSV
    assert snapshot.device_id == "UTS_IAQ_1"
    assert snapshot.metrics[MetricName.CO2].unit == "ppm"
    assert snapshot.metrics[MetricName.PM25].unit == "ug/m3"
    assert snapshot.metrics[MetricName.TEMPERATURE].unit == "C"
    assert snapshot.metrics[MetricName.HUMIDITY].unit == "%"


def test_load_recent_window_from_sample_csv(adapter: CsvDataAdapter) -> None:
    window = adapter.load_recent_window("UTS_IAQ_1", "Simona's UTS desk", 30)

    assert window.window_minutes == 30
    assert len(window.series[MetricName.CO2]) >= 2
    assert len(window.series[MetricName.PM25]) >= 2


def test_missing_csv_raises_clear_error(adapter: CsvDataAdapter) -> None:
    with pytest.raises(CsvFileNotFoundError):
        adapter.load_snapshot("UTS_IAQ_99", "Missing device")


def test_csv_to_analysis_pipeline() -> None:
    resolver = LocationResolver.from_config(CONFIG_PATH / "location_mapping.json")
    adapter = CsvDataAdapter(data_dir=SAMPLES_DIR)
    analysis = AnalysisService()

    location = resolver.resolve("simona's desk")
    snapshot = adapter.load_snapshot(location.device_id, location.canonical_location)
    window = adapter.load_recent_window(
        location.device_id, location.canonical_location
    )
    result = analysis.analyze(snapshot, window)

    assert result.overall_status.value in {"good", "moderate", "poor"}
    assert MetricName.CO2 in result.metric_assessments
