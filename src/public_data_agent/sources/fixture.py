from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from public_data_agent.models import DatasetRef, HarvestedRecord
from public_data_agent.sources.base import SourceBase

INGEST_REASON = "listed in the local fixture catalog used by tests"


class FixtureSource(SourceBase):
    """In-process catalog for tests and CI. Same adapter shape as Data.norge."""

    source_id = "fixture"
    source_name = "Fixture catalog"
    endpoints = ("file://fixtures",)
    ingest_reason = INGEST_REASON

    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self._payloads = list(payloads)

    @classmethod
    def from_directory(cls, directory: Path) -> FixtureSource:
        files = sorted(directory.glob("*.json"))
        if not files:
            raise FileNotFoundError(f"no JSON fixtures in {directory}")
        payloads = [json.loads(path.read_text(encoding="utf-8")) for path in files]
        return cls(payloads)

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        refs = [_ref_from_payload(payload) for payload in self._payloads]
        end = None if limit is None else offset + limit
        return refs[offset:end]

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        for payload in self._payloads:
            if payload.get("uri") == ref.source_native_uri or payload.get("id") == ref.source_native_id:
                return self._record(payload, ref)
        raise KeyError(f"fixture has no dataset {ref.source_native_uri}")

    def fetch_many(self, refs: Iterable[DatasetRef]) -> list[HarvestedRecord]:
        return [self.fetch_dataset(ref) for ref in refs]

    def _record(self, payload: dict[str, Any], ref: DatasetRef) -> HarvestedRecord:
        harvest = payload.get("harvest") if isinstance(payload.get("harvest"), dict) else {}
        catalog_modified = ref.catalog_modified or harvest.get("modified")
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=payload.get("id") or ref.source_native_id,
            source_native_uri=payload.get("uri") or ref.source_native_uri,
            fetched_from=f"file://fixtures/{payload.get('id') or 'unknown'}",
            payload=payload,
            catalog_modified=catalog_modified,
        )


def _ref_from_payload(payload: dict[str, Any]) -> DatasetRef:
    uri = payload.get("uri")
    if not isinstance(uri, str) or not uri:
        raise ValueError("fixture payload is missing uri")
    harvest = payload.get("harvest") if isinstance(payload.get("harvest"), dict) else {}
    native_id = payload.get("id")
    return DatasetRef(
        source_native_uri=uri,
        source_native_id=native_id if isinstance(native_id, str) else None,
        catalog_modified=harvest.get("modified") if isinstance(harvest.get("modified"), str) else None,
    )
