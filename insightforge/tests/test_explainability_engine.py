from datetime import datetime, timezone
from pathlib import Path

from app.schemas.domain import (
    ConfidenceLevel,
    DataSource,
    LocationResolution,
    MetricName,
    MetricValue,
    SensorSnapshot,
    StatusLevel,
    TrendDirection,
)
from app.schemas.response import (
    AnalysisResult,
    MetricAssessment,
    RecommendationResult,
    RiskAssessment,
    TrendResult,
)
from app.services import (
    AnalysisService,
    CsvDataAdapter,
    ExplainabilityEngine,
    LocationResolver,
    RecommendationService,
    RiskService,
)

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "data" / "samples" / "UTS_IAQ_1"
CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def test_build_trace_from_full_pipeline() -> None:
    resolver = LocationResolver.from_config(CONFIG_DIR / "location_mapping.json")
    adapter = CsvDataAdapter(data_dir=SAMPLES_DIR)
    analysis_svc = AnalysisService()
    risk_svc = RiskService()
    recommendation_svc = RecommendationService()
    engine = ExplainabilityEngine()

    location = resolver.resolve("simona's desk")
    snapshot = adapter.load_snapshot(location.device_id, location.canonical_location)
    window = adapter.load_recent_window(location.device_id, location.canonical_location)
    analysis = analysis_svc.analyze(snapshot, window)
    risk = risk_svc.assess(snapshot, analysis, window, reference_time=snapshot.timestamp)
    recommendation = recommendation_svc.recommend(
        analysis, risk, location_name=location.canonical_location
    )

    trace = engine.build_trace(
        query="What is the air quality at Simona's desk?",
        location=location,
        snapshot=snapshot,
        analysis=analysis,
        risk=risk,
        recommendation=recommendation,
    )

    assert trace[0].startswith("Query:")
    assert any("Location resolution" in line for line in trace)
    assert any("Data provenance" in line for line in trace)
    assert any("Triggered rules" in line for line in trace)
    assert any("Trend analysis" in line for line in trace)
    assert any("Risk and confidence" in line for line in trace)
    assert any("Recommendation rationale" in line for line in trace)
    assert any("CO2" in line for line in trace)


def test_trace_includes_risk_flags_when_present() -> None:
    engine = ExplainabilityEngine()
    location = LocationResolution(
        input_text="desk",
        canonical_location="Simona's UTS desk",
        device_id="UTS_IAQ_1",
        match_type="alias",
    )
    snapshot_time = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    snapshot = SensorSnapshot(
        device_id="UTS_IAQ_1",
        location_name="Simona's UTS desk",
        timestamp=snapshot_time,
        source=DataSource.MOCK,
        metrics={
            MetricName.CO2: MetricValue(value=900, unit="ppm"),
        },
    )
    analysis = AnalysisResult(
        overall_status=StatusLevel.MODERATE,
        metric_assessments={
            MetricName.CO2: MetricAssessment(
                metric=MetricName.CO2,
                value=900,
                unit="ppm",
                status=StatusLevel.MODERATE,
                reason="CO2 at 900 ppm is in the moderate range (800–1200 ppm).",
            )
        },
        trend=TrendResult(
            window_minutes=30,
            trends={MetricName.CO2: TrendDirection.STABLE},
        ),
        reason_summary=["Overall air quality status is moderate."],
    )
    risk = RiskAssessment(
        confidence=ConfidenceLevel.LOW,
        flags=["stale_data", "missing_metric:pm25"],
        data_quality_status="poor",
    )
    recommendation = RecommendationResult(
        summary="Air quality is moderate.",
        actions=["Increase ventilation."],
        rationale="Moderate CO2 levels.",
    )

    trace = engine.build_trace(
        query="Why is air quality moderate?",
        location=location,
        snapshot=snapshot,
        analysis=analysis,
        risk=risk,
        recommendation=recommendation,
    )

    joined = "\n".join(trace)
    assert "stale_data" in joined
    assert "missing_metric:pm25" in joined
    assert "1. Increase ventilation." in joined
