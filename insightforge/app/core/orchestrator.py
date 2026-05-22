from __future__ import annotations

from pathlib import Path

from app.agents.planner_stub import StubPlanner
from app.schemas.domain import MetricName
from app.schemas.planner import IntentType, PlannerOutput
from app.schemas.response import FinalResponse, RecommendationResult
from app.services.analysis_service import AnalysisService
from app.services.csv_adapter import CsvAdapterError, CsvDataAdapter, CsvFileNotFoundError
from app.services.explainability_engine import ExplainabilityEngine
from app.services.location_resolver import (
    AmbiguousLocationError,
    LocationNotFoundError,
    LocationResolver,
)
from app.services.recommendation_service import RecommendationService
from app.services.risk_service import RiskService
from app.services.trend_calculator import clamp_trend_window_minutes, load_settings


class OrchestratorError(Exception):
    """Raised when the orchestrated pipeline cannot complete."""


class Orchestrator:
    """Central controller: validate plan, run agents, compose FinalResponse."""

    def __init__(
        self,
        location_resolver: LocationResolver | None = None,
        data_adapter: CsvDataAdapter | None = None,
        analysis_service: AnalysisService | None = None,
        risk_service: RiskService | None = None,
        recommendation_service: RecommendationService | None = None,
        explainability_engine: ExplainabilityEngine | None = None,
        csv_data_dir: Path | None = None,
    ) -> None:
        self.settings = load_settings()
        self.location_resolver = location_resolver or LocationResolver.from_config()
        self.data_adapter = data_adapter or self._build_data_adapter(csv_data_dir)
        self.analysis_service = analysis_service or AnalysisService()
        self.risk_service = risk_service or RiskService()
        self.recommendation_service = (
            recommendation_service or RecommendationService()
        )
        self.explainability_engine = (
            explainability_engine or ExplainabilityEngine()
        )
        self.stub_planner = StubPlanner()

    def run_query(self, query: str) -> FinalResponse:
        """End-to-end entry point using the deterministic stub planner."""
        plan = self.stub_planner.plan(query)
        return self.run(query=query, plan=plan)

    def run(self, query: str, plan: PlannerOutput) -> FinalResponse:
        self._validate_plan(plan)

        try:
            location = self.location_resolver.resolve(plan.location_text)
            snapshot = self.data_adapter.load_snapshot(
                location.device_id, location.canonical_location
            )
            window = self.data_adapter.load_recent_window(
                location.device_id,
                location.canonical_location,
                window_minutes=clamp_trend_window_minutes(
                    plan.trend_window_minutes, self.settings
                ),
            )
            analysis = self.analysis_service.analyze(snapshot, window)
            risk = self.risk_service.assess(
                snapshot,
                analysis,
                window,
                reference_time=snapshot.timestamp,
            )

            if plan.requires_recommendation:
                recommendation = self.recommendation_service.recommend(
                    analysis,
                    risk,
                    location_name=location.canonical_location,
                )
            else:
                recommendation = _empty_recommendation(analysis.overall_status.value)

            if plan.requires_explanation:
                explainability = self.explainability_engine.build_trace(
                    query=query,
                    location=location,
                    snapshot=snapshot,
                    analysis=analysis,
                    risk=risk,
                    recommendation=recommendation,
                )
            else:
                explainability = list(analysis.reason_summary)

            return FinalResponse(
                query=query,
                location=location,
                status={
                    "overall": analysis.overall_status.value,
                    "confidence": risk.confidence.value,
                    "data_quality": risk.data_quality_status,
                },
                current_readings=snapshot.metrics,
                analysis=analysis,
                risk=risk,
                recommendation=recommendation,
                explainability=explainability,
            )
        except LocationNotFoundError as exc:
            raise OrchestratorError(
                f"Could not resolve location '{plan.location_text}': {exc}"
            ) from exc
        except AmbiguousLocationError as exc:
            raise OrchestratorError(
                f"Ambiguous location '{plan.location_text}': {exc}"
            ) from exc
        except CsvFileNotFoundError as exc:
            raise OrchestratorError(
                f"Sensor data unavailable for resolved device: {exc}"
            ) from exc
        except CsvAdapterError as exc:
            raise OrchestratorError(f"Data adapter failure: {exc}") from exc

    def _validate_plan(self, plan: PlannerOutput) -> None:
        allowed_intents = {intent for intent in IntentType}
        if plan.intent not in allowed_intents:
            raise OrchestratorError(f"Unsupported intent: {plan.intent}")

        if not plan.location_text.strip():
            raise OrchestratorError("Planner output location_text is empty.")

        allowed_metrics = {metric for metric in MetricName}
        unknown = [
            metric for metric in plan.canonical_metrics if metric not in allowed_metrics
        ]
        if unknown:
            names = ", ".join(metric.value for metric in unknown)
            raise OrchestratorError(f"Unsupported metrics in plan: {names}")

    def _build_data_adapter(self, csv_data_dir: Path | None) -> CsvDataAdapter:
        if csv_data_dir is not None:
            return CsvDataAdapter(data_dir=csv_data_dir)
        return CsvDataAdapter.from_settings()


def _empty_recommendation(overall_status: str) -> RecommendationResult:
    return RecommendationResult(
        summary=f"No recommendation requested; overall status is {overall_status}.",
        actions=[],
        rationale="Recommendation step was disabled in the planner output.",
    )
