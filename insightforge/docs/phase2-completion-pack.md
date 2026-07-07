## Phase 2 Completion Pack

## Current Phase
Phase 2: Data and Domain Modelling

## Locked MVP
InsightForge MVP answers one-location indoor air quality queries using Smart Citizen sensor data.

## Data Source
Primary: Smart Citizen API  
Fallback: CSV export / cached dataset

## Metrics
Primary:
- CO2
- PM2.5

Context:
- Temperature
- Humidity

## Location Handling
Smart Citizen device names such as UTS_IAQ_1 are technical identifiers only.

Human-friendly location names are mapped through `config/location_mapping.json`.

Sensors are movable. If a device moves, update the JSON mapping rather than changing code.

## Trend Logic
Trend window is configurable between 15 and 60 minutes.  
Default: 30 minutes.

Trend is used for explanation support, not primary classification.

## Rule Model
CO2 and PM2.5 drive air quality classification.  
Temperature and humidity add comfort/context notes.

## Phase 2 Remaining Before Coding Phase 3
- Replace example location mappings with real sensor locations
- Confirm Smart Citizen API response structure
- Add sample API response file
- Add mock adapter for local testing
