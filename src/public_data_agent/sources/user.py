from __future__ import annotations

import csv
import re
import sqlite3
from pathlib import Path
from typing import Any

from public_data_agent.models import DatasetRef, HarvestCounts, HarvestedRecord
from public_data_agent.registry import Registry
from public_data_agent.sources.base import SourceBase

USER_SOURCE_ID = "user"
INGEST_REASON = "user-supplied local file for this search run"


class UserFileSource(SourceBase):
    """Map a local CSV or SQLite table onto the same harvest document shape."""

    source_id = USER_SOURCE_ID
    source_name = "user-supplied file"
    ingest_reason = INGEST_REASON

    def __init__(self, path: Path, payloads: list[dict[str, Any]]) -> None:
        self.path = path
        self.endpoints = (path.resolve().as_uri(),)
        self._payloads = list(payloads)

    @classmethod
    def from_path(cls, path: Path | str) -> UserFileSource:
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"no user file at {file_path}")
        suffix = file_path.suffix.lower()
        if suffix == ".csv":
            payloads = _payloads_from_csv(file_path)
        elif suffix in {".sqlite", ".db"}:
            payloads = _payloads_from_sqlite(file_path)
        else:
            raise ValueError(f"user file must be .csv, .sqlite, or .db: {file_path}")
        if not payloads:
            raise ValueError(f"user file has no rows: {file_path}")
        return cls(file_path, payloads)

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        refs = [
            DatasetRef(
                source_native_uri=str(payload["uri"]),
                source_native_id=str(payload["id"]),
            )
            for payload in self._payloads
        ]
        end = None if limit is None else offset + limit
        return refs[offset:end]

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        for payload in self._payloads:
            if payload.get("uri") == ref.source_native_uri or payload.get("id") == ref.source_native_id:
                return HarvestedRecord(
                    source_id=self.source_id,
                    source_name=self.source_name,
                    source_endpoints=self.endpoints,
                    ingest_reason=self.ingest_reason,
                    source_native_id=str(payload["id"]),
                    source_native_uri=str(payload["uri"]),
                    fetched_from=self.path.resolve().as_uri(),
                    payload=payload,
                )
        raise KeyError(f"user file has no dataset {ref.source_native_uri}")


def ingest_user_file(registry: Registry, path: Path | str) -> HarvestCounts:
    from public_data_agent.harvest import harvest

    source = UserFileSource.from_path(path)
    return harvest(registry, source, notes=f"user file {Path(path)}")


def annotate_search_hits(results: list[dict[str, Any]], registry: Registry) -> list[dict[str, Any]]:
    """Copy stored source_id onto each hit. Does not change ranking."""

    for hit in results:
        row = registry.get_dataset(hit["id"])
        source_id = (row or {}).get("source_id") or str(hit["id"]).split(":", 1)[0]
        hit["source"] = source_id
        hit["user_supplied"] = source_id == USER_SOURCE_ID
    return results


def ensure_user_hits(
    results: list[dict[str, Any]],
    registry: Registry,
    query: str,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    """Keep at least one matching user row when follow-up truncation drops it."""

    if any((registry.get_dataset(hit["id"]) or {}).get("source_id") == USER_SOURCE_ID for hit in results):
        return results
    from public_data_agent.search import search

    extras: list[dict[str, Any]] = []
    seen = {hit["id"] for hit in results}
    for hit in search(registry, query, limit=max(limit, 1), decompose_query=False):
        row = registry.get_dataset(hit.dataset_id)
        if (row or {}).get("source_id") != USER_SOURCE_ID:
            continue
        if hit.dataset_id in seen:
            continue
        extras.append(hit.to_dict())
    if not extras:
        return results
    return (extras + results)[:limit]


def _payloads_from_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [_row_to_payload(row, path, index) for index, row in enumerate(rows, start=1)]


def _payloads_from_sqlite(path: Path) -> list[dict[str, Any]]:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        table = conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchone()
        if table is None:
            return []
        rows = conn.execute(f"SELECT * FROM \"{table['name']}\"").fetchall()
    finally:
        conn.close()
    return [_row_to_payload(dict(row), path, index) for index, row in enumerate(rows, start=1)]


def _row_to_payload(row: dict[str, Any], path: Path, index: int) -> dict[str, Any]:
    fields = {str(key).casefold(): value for key, value in row.items() if key is not None}
    native_id = _text(fields, "id") or f"{path.stem}-{index}"
    title = _text(fields, "title") or _text(fields, "name")
    description = _text(fields, "description") or _text(fields, "notes")
    publisher_name = _text(fields, "publisher") or USER_SOURCE_ID
    license_value = _text(fields, "license")
    access = _text(fields, "access_path") or _text(fields, "url") or str(path.resolve())
    keywords = _keywords(_text(fields, "keywords") or _text(fields, "keyword"))
    payload: dict[str, Any] = {
        "id": native_id,
        "uri": f"{path.resolve().as_uri()}#{native_id}",
        "title": title,
        "description": description,
        "keyword": keywords,
        "landingPage": [access],
        "publisher": {"name": publisher_name},
    }
    if license_value:
        payload["license"] = license_value
    return payload


def _text(fields: dict[str, Any], key: str) -> str | None:
    value = fields.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _keywords(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in re.split(r"[;,]", raw) if part.strip()]
