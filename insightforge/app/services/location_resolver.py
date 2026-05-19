from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from app.schemas.domain import LocationMappingEntry, LocationResolution

DEFAULT_MAPPING_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "location_mapping.json"
)


class LocationResolverError(Exception):
    """Base error for location resolution failures."""


class LocationNotFoundError(LocationResolverError):
    """No active mapping matches the provided location text."""


class AmbiguousLocationError(LocationResolverError):
    """Multiple active mappings match the provided location text."""


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


class LocationResolver:
    """Resolve human location text to a device ID using config JSON."""

    def __init__(self, entries: List[LocationMappingEntry]) -> None:
        self._entries = entries
        self._by_device: Dict[str, LocationMappingEntry] = {}
        self._by_canonical: Dict[str, LocationMappingEntry] = {}
        self._by_alias: Dict[str, List[LocationMappingEntry]] = {}
        self._build_indexes()

    @classmethod
    def from_config(cls, path: Path | None = None) -> LocationResolver:
        mapping_path = path or DEFAULT_MAPPING_PATH
        entries = load_location_mappings(mapping_path)
        return cls(entries)

    def resolve(self, location_text: str) -> LocationResolution:
        if not location_text or not location_text.strip():
            raise LocationNotFoundError("Location text is empty.")

        normalized = _normalize(location_text)

        match = (
            self._match_device_id(normalized)
            or self._match_canonical(normalized)
            or self._match_alias(normalized)
        )
        if match is None:
            raise LocationNotFoundError(
                f"No active location mapping found for '{location_text}'."
            )

        entry, match_type = match
        return LocationResolution(
            input_text=location_text,
            canonical_location=entry.location_name,
            device_id=entry.device_id,
            match_type=match_type,
        )

    def _build_indexes(self) -> None:
        for entry in self._entries:
            if not entry.active:
                continue

            device_key = _normalize(entry.device_id)
            if device_key in self._by_device:
                raise ValueError(f"Duplicate active device_id: {entry.device_id}")
            self._by_device[device_key] = entry

            canonical_key = _normalize(entry.location_name)
            if canonical_key in self._by_canonical:
                raise ValueError(
                    f"Duplicate active location_name: {entry.location_name}"
                )
            self._by_canonical[canonical_key] = entry

            for alias in entry.aliases:
                alias_key = _normalize(alias)
                if not alias_key:
                    continue
                self._by_alias.setdefault(alias_key, []).append(entry)

        for alias_key, matches in self._by_alias.items():
            device_ids = {entry.device_id for entry in matches}
            if len(device_ids) > 1:
                names = ", ".join(sorted(entry.location_name for entry in matches))
                raise ValueError(
                    f"Ambiguous alias '{alias_key}' maps to multiple locations: {names}"
                )

    def _match_device_id(
        self, normalized: str
    ) -> tuple[LocationMappingEntry, str] | None:
        entry = self._by_device.get(normalized)
        if entry is None:
            return None
        return entry, "device_id"

    def _match_canonical(
        self, normalized: str
    ) -> tuple[LocationMappingEntry, str] | None:
        entry = self._by_canonical.get(normalized)
        if entry is None:
            return None
        return entry, "canonical"

    def _match_alias(
        self, normalized: str
    ) -> tuple[LocationMappingEntry, str] | None:
        matches = self._by_alias.get(normalized, [])
        if not matches:
            return None
        if len(matches) > 1:
            names = ", ".join(entry.location_name for entry in matches)
            raise AmbiguousLocationError(
                f"Alias '{normalized}' matches multiple locations: {names}"
            )
        return matches[0], "alias"


def load_location_mappings(path: Path) -> List[LocationMappingEntry]:
    if not path.is_file():
        raise FileNotFoundError(f"Location mapping file not found: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Location mapping file must contain a JSON array.")

    return [LocationMappingEntry.model_validate(entry) for entry in raw]
