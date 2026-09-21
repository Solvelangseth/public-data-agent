from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DatasetRef:
    """A catalog listing entry. Enough to fetch the full record later."""

    source_native_uri: str
    source_native_id: str | None = None
    catalog_modified: str | None = None


@dataclass(frozen=True)
class HarvestedRecord:
    """Original payload from a source adapter, before mapping."""

    source_id: str
    source_name: str
    source_endpoints: tuple[str, ...]
    ingest_reason: str
    source_native_id: str | None
    source_native_uri: str
    fetched_from: str
    payload: dict[str, Any]
    catalog_modified: str | None = None


@dataclass
class NormalizedDataset:
    """Mapped registry row. None means the source did not have the value."""

    id: str
    source_id: str
    source_native_id: str | None
    source_native_uri: str | None
    title: str | None
    title_i18n: dict[str, str]
    description: str | None
    description_i18n: dict[str, str]
    publisher_id: str | None
    publisher_name: str | None
    publisher_uri: str | None
    publisher: dict[str, Any] | None
    license: str | None
    licenses: list[str]
    access_path: str | None
    access_rights: str | None
    access_rights_uri: str | None
    issued: str | None
    modified: str | None
    temporal_start: str | None
    temporal_end: str | None
    temporal: list[dict[str, Any]]
    spatial: list[dict[str, Any]]
    media_types: list[str]
    formats: list[str]
    conforms_to: list[str]
    distributions: list[dict[str, Any]]
    landing_pages: list[str]
    ingest_reason: str
    source_name: str
    source_endpoints: tuple[str, ...]
    missing_fields: dict[str, str]
    payload_hash: str
    source_catalog_modified: str | None
    source_harvest_modified: str | None
    fetched_from: str
    payload: dict[str, Any]


@dataclass
class HarvestCounts:
    listed: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    failed: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    # Listed by the source but not harvested because they are endpoints an API
    # exposes about itself -- health checks, status pages, OGC conformance --
    # rather than data it publishes. Counted, not hidden.
    ignored: int = 0


class SourceError(Exception):
    """A source adapter failed for one record or the listing step."""
