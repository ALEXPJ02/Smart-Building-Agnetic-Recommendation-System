from pathlib import Path

import pytest

from app.services.location_resolver import (
    AmbiguousLocationError,
    LocationNotFoundError,
    LocationResolver,
    load_location_mappings,
)
from app.schemas.domain import LocationMappingEntry

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "location_mapping.json"


@pytest.fixture
def resolver() -> LocationResolver:
    return LocationResolver.from_config(CONFIG_PATH)


def test_resolve_by_device_id_case_insensitive(resolver: LocationResolver) -> None:
    result = resolver.resolve("uts_iaq_11")

    assert result.device_id == "UTS_IAQ_11"
    assert result.canonical_location == "Big Kitchen Level 11"
    assert result.match_type == "device_id"
    assert result.input_text == "uts_iaq_11"


def test_resolve_by_canonical_name(resolver: LocationResolver) -> None:
    result = resolver.resolve("Reception Office Level 12")

    assert result.device_id == "UTS_IAQ_7"
    assert result.match_type == "canonical"


def test_resolve_by_alias_case_insensitive() -> None:
    """Alias matching uses an in-memory mapping so this test does not depend on config aliases."""
    resolver = LocationResolver(
        [
            LocationMappingEntry(
                device_id="UTS_IAQ_11",
                location_name="Big Kitchen Level 11",
                aliases=["Big Kitchen"],
                active=True,
            )
        ]
    )
    result = resolver.resolve("  big kitchen  ")

    assert result.device_id == "UTS_IAQ_11"
    assert result.match_type == "alias"


def test_resolve_unknown_location(resolver: LocationResolver) -> None:
    with pytest.raises(LocationNotFoundError):
        resolver.resolve("nonexistent room")


def test_resolve_empty_location(resolver: LocationResolver) -> None:
    with pytest.raises(LocationNotFoundError):
        resolver.resolve("   ")


def test_inactive_sensor_is_not_resolvable() -> None:
    entries = [
        LocationMappingEntry(
            device_id="UTS_IAQ_99",
            location_name="Closed Room",
            aliases=["closed"],
            active=False,
        )
    ]
    resolver = LocationResolver(entries)

    with pytest.raises(LocationNotFoundError):
        resolver.resolve("closed")


def test_ambiguous_alias_at_runtime() -> None:
    entries = [
        LocationMappingEntry(
            device_id="UTS_IAQ_A",
            location_name="Room A",
            aliases=["shared"],
            active=True,
        ),
        LocationMappingEntry(
            device_id="UTS_IAQ_B",
            location_name="Room B",
            aliases=["shared"],
            active=True,
        ),
    ]

    with pytest.raises(ValueError, match="Ambiguous alias"):
        LocationResolver(entries)


def test_load_location_mappings_from_config() -> None:
    entries = load_location_mappings(CONFIG_PATH)

    assert len(entries) >= 1
    assert all(isinstance(entry, LocationMappingEntry) for entry in entries)


@pytest.mark.parametrize(
    ("query", "expected_device_id", "expected_match_type"),
    [
        ("reception", "UTS_IAQ_7", "alias"),
        ("big kitchen", "UTS_IAQ_11", "alias"),
        ("simona's desk", "UTS_IAQ_1", "alias"),
        ("home office", "UTS_IAQ_2", "alias"),
        ("meeting room", "UTS_IAQ_3", "alias"),
        ("large meeting room", "UTS_IAQ_8", "alias"),
        ("printer", "UTS_IAQ_10", "alias"),
        ("garage", "UTS_IAQ_9", "alias"),
    ],
)
def test_resolve_aliases_from_project_config(
    resolver: LocationResolver,
    query: str,
    expected_device_id: str,
    expected_match_type: str,
) -> None:
    """Uses aliases from config/location_mapping.json — fails if config changes without updating this test."""
    result = resolver.resolve(query)

    assert result.device_id == expected_device_id
    assert result.match_type == expected_match_type
