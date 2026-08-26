from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any

from public_data_agent.models import HarvestCounts, NormalizedDataset

SCHEMA_PACKAGE = "public_data_agent"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class Registry:
    def __init__(self, path: Path | str) -> None:
        self.path = path
        if path != ":memory:":
            self.path = Path(path)
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA busy_timeout = 5000")
        self._apply_schema()

    def close(self) -> None:
        self.conn.close()

    def _apply_schema(self) -> None:
        sql = resources.files(SCHEMA_PACKAGE).joinpath("schema.sql").read_text(encoding="utf-8")
        self.conn.executescript(sql)
        self.conn.commit()

    def start_run(
        self,
        *,
        source_id: str,
        source_name: str,
        source_endpoints: tuple[str, ...],
        limit_applied: int | None,
        notes: str | None = None,
        started_at: str | None = None,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO harvest_runs (
                source_id, source_name, source_endpoints_json, started_at,
                status, limit_applied, notes
            ) VALUES (?, ?, ?, ?, 'running', ?, ?)
            """,
            (
                source_id,
                source_name,
                json.dumps(list(source_endpoints), ensure_ascii=False),
                started_at or utc_now(),
                limit_applied,
                notes,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def finish_run(
        self,
        run_id: int,
        counts: HarvestCounts,
        *,
        status: str,
        finished_at: str | None = None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE harvest_runs
            SET finished_at = ?, status = ?, listed = ?, inserted = ?,
                updated = ?, unchanged = ?, failed = ?, errors_json = ?
            WHERE id = ?
            """,
            (
                finished_at or utc_now(),
                status,
                counts.listed,
                counts.inserted,
                counts.updated,
                counts.unchanged,
                counts.failed,
                json.dumps(counts.errors, ensure_ascii=False),
                run_id,
            ),
        )
        self.conn.commit()

    def checkpoint_run(self, run_id: int, counts: HarvestCounts) -> None:
        """Write live counts while status is still running."""

        self.conn.execute(
            """
            UPDATE harvest_runs
            SET listed = ?, inserted = ?, updated = ?, unchanged = ?,
                failed = ?, errors_json = ?
            WHERE id = ?
            """,
            (
                counts.listed,
                counts.inserted,
                counts.updated,
                counts.unchanged,
                counts.failed,
                json.dumps(counts.errors, ensure_ascii=False),
                run_id,
            ),
        )
        self.conn.commit()

    def missing_field_stats(self) -> dict[str, Any]:
        rows = self.conn.execute("SELECT missing_fields_json FROM datasets").fetchall()
        total = len(rows)
        keys = (
            "publisher",
            "license",
            "access_path",
            "issued",
            "modified",
            "temporal",
            "spatial",
            "structure",
            "title",
            "description",
            "original_source",
        )
        counts = {key: 0 for key in keys}
        for row in rows:
            missing = json.loads(row["missing_fields_json"] or "{}")
            for key in keys:
                if key in missing:
                    counts[key] += 1
        rates = {
            key: {
                "count": counts[key],
                "percent": round((counts[key] / total) * 100, 2) if total else 0.0,
            }
            for key in keys
        }
        return {"datasets": total, "missing": rates}

    def get_dataset(self, dataset_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
        return dict(row) if row else None

    def get_payload(self, dataset_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (dataset_id,),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["payload_json"])

    def existing_catalog_modified(self, source_id: str, source_native_uri: str) -> str | None:
        row = self.conn.execute(
            """
            SELECT source_catalog_modified FROM datasets
            WHERE source_id = ? AND source_native_uri = ?
            """,
            (source_id, source_native_uri),
        ).fetchone()
        if row is None:
            return None
        return row["source_catalog_modified"]

    def mark_seen(self, source_id: str, source_native_uri: str, run_id: int, seen_at: str) -> None:
        self.conn.execute(
            """
            UPDATE datasets
            SET last_seen_at = ?, last_harvest_run_id = ?
            WHERE source_id = ? AND source_native_uri = ?
            """,
            (seen_at, run_id, source_id, source_native_uri),
        )
        self.conn.commit()

    def dataset_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS n FROM datasets").fetchone()
        return int(row["n"])

    def list_runs(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM harvest_runs ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    def iter_search_rows(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT d.*, p.payload_json
            FROM datasets d
            LEFT JOIN harvested_payloads p ON p.dataset_id = d.id
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def upsert(self, dataset: NormalizedDataset, run_id: int, *, now: str | None = None) -> str:
        """Insert or update by stable id. Never deletes other rows."""

        stamp = now or utc_now()
        existing = self.get_dataset(dataset.id)
        payload_json = json.dumps(dataset.payload, ensure_ascii=False)
        values = _row_values(dataset, run_id, stamp)

        if existing is None:
            self.conn.execute(
                f"INSERT INTO datasets ({', '.join(_DATASET_COLUMNS)}) VALUES ({_placeholders(_DATASET_COLUMNS)})",
                values,
            )
            self.conn.execute(
                """
                INSERT INTO harvested_payloads (dataset_id, payload_json, fetched_from, fetched_at)
                VALUES (?, ?, ?, ?)
                """,
                (dataset.id, payload_json, dataset.fetched_from, stamp),
            )
            self.conn.commit()
            return "inserted"

        self.conn.execute(
            """
            UPDATE datasets SET last_seen_at = ?, last_harvest_run_id = ? WHERE id = ?
            """,
            (stamp, run_id, dataset.id),
        )
        if existing["payload_hash"] == dataset.payload_hash:
            self.conn.commit()
            return "unchanged"

        assign = ", ".join(f"{col} = ?" for col in _UPDATE_COLUMNS)
        update_values = [_row_map(dataset, run_id, stamp)[col] for col in _UPDATE_COLUMNS]
        self.conn.execute(
            f"UPDATE datasets SET {assign} WHERE id = ?",
            (*update_values, dataset.id),
        )
        self.conn.execute(
            """
            UPDATE harvested_payloads
            SET payload_json = ?, fetched_from = ?, fetched_at = ?
            WHERE dataset_id = ?
            """,
            (payload_json, dataset.fetched_from, stamp, dataset.id),
        )
        self.conn.commit()
        return "updated"


_DATASET_COLUMNS = (
    "id",
    "source_id",
    "source_native_id",
    "source_native_uri",
    "title",
    "title_i18n_json",
    "description",
    "description_i18n_json",
    "publisher_id",
    "publisher_name",
    "publisher_uri",
    "publisher_json",
    "license",
    "licenses_json",
    "access_path",
    "access_rights",
    "access_rights_uri",
    "issued",
    "modified",
    "temporal_start",
    "temporal_end",
    "temporal_json",
    "spatial_json",
    "media_types_json",
    "formats_json",
    "conforms_to_json",
    "distributions_json",
    "landing_pages_json",
    "ingest_reason",
    "source_name",
    "source_endpoints_json",
    "missing_fields_json",
    "payload_hash",
    "source_catalog_modified",
    "source_harvest_modified",
    "first_ingested_at",
    "last_ingested_at",
    "last_seen_at",
    "last_changed_at",
    "last_harvest_run_id",
)

_UPDATE_COLUMNS = tuple(
    col
    for col in _DATASET_COLUMNS
    if col not in {"id", "first_ingested_at", "last_seen_at"}
)


def _placeholders(columns: tuple[str, ...]) -> str:
    return ", ".join("?" for _ in columns)


def _dumps(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _row_map(dataset: NormalizedDataset, run_id: int, stamp: str) -> dict[str, Any]:
    return {
        "id": dataset.id,
        "source_id": dataset.source_id,
        "source_native_id": dataset.source_native_id,
        "source_native_uri": dataset.source_native_uri,
        "title": dataset.title,
        "title_i18n_json": _dumps(dataset.title_i18n),
        "description": dataset.description,
        "description_i18n_json": _dumps(dataset.description_i18n),
        "publisher_id": dataset.publisher_id,
        "publisher_name": dataset.publisher_name,
        "publisher_uri": dataset.publisher_uri,
        "publisher_json": _dumps(dataset.publisher),
        "license": dataset.license,
        "licenses_json": _dumps(dataset.licenses),
        "access_path": dataset.access_path,
        "access_rights": dataset.access_rights,
        "access_rights_uri": dataset.access_rights_uri,
        "issued": dataset.issued,
        "modified": dataset.modified,
        "temporal_start": dataset.temporal_start,
        "temporal_end": dataset.temporal_end,
        "temporal_json": _dumps(dataset.temporal),
        "spatial_json": _dumps(dataset.spatial),
        "media_types_json": _dumps(dataset.media_types),
        "formats_json": _dumps(dataset.formats),
        "conforms_to_json": _dumps(dataset.conforms_to),
        "distributions_json": _dumps(dataset.distributions),
        "landing_pages_json": _dumps(dataset.landing_pages),
        "ingest_reason": dataset.ingest_reason,
        "source_name": dataset.source_name,
        "source_endpoints_json": _dumps(list(dataset.source_endpoints)),
        "missing_fields_json": _dumps(dataset.missing_fields),
        "payload_hash": dataset.payload_hash,
        "source_catalog_modified": dataset.source_catalog_modified,
        "source_harvest_modified": dataset.source_harvest_modified,
        "first_ingested_at": stamp,
        "last_ingested_at": stamp,
        "last_seen_at": stamp,
        "last_changed_at": stamp,
        "last_harvest_run_id": run_id,
    }


def _row_values(dataset: NormalizedDataset, run_id: int, stamp: str) -> tuple[Any, ...]:
    mapping = _row_map(dataset, run_id, stamp)
    return tuple(mapping[col] for col in _DATASET_COLUMNS)
