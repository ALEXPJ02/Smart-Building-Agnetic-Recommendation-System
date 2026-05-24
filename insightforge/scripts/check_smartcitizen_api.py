#!/usr/bin/env python3
"""
Step 1 helper: verify your Smart Citizen API key and list your devices.

Run from the insightforge folder:
  python scripts/check_smartcitizen_api.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config.env import load_local_env  # noqa: E402
from app.services.smartcitizen_client import (  # noqa: E402
    SmartCitizenClient,
    SmartCitizenClientError,
)


def main() -> int:
    load_local_env()

    print("InsightForge — Smart Citizen API check")
    print("=" * 40)

    try:
        client = SmartCitizenClient.from_env()
    except SmartCitizenClientError as exc:
        print(f"\nSetup issue: {exc}")
        print("\nFix:")
        print("  1. cd insightforge")
        print("  2. cp .env.example .env")
        print("  3. Paste your API key into SMART_CITIZEN_API_KEY")
        return 1

    print(f"\nAPI base (v0): {client._v0_root}")
    print("\nFetching your account (GET /v0/me)...")

    try:
        devices = client.list_my_devices()
    except SmartCitizenClientError as exc:
        print(f"\nRequest failed: {exc}")
        return 1

    if not devices:
        print("\nNo devices returned. Check that your token has access.")
        return 1

    print(f"\nFound {len(devices)} device(s):\n")
    for device in devices:
        device_id = device.get("id", "?")
        name = device.get("name", "(no name)")
        print(f"  - id={device_id}  name={name}")

    first_id = devices[0].get("id")
    if first_id is not None:
        print(f"\nSensors on device {first_id} (GET /v0/devices/{first_id}):")
        try:
            sensors = client.list_device_sensors(int(first_id))
        except SmartCitizenClientError as exc:
            print(f"  Could not load sensors: {exc}")
            return 0

        for sensor in sensors:
            unit = f" ({sensor.unit})" if sensor.unit else ""
            print(f"  - [{sensor.sensor_id}] {sensor.name}{unit}")

    print(
        "\nNext: add mappings to config/device_api_ids.json, e.g."
        '\n  "UTS_IAQ_1": 18774'
    )
    print("Then run: pytest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
