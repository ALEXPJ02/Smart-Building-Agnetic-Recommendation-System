from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from app.services.smartcitizen_client import SmartCitizenClient, _to_api_time


def test_list_my_devices_uses_me_endpoint_not_me_devices() -> None:
    client = SmartCitizenClient(access_token="test-token")

    with patch.object(client, "_get") as mock_get:
        mock_get.return_value = {
            "id": 1,
            "username": "tester",
            "devices": [{"id": 18774, "name": "UTS_IAQ_1"}],
        }
        devices = client.list_my_devices()

    mock_get.assert_called_once_with("me")
    assert devices == [{"id": 18774, "name": "UTS_IAQ_1"}]


def test_to_api_time_uses_z_suffix() -> None:
    value = datetime(2026, 5, 8, 7, 13, 49, tzinfo=timezone.utc)
    assert _to_api_time(value) == "2026-05-08T07:13:49Z"
