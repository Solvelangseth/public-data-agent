from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
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
        self._defer_commit = False
        self._apply_schema()

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def deferred_commit(self) -> Iterator[None]:
        """Commit once at the end of a bulk write instead of once per row.

        Storing a table's cells one commit at a time is one fsync per cell,
        which is fine for a 36-row join and not fine for a table with tens of
        thousands. Durability is unchanged for a completed block; an exception
        rolls the whole block back, which is the behaviour a partial table
        should have anyway.
        """

        previous = self._defer_commit
        self._defer_commit = True
        try:
            yield
        except Exception:
            self.conn.rollback()
            raise
        else:
            self.conn.commit()
        finally:
            self._defer_commit = previous

    def _commit(self) -> None:
        if not self._defer_commit:
            self.conn.commit()

    def _apply_schema(self) -> None:
        sql = resources.files(SCHEMA_PACKAGE).joinpath("schema.sql").read_text(encoding="utf-8")
        self.conn.executescript(sql)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        """Add columns that `CREATE TABLE IF NOT EXISTS` cannot add to an old file.

        Existing rows keep series NULL: we do not backfill a provenance claim we
        cannot verify from what was stored.
        """

        columns = {
            row["name"] for row in self.conn.execute("PRAGMA table_info(observations)").fetchall()
        }
        if "series" not in columns:
            self.conn.execute("ALTER TABLE observations ADD COLUMN series TEXT")

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

    def get_enrichment(self, dataset_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM enrichments WHERE dataset_id = ?",
            (dataset_id,),
        ).fetchone()
        return dict(row) if row else None

    def enrichment_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()
        return int(row["n"])

    def ensure_observation_dataset(
        self,
        *,
        dataset_id: str,
        title: str | None,
        publisher_name: str | None,
        access_path: str | None,
        license: str | None,
    ) -> None:
        """Insert an identity-only datasets row so observations can satisfy the FK.

        Does not write harvested_payloads or enrichments. Does not update a
        row that already exists.
        """

        if self.get_dataset(dataset_id) is not None:
            return
        source_id, _, native_id = dataset_id.partition(":")
        stamp = utc_now()
        self.conn.execute(
            """
            INSERT INTO datasets (
                id, source_id, source_native_id, source_native_uri,
                title, publisher_name, license, access_path,
                ingest_reason, source_name, source_endpoints_json,
                missing_fields_json, payload_hash,
                first_ingested_at, last_ingested_at, last_seen_at, last_changed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dataset_id,
                source_id or dataset_id,
                native_id or None,
                access_path,
                title,
                publisher_name,
                license,
                access_path,
                "observation_store_identity",
                publisher_name or dataset_id,
                json.dumps([access_path] if access_path else [], ensure_ascii=False),
                json.dumps({}, ensure_ascii=False),
                hashlib.sha256(dataset_id.encode("utf-8")).hexdigest(),
                stamp,
                stamp,
                stamp,
                stamp,
            ),
        )
        self.conn.commit()

    def start_fetch_run(
        self,
        *,
        dataset_id: str,
        table_id: str,
        request_url: str,
        request_method: str,
        started_at: str | None = None,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO fetch_runs (
                dataset_id, table_id, request_url, request_method,
                started_at, status
            ) VALUES (?, ?, ?, ?, ?, 'running')
            """,
            (dataset_id, table_id, request_url, request_method, started_at or utc_now()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def set_fetch_request(
        self,
        run_id: int,
        *,
        request_url: str,
        request_body: dict[str, Any],
    ) -> None:
        self.conn.execute(
            """
            UPDATE fetch_runs
            SET request_url = ?, request_body_json = ?
            WHERE id = ?
            """,
            (request_url, json.dumps(request_body, ensure_ascii=False), run_id),
        )
        self.conn.commit()

    def finish_fetch_run(
        self,
        run_id: int,
        counts: HarvestCounts,
        *,
        status: str,
        http_status: int | None,
        finished_at: str | None = None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE fetch_runs
            SET finished_at = ?, status = ?, http_status = ?, listed = ?,
                inserted = ?, updated = ?, unchanged = ?, failed = ?,
                errors_json = ?
            WHERE id = ?
            """,
            (
                finished_at or utc_now(),
                status,
                http_status,
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

    def observation_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS n FROM observations").fetchone()
        return int(row["n"])

    def list_observations(
        self,
        dataset_id: str | None = None,
        *,
        series: str | None = None,
        ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        if ids is not None and not ids:
            return []
        clauses: list[str] = []
        params: list[Any] = []
        if ids is not None:
            # Chunked to stay under SQLite's variable limit on a wide fetch.
            out: list[dict[str, Any]] = []
            for start in range(0, len(ids), 500):
                chunk = ids[start : start + 500]
                placeholders = ",".join("?" for _ in chunk)
                rows = self.conn.execute(
                    f"SELECT * FROM observations WHERE id IN ({placeholders}) ORDER BY id",
                    tuple(chunk),
                ).fetchall()
                out.extend(dict(row) for row in rows)
            return out
        if dataset_id:
            clauses.append("dataset_id = ?")
            params.append(dataset_id)
        if series is not None:
            clauses.append("series = ?")
            params.append(series)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.conn.execute(
            f"SELECT * FROM observations{where} ORDER BY id", tuple(params)
        ).fetchall()
        return [dict(row) for row in rows]

    # ---- resource index -------------------------------------------------
    # What a dataset can return and what is inside it. A question reaches a
    # resource through these, not through its title alone.

    def set_capability(self, dataset_id: str, capability: dict[str, Any]) -> str:
        """Record what a dataset has been verified to return.

        `verified_at` is only meaningful alongside a sample count: a capability
        claimed without having seen a record is exactly the overreach the
        `unverified` kind exists to express.
        """

        if capability.get("verified_at") and not capability.get("verified_sample_count"):
            raise ValueError(
                "verified_at requires verified_sample_count; a capability is "
                "claimed from records actually seen, not from a URL pattern"
            )
        columns = (
            "dataset_id", "capability", "record_kind", "endpoint", "request_method",
            "period_start", "period_end", "source_modified_at", "verified_at",
            "verified_sample_count", "notes",
        )
        values = {"dataset_id": dataset_id, **{c: capability.get(c) for c in columns[1:]}}
        if values["capability"] is None:
            raise ValueError("capability is required")
        existing = self.conn.execute(
            "SELECT dataset_id FROM resource_capability WHERE dataset_id = ?", (dataset_id,)
        ).fetchone()
        if existing is None:
            self.conn.execute(
                f"INSERT INTO resource_capability ({', '.join(columns)}) "
                f"VALUES ({_placeholders(columns)})",
                tuple(values[c] for c in columns),
            )
            action = "inserted"
        else:
            assign = ", ".join(f"{c} = ?" for c in columns[1:])
            self.conn.execute(
                f"UPDATE resource_capability SET {assign} WHERE dataset_id = ?",
                (*(values[c] for c in columns[1:]), dataset_id),
            )
            action = "updated"
        self._commit()
        return action

    def get_capability(self, dataset_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM resource_capability WHERE dataset_id = ?", (dataset_id,)
        ).fetchone()
        return dict(row) if row else None

    def set_resource_shape(
        self,
        dataset_id: str,
        fields: list[dict[str, Any]],
        *,
        keys: list[dict[str, Any]] | None = None,
    ) -> dict[str, int]:
        """Replace a resource's recorded shape.

        A shape is replaced rather than merged: a field the source has dropped
        must disappear, or a later query offers a selection the resource will
        refuse.
        """

        with self.deferred_commit():
            self.conn.execute("DELETE FROM resource_fields WHERE dataset_id = ?", (dataset_id,))
            self.conn.execute(
                "DELETE FROM resource_field_values WHERE dataset_id = ?", (dataset_id,)
            )
            self.conn.execute("DELETE FROM resource_keys WHERE dataset_id = ?", (dataset_id,))
            n_values = 0
            for field in fields:
                code = field.get("field_code")
                if not code:
                    raise ValueError("every field needs a field_code")
                values = field.get("values") or []
                self.conn.execute(
                    "INSERT INTO resource_fields "
                    "(dataset_id, field_code, field_label, field_role, value_count) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        dataset_id, code, field.get("field_label"), field.get("field_role"),
                        field.get("value_count", len(values)) or None,
                    ),
                )
                seen: set[str] = set()
                for value in values:
                    value_code = str(value["value_code"] if isinstance(value, dict) else value)
                    if value_code in seen:
                        continue
                    seen.add(value_code)
                    self.conn.execute(
                        "INSERT INTO resource_field_values "
                        "(dataset_id, field_code, value_code, value_label) VALUES (?, ?, ?, ?)",
                        (
                            dataset_id, code, value_code,
                            value.get("value_label") if isinstance(value, dict) else None,
                        ),
                    )
                    n_values += 1
            for key in keys or []:
                self.conn.execute(
                    "INSERT INTO resource_keys "
                    "(dataset_id, scheme, field_code, coverage_count) VALUES (?, ?, ?, ?)",
                    (
                        dataset_id, key["scheme"], key.get("field_code"),
                        key.get("coverage_count"),
                    ),
                )
        return {"fields": len(fields), "values": n_values, "keys": len(keys or [])}

    def resource_fields(self, dataset_id: str) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self.conn.execute(
                "SELECT * FROM resource_fields WHERE dataset_id = ? ORDER BY field_code",
                (dataset_id,),
            )
        ]

    def datasets_with_key(self, scheme: str, *, limit: int = 100) -> list[dict[str, Any]]:
        """Which resources speak a published identifier scheme.

        Answering this from the index is the difference between knowing what can
        be related to what and finding out during a failed request.
        """

        return [
            dict(row)
            for row in self.conn.execute(
                "SELECT rk.dataset_id, rk.field_code, rk.coverage_count, d.title, "
                "       rc.capability "
                "FROM resource_keys rk "
                "JOIN datasets d ON d.id = rk.dataset_id "
                "LEFT JOIN resource_capability rc ON rc.dataset_id = rk.dataset_id "
                "WHERE rk.scheme = ? ORDER BY rk.coverage_count DESC LIMIT ?",
                (scheme, limit),
            )
        ]

    def datasets_containing_value(
        self, value_code: str, *, field_code: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Which resources actually contain a code.

        This is how a question reaches a table whose title never mentions the
        thing being asked about.
        """

        sql = (
            "SELECT rfv.dataset_id, rfv.field_code, rfv.value_label, d.title, rc.capability "
            "FROM resource_field_values rfv "
            "JOIN datasets d ON d.id = rfv.dataset_id "
            "LEFT JOIN resource_capability rc ON rc.dataset_id = rfv.dataset_id "
            "WHERE rfv.value_code = ?"
        )
        params: list[Any] = [value_code]
        if field_code is not None:
            sql += " AND rfv.field_code = ?"
            params.append(field_code)
        sql += " LIMIT ?"
        params.append(limit)
        return [dict(row) for row in self.conn.execute(sql, params)]

    # ---- records --------------------------------------------------------

    def upsert_record(self, row: dict[str, Any], run_id: int) -> str:
        """Store one retrieved record of any kind.

        Identity comes from everything that can make two records different --
        subject, period, measure and attributes. Keyed on less, a resource that
        splits a subject several ways overwrites itself and reports success.
        """

        kind = row.get("kind")
        if kind not in _RECORD_KINDS:
            raise ValueError(f"unknown record kind {kind!r}; known={sorted(_RECORD_KINDS)}")
        attributes = row.get("attributes") or {}
        values = {
            "id": row["id"],
            "dataset_id": row["dataset_id"],
            "kind": kind,
            "series": row.get("series"),
            "subject_scheme": row.get("subject_scheme"),
            "subject_code": row.get("subject_code"),
            "subject_label": row.get("subject_label"),
            "period": row.get("period"),
            "measure": row.get("measure"),
            "value_num": _numeric(row.get("value")),
            "value_json": _dumps(row.get("value")),
            "suppressed": row.get("suppressed"),
            "attributes_json": json.dumps(
                attributes, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
            "geometry_json": _dumps(row.get("geometry")) if row.get("geometry") else None,
            "retrieved_at": row["retrieved_at"],
            "request_url": row["request_url"],
            "http_status": row["http_status"],
            "publisher_name": row.get("publisher_name"),
            "license": row.get("license"),
            "fetch_run_id": run_id,
        }
        existing = self.conn.execute(
            "SELECT id, value_json, attributes_json FROM records WHERE id = ?", (row["id"],)
        ).fetchone()
        if existing is None:
            self.conn.execute(
                f"INSERT INTO records ({', '.join(_RECORD_COLUMNS)}) "
                f"VALUES ({_placeholders(_RECORD_COLUMNS)})",
                tuple(values[col] for col in _RECORD_COLUMNS),
            )
            self._commit()
            return "inserted"
        if (
            existing["value_json"] == values["value_json"]
            and existing["attributes_json"] == values["attributes_json"]
        ):
            return "unchanged"
        assign = ", ".join(f"{col} = ?" for col in _RECORD_UPDATE_COLUMNS)
        self.conn.execute(
            f"UPDATE records SET {assign} WHERE id = ?",
            (*(values[col] for col in _RECORD_UPDATE_COLUMNS), row["id"]),
        )
        self._commit()
        return "updated"

    def list_records(
        self,
        dataset_id: str | None = None,
        *,
        kind: str | None = None,
        subject_scheme: str | None = None,
        subject_code: str | None = None,
        series: str | None = None,
        ids: list[str] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Read records, scoped. An unscoped read blends incompatible shapes."""

        if ids is not None:
            if not ids:
                return []
            out: list[dict[str, Any]] = []
            for start in range(0, len(ids), 500):
                chunk = ids[start : start + 500]
                out.extend(
                    dict(r)
                    for r in self.conn.execute(
                        f"SELECT * FROM records WHERE id IN ({','.join('?' * len(chunk))})",
                        chunk,
                    )
                )
            return out
        clauses: list[str] = []
        params: list[Any] = []
        for column, value in (
            ("dataset_id", dataset_id), ("kind", kind), ("subject_scheme", subject_scheme),
            ("subject_code", subject_code), ("series", series),
        ):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        sql = "SELECT * FROM records"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        return [dict(row) for row in self.conn.execute(sql, params)]

    def record_count(self, dataset_id: str | None = None) -> int:
        if dataset_id is None:
            return int(self.conn.execute("SELECT COUNT(*) FROM records").fetchone()[0])
        return int(
            self.conn.execute(
                "SELECT COUNT(*) FROM records WHERE dataset_id = ?", (dataset_id,)
            ).fetchone()[0]
        )

    def upsert_observation(self, row: dict[str, Any], run_id: int) -> str:
        existing = self.conn.execute(
            "SELECT id, value_json, series FROM observations WHERE id = ?",
            (row["id"],),
        ).fetchone()
        values = {
            "id": row["id"],
            "dataset_id": row["dataset_id"],
            "series": row.get("series"),
            "table_id": row["table_id"],
            "measure": row["measure"],
            "value_json": _dumps(row.get("value")),
            "dimensions_json": json.dumps(
                row["dimensions"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
            "retrieved_at": row["retrieved_at"],
            "request_url": row["request_url"],
            "http_status": row["http_status"],
            "publisher_name": row.get("publisher_name"),
            "license": row.get("license"),
            "access_path": row.get("access_path"),
            "source_native_uri": row.get("source_native_uri"),
            "fetch_run_id": run_id,
        }
        if existing is None:
            self.conn.execute(
                f"INSERT INTO observations ({', '.join(_OBSERVATION_COLUMNS)}) "
                f"VALUES ({_placeholders(_OBSERVATION_COLUMNS)})",
                tuple(values[col] for col in _OBSERVATION_COLUMNS),
            )
            self._commit()
            return "inserted"
        if existing["value_json"] == values["value_json"]:
            # The value is unchanged, but a row written before the series column
            # existed carries no tag.  Backfill it from the connector that just
            # re-produced this exact cell; "unchanged" still describes the value.
            if values["series"] is not None and existing["series"] != values["series"]:
                self.conn.execute(
                    "UPDATE observations SET series = ? WHERE id = ?",
                    (values["series"], row["id"]),
                )
                self._commit()
            return "unchanged"
        assign = ", ".join(f"{col} = ?" for col in _OBSERVATION_UPDATE_COLUMNS)
        self.conn.execute(
            f"UPDATE observations SET {assign} WHERE id = ?",
            (*(values[col] for col in _OBSERVATION_UPDATE_COLUMNS), row["id"]),
        )
        self._commit()
        return "updated"

    def upsert_embedding(
        self,
        *,
        dataset_id: str,
        model: str,
        vector: bytes,
        dim: int,
        text_hash: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO embeddings (dataset_id, model, dim, vector, text_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(dataset_id) DO UPDATE SET
                model = excluded.model, dim = excluded.dim, vector = excluded.vector,
                text_hash = excluded.text_hash, created_at = excluded.created_at
            """,
            (dataset_id, model, dim, vector, text_hash, utc_now()),
        )
        self._commit()

    def embedding_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS n FROM embeddings").fetchone()
        return int(row["n"])

    def embedded_hashes(self) -> dict[str, str]:
        """dataset_id -> text_hash already embedded, so re-embedding is incremental."""

        return {
            row["dataset_id"]: row["text_hash"]
            for row in self.conn.execute("SELECT dataset_id, text_hash FROM embeddings")
        }

    def iter_embeddings(self, model: str | None = None):
        sql = "SELECT dataset_id, dim, vector FROM embeddings"
        params: tuple[Any, ...] = ()
        if model is not None:
            sql += " WHERE model = ?"
            params = (model,)
        for row in self.conn.execute(sql, params):
            yield row["dataset_id"], row["dim"], row["vector"]

    def upsert_printed_table_url(
        self,
        *,
        dataset_id: str,
        url: str,
        kind: str,
        found_in: str,
    ) -> str:
        """Persist a harvest-printed table URL. Does not write harvest blobs."""

        stamp = utc_now()
        existing = self.conn.execute(
            "SELECT url, kind, found_in FROM printed_table_urls WHERE dataset_id = ? AND url = ?",
            (dataset_id, url),
        ).fetchone()
        if existing is None:
            self.conn.execute(
                """
                INSERT INTO printed_table_urls (
                    dataset_id, url, kind, found_in, first_seen_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (dataset_id, url, kind, found_in, stamp, stamp),
            )
            self.conn.commit()
            return "inserted"
        self.conn.execute(
            """
            UPDATE printed_table_urls
            SET kind = ?, found_in = ?, last_seen_at = ?
            WHERE dataset_id = ? AND url = ?
            """,
            (kind, found_in, stamp, dataset_id, url),
        )
        self.conn.commit()
        if existing["kind"] == kind and existing["found_in"] == found_in:
            return "unchanged"
        return "updated"

    def list_printed_table_urls(self, dataset_id: str | None = None) -> list[dict[str, Any]]:
        if dataset_id is None:
            rows = self.conn.execute(
                "SELECT * FROM printed_table_urls ORDER BY dataset_id, url"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM printed_table_urls WHERE dataset_id = ? ORDER BY url",
                (dataset_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def printed_table_url_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS n FROM printed_table_urls").fetchone()
        return int(row["n"])

    def start_join_run(
        self,
        *,
        join_key: str,
        left_dataset_id: str | None,
        right_dataset_id: str | None,
        left_request_url: str,
        right_request_url: str,
        started_at: str | None = None,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO join_runs (
                join_key, left_dataset_id, right_dataset_id,
                left_request_url, right_request_url, started_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, 'running')
            """,
            (
                join_key,
                left_dataset_id,
                right_dataset_id,
                left_request_url,
                right_request_url,
                started_at or utc_now(),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def finish_join_run(
        self,
        run_id: int,
        counts: HarvestCounts,
        *,
        status: str,
        left_http_status: int | None,
        right_http_status: int | None,
        finished_at: str | None = None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE join_runs
            SET finished_at = ?, status = ?, left_http_status = ?,
                right_http_status = ?, listed = ?, inserted = ?,
                updated = ?, unchanged = ?, failed = ?, errors_json = ?
            WHERE id = ?
            """,
            (
                finished_at or utc_now(),
                status,
                left_http_status,
                right_http_status,
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

    def joined_row_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS n FROM joined_rows").fetchone()
        return int(row["n"])

    def list_joined_rows(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM joined_rows ORDER BY join_key_value, id").fetchall()
        return [dict(row) for row in rows]

    def upsert_joined_row(self, row: dict[str, Any], run_id: int) -> str:
        existing = self.conn.execute(
            "SELECT id, payload_json FROM joined_rows WHERE id = ?",
            (row["id"],),
        ).fetchone()
        values = {
            "id": row["id"],
            "join_run_id": run_id,
            "join_key": row["join_key"],
            "join_key_value": row["join_key_value"],
            "why_matched": row["why_matched"],
            "left_dataset_id": row.get("left_dataset_id"),
            "right_dataset_id": row.get("right_dataset_id"),
            "left_publisher_name": row.get("left_publisher_name"),
            "right_publisher_name": row.get("right_publisher_name"),
            "left_license": row.get("left_license"),
            "right_license": row.get("right_license"),
            "left_access_path": row.get("left_access_path"),
            "right_access_path": row.get("right_access_path"),
            "left_request_url": row.get("left_request_url"),
            "right_request_url": row.get("right_request_url"),
            "left_retrieved_at": row.get("left_retrieved_at"),
            "right_retrieved_at": row.get("right_retrieved_at"),
            "payload_json": _dumps(row.get("payload")),
        }
        if existing is None:
            self.conn.execute(
                f"INSERT INTO joined_rows ({', '.join(_JOINED_ROW_COLUMNS)}) "
                f"VALUES ({_placeholders(_JOINED_ROW_COLUMNS)})",
                tuple(values[col] for col in _JOINED_ROW_COLUMNS),
            )
            self.conn.commit()
            return "inserted"
        if existing["payload_json"] == values["payload_json"]:
            return "unchanged"
        assign = ", ".join(f"{col} = ?" for col in _JOINED_ROW_UPDATE_COLUMNS)
        self.conn.execute(
            f"UPDATE joined_rows SET {assign} WHERE id = ?",
            (*(values[col] for col in _JOINED_ROW_UPDATE_COLUMNS), row["id"]),
        )
        self.conn.commit()
        return "updated"

    def upsert_enrichment(self, row: dict[str, Any], *, now: str | None = None) -> str:
        """Insert or update by dataset_id. Matching harvest payload_hash is a no-op."""

        stamp = now or utc_now()
        existing = self.get_enrichment(row["dataset_id"])
        if existing is not None and existing["payload_hash"] == row["payload_hash"]:
            return "unchanged"

        values = {
            "dataset_id": row["dataset_id"],
            "source": row["source"],
            "method": row["method"],
            "created_at": existing["created_at"] if existing else stamp,
            "updated_at": stamp,
            "payload_hash": row["payload_hash"],
            "topics_json": _dumps(row.get("topics")),
            "aliases_json": _dumps(row.get("aliases")),
            "geography_json": _dumps(row.get("geography")),
            "time_coverage_json": _dumps(row.get("time_coverage")),
            "fields_json": _dumps(row.get("fields")),
            "can_answer_json": _dumps(row.get("can_answer")),
            "missing_json": _dumps(row.get("missing") or {}),
        }
        if existing is None:
            self.conn.execute(
                f"INSERT INTO enrichments ({', '.join(_ENRICHMENT_COLUMNS)}) "
                f"VALUES ({_placeholders(_ENRICHMENT_COLUMNS)})",
                tuple(values[col] for col in _ENRICHMENT_COLUMNS),
            )
            self.conn.commit()
            return "inserted"

        assign = ", ".join(f"{col} = ?" for col in _ENRICHMENT_UPDATE_COLUMNS)
        self.conn.execute(
            f"UPDATE enrichments SET {assign} WHERE dataset_id = ?",
            (*(values[col] for col in _ENRICHMENT_UPDATE_COLUMNS), row["dataset_id"]),
        )
        self.conn.commit()
        return "updated"

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

_ENRICHMENT_COLUMNS = (
    "dataset_id",
    "source",
    "method",
    "created_at",
    "updated_at",
    "payload_hash",
    "topics_json",
    "aliases_json",
    "geography_json",
    "time_coverage_json",
    "fields_json",
    "can_answer_json",
    "missing_json",
)

_ENRICHMENT_UPDATE_COLUMNS = tuple(
    col for col in _ENRICHMENT_COLUMNS if col not in {"dataset_id", "created_at"}
)

_OBSERVATION_COLUMNS = (
    "id",
    "dataset_id",
    "series",
    "table_id",
    "measure",
    "value_json",
    "dimensions_json",
    "retrieved_at",
    "request_url",
    "http_status",
    "publisher_name",
    "license",
    "access_path",
    "source_native_uri",
    "fetch_run_id",
)

_OBSERVATION_UPDATE_COLUMNS = tuple(
    col for col in _OBSERVATION_COLUMNS if col not in {"id", "dataset_id", "table_id"}
)

_JOINED_ROW_COLUMNS = (
    "id",
    "join_run_id",
    "join_key",
    "join_key_value",
    "why_matched",
    "left_dataset_id",
    "right_dataset_id",
    "left_publisher_name",
    "right_publisher_name",
    "left_license",
    "right_license",
    "left_access_path",
    "right_access_path",
    "left_request_url",
    "right_request_url",
    "left_retrieved_at",
    "right_retrieved_at",
    "payload_json",
)

_JOINED_ROW_UPDATE_COLUMNS = tuple(col for col in _JOINED_ROW_COLUMNS if col not in {"id"})


_RECORD_KINDS = frozenset({"observation", "entity", "feature", "document"})

_RECORD_COLUMNS = (
    "id", "dataset_id", "kind", "series", "subject_scheme", "subject_code",
    "subject_label", "period", "measure", "value_num", "value_json", "suppressed",
    "attributes_json", "geometry_json", "retrieved_at", "request_url", "http_status",
    "publisher_name", "license", "fetch_run_id",
)
# id never changes; everything else may be re-reported by a later fetch.
_RECORD_UPDATE_COLUMNS = tuple(c for c in _RECORD_COLUMNS if c != "id")


def _numeric(value: Any) -> float | None:
    """The value as a number, or None where it is not one.

    A publisher's suppression marker and a free-text code are both non-numeric,
    and neither should become a zero that a later average silently counts.
    """

    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None

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
