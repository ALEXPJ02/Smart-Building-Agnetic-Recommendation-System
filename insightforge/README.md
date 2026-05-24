# InsightForge

InsightForge is the indoor air quality (IAQ) reasoning layer for the MAS Building Management project. It answers natural-language questions about a single location at a time—using live [Smart Citizen](https://smartcitizen.me/) sensor data when available, with CSV exports as a fallback.

## What it does

Given a query such as *"What is the air quality at Simona's desk?"*, InsightForge:

1. Resolves a human-friendly location to a device (`UTS_IAQ_1`, etc.)
2. Loads CO₂, PM2.5, temperature, and humidity readings
3. Classifies air quality and comfort (rule-based)
4. Assesses risk and data confidence
5. Returns recommendations and an explainability trace when requested

## Architecture

```text
User query → StubPlanner → Orchestrator
                              ├─ LocationResolver
                              ├─ Data adapter (API primary, CSV fallback)
                              ├─ AnalysisService → RiskService
                              └─ RecommendationService + ExplainabilityEngine
```

| Component | Path |
|-----------|------|
| Orchestrator | `app/core/orchestrator.py` |
| Planner (stub) | `app/agents/planner_stub.py` |
| Smart Citizen API | `app/services/smartcitizen_client.py`, `smartcitizen_api_adapter.py` |
| CSV fallback | `app/services/csv_adapter.py` |
| Location mapping | `config/location_mapping.json` |
| Device API IDs | `config/device_api_ids.json` |

## Requirements

- Python 3.12+
- A Smart Citizen API token (for live data)
- Optional: calibrated CSV exports under `SMARTCITIZEN_CSV_DIR` for offline/demo use

## Quick start

### 1. Virtual environment

```bash
cd insightforge
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment variables

```bash
cp .env.example .env
```

Edit `.env`:

| Variable | Description |
|----------|-------------|
| `SMART_CITIZEN_API_KEY` | Bearer token from Smart Citizen |
| `SMART_CITIZEN_BASE_URL` | `https://api.smartcitizen.me` (default) |
| `SMARTCITIZEN_CSV_DIR` | Optional path to calibrated CSV folder |

Never commit `.env`—it is gitignored.

### 3. Verify API access

```bash
python scripts/check_smartcitizen_api.py
```

You should see your devices listed with numeric IDs. Those IDs must appear in `config/device_api_ids.json` (keys are labels like `UTS_IAQ_1`, values are API ids like `18774`).

### 4. Run a query

```bash
python -c "
from app.config.env import load_local_env
load_local_env()
from app.core import Orchestrator

response = Orchestrator().run_query(\"What is the air quality at Simona's desk?\")
print(response.status)
print(response.current_readings)
"
```

### 5. Run tests

```bash
pytest
```

Tests use mocks and sample CSVs under `data/samples/`—no API key required for CI-style runs.

## Configuration

| File | Purpose |
|------|---------|
| `config/settings.json` | Trend window, data source primary/fallback |
| `config/location_mapping.json` | Human names and aliases → `device_id` |
| `config/device_api_ids.json` | `device_id` → Smart Citizen numeric id |
| `config/api_metrics.json` | Sensor name patterns for API mapping |
| `config/csv_metrics.json` | CSV file suffixes per metric |
| `config/rules.json` | CO₂ / PM2.5 thresholds and comfort bands |

If a sensor moves to a new room, update `location_mapping.json` only—no code change needed.

## Data sources

**Primary (live):** Smart Citizen API v0 — latest values from `GET /v0/devices/{id}`, history from `GET /v0/devices/{id}/readings`.

**Fallback:** Calibrated CSV exports (same column layout as the [smartcitizen-tools](https://github.com/Future-Mobility-Lab/smartcitizen-tools) pipeline: `timestamp`, `value`, `unit`).

Controlled by `data_source_primary` and `data_source_fallback` in `settings.json`.

## Project layout

```text
insightforge/
├── app/
│   ├── agents/          # Query planner
│   ├── core/            # Orchestrator
│   ├── services/        # Data adapters, analysis, risk, recommendations
│   └── schemas/         # Pydantic models
├── config/              # JSON configuration
├── data/
│   ├── fixtures/        # API response fixtures for tests
│   └── samples/         # Small CSV samples for e2e tests
├── docs/                # Phase notes and design packs
├── scripts/             # API connectivity check
└── tests/
```

## Related resources

- [Smart Citizen API reference](https://developer.smartcitizen.me/)
- [Future-Mobility-Lab/smartcitizen-tools](https://github.com/Future-Mobility-Lab/smartcitizen-tools) — fetch, merge, and plot toolkit

## Status

Phase 2 (data & domain modelling) — MVP pipeline operational with live API and CSV fallback. HTTP API surface (FastAPI) planned for a later phase.
