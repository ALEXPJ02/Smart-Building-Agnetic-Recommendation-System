from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Tuple

from app.schemas.domain import MetricName
from app.schemas.planner import IntentType, PlannerOutput

DEFAULT_MAPPING_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "location_mapping.json"
)

_RECOMMENDATION_HINTS = (
    "improve",
    "what should",
    "what can i do",
    "recommend",
    "suggest",
    "fix",
)
_EXPLANATION_HINTS = ("why", "explain", "reason", "cause")


class StubPlanner:
    """
    Deterministic stand-in for the LLM Planner Agent.

    Uses keyword rules and location_mapping aliases — not for production NLU.
    """

    def __init__(self, mapping_path: Path | None = None) -> None:
        path = mapping_path or DEFAULT_MAPPING_PATH
        raw = json.loads(path.read_text(encoding="utf-8"))
        self._location_candidates: List[Tuple[str, str]] = []
        for entry in raw:
            if not entry.get("active", True):
                continue
            canonical = entry["location_name"]
            self._location_candidates.append((canonical.lower(), canonical))
            for alias in entry.get("aliases", []):
                if alias:
                    self._location_candidates.append((alias.lower(), canonical))
        self._location_candidates.sort(key=lambda item: len(item[0]), reverse=True)

    def plan(self, query: str) -> PlannerOutput:
        if not query or not query.strip():
            raise ValueError("Query must not be empty.")

        normalized_query = _normalize(query)
        location_text = self._extract_location_text(normalized_query, query)
        intent = self._infer_intent(normalized_query)

        return PlannerOutput(
            intent=intent,
            location_text=location_text,
            requires_explanation=True,
            requires_recommendation=intent
            == IntentType.AIR_QUALITY_RECOMMENDATION,
        )

    def _extract_location_text(self, normalized_query: str, original_query: str) -> str:
        for candidate, canonical in self._location_candidates:
            if candidate in normalized_query:
                return canonical

        for pattern in (
            r"(?:in|at|for)\s+(.+?)(?:\?|$)",
            r"(?:air quality in|air quality at|air quality for)\s+(.+?)(?:\?|$)",
        ):
            match = re.search(pattern, normalized_query)
            if match:
                extracted = match.group(1).strip(" ?.,")
                if extracted:
                    return extracted

        return original_query.strip()

    def _infer_intent(self, normalized_query: str) -> IntentType:
        if any(hint in normalized_query for hint in _RECOMMENDATION_HINTS):
            return IntentType.AIR_QUALITY_RECOMMENDATION
        if any(hint in normalized_query for hint in _EXPLANATION_HINTS):
            return IntentType.AIR_QUALITY_EXPLANATION
        return IntentType.AIR_QUALITY_ASSESSMENT


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())
