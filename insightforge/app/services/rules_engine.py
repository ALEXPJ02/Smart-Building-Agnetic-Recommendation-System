from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Tuple

from app.schemas.domain import MetricName, SensorSnapshot, StatusLevel
from app.schemas.response import MetricAssessment

DEFAULT_RULES_PATH = Path(__file__).resolve().parents[2] / "config" / "rules.json"

PRIMARY_METRICS = (MetricName.CO2, MetricName.PM25)
CONTEXT_METRICS = (MetricName.TEMPERATURE, MetricName.HUMIDITY)

_METRIC_RULE_KEYS: Dict[MetricName, str] = {
    MetricName.CO2: "co2",
    MetricName.PM25: "pm25",
    MetricName.TEMPERATURE: "temperature",
    MetricName.HUMIDITY: "humidity",
}

_STATUS_RANK = {
    StatusLevel.GOOD: 0,
    StatusLevel.MODERATE: 1,
    StatusLevel.POOR: 2,
    StatusLevel.COMFORTABLE: 0,
    StatusLevel.OUT_OF_COMFORT_BAND: 1,
    StatusLevel.UNKNOWN: -1,
}


def load_rules(path: Path | None = None) -> dict:
    rules_path = path or DEFAULT_RULES_PATH
    if not rules_path.is_file():
        raise FileNotFoundError(f"Rules file not found: {rules_path}")

    rules = json.loads(rules_path.read_text(encoding="utf-8"))
    if not isinstance(rules, dict):
        raise ValueError("Rules file must contain a JSON object.")
    return rules


def classify_primary(
    value: float, rules: dict, metric_key: str
) -> Tuple[StatusLevel, str]:
    metric_rules = rules[metric_key]
    unit = metric_rules["unit"]
    good_max = metric_rules["good_max"]
    moderate_max = metric_rules["moderate_max"]

    label = metric_key.upper()
    if value <= good_max:
        status = StatusLevel.GOOD
        reason = (
            f"{label} at {value:g} {unit} is good (at or below {good_max:g} {unit})."
        )
    elif value <= moderate_max:
        status = StatusLevel.MODERATE
        reason = (
            f"{label} at {value:g} {unit} is moderate "
            f"({good_max:g}–{moderate_max:g} {unit})."
        )
    else:
        status = StatusLevel.POOR
        reason = (
            f"{label} at {value:g} {unit} is poor "
            f"(above {moderate_max:g} {unit})."
        )

    return status, reason


def classify_comfort(
    value: float, rules: dict, metric_key: str
) -> Tuple[StatusLevel, str]:
    metric_rules = rules[metric_key]
    unit = metric_rules["unit"]
    comfort_min = metric_rules["comfort_min"]
    comfort_max = metric_rules["comfort_max"]
    label = metric_key.capitalize()

    if comfort_min <= value <= comfort_max:
        status = StatusLevel.COMFORTABLE
        reason = (
            f"{label} at {value:g}{unit} is within the comfort band "
            f"({comfort_min:g}–{comfort_max:g}{unit})."
        )
    else:
        status = StatusLevel.OUT_OF_COMFORT_BAND
        reason = (
            f"{label} at {value:g}{unit} is outside the comfort band "
            f"({comfort_min:g}–{comfort_max:g}{unit})."
        )

    return status, reason


def overall_status(primary_statuses: Dict[MetricName, StatusLevel]) -> StatusLevel:
    statuses = [
        primary_statuses[metric]
        for metric in PRIMARY_METRICS
        if metric in primary_statuses
        and primary_statuses[metric] != StatusLevel.UNKNOWN
    ]
    if not statuses:
        return StatusLevel.UNKNOWN

    return max(statuses, key=lambda status: _STATUS_RANK[status])


def assess_snapshot(
    snapshot: SensorSnapshot, rules: dict
) -> Dict[MetricName, MetricAssessment]:
    assessments: Dict[MetricName, MetricAssessment] = {}

    for metric in MetricName:
        rule_key = _METRIC_RULE_KEYS[metric]
        reading = snapshot.metrics.get(metric)
        if reading is None:
            assessments[metric] = MetricAssessment(
                metric=metric,
                value=0.0,
                unit=rules[rule_key]["unit"],
                status=StatusLevel.UNKNOWN,
                reason=f"{rule_key.upper()} reading is missing.",
            )
            continue

        if metric in PRIMARY_METRICS:
            status, reason = classify_primary(reading.value, rules, rule_key)
        else:
            status, reason = classify_comfort(reading.value, rules, rule_key)

        assessments[metric] = MetricAssessment(
            metric=metric,
            value=reading.value,
            unit=reading.unit or rules[rule_key]["unit"],
            status=status,
            reason=reason,
        )

    return assessments
