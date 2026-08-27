from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from public_data_agent.fetch import JsonHttp, fetch_observations
from public_data_agent.models import HarvestCounts
from public_data_agent.registry import Registry, utc_now
from public_data_agent.ssb_pxweb import DEFAULT_SSB_TABLE, DEFAULT_SSB_TABLE_URL, fetch_ssb_table

DEFAULT_KLASS_DATASET = "datanorge:0c89041e-ae88-32ef-a765-8e1ccbd64fdd"
JOIN_KEY = "bydel_code"
SSB_PUBLISHER = "Statistisk sentralbyrå"

WHY_NOT_M7_M8 = (
    "OK-BEF008 is Oslo city totals with no bydel or kommune code. "
    "Klass 1168 is classification names keyed by 0301xx. "
    "Those two do not share a key to a metric."
)
WHY_NOT_07459 = (
    "07459 is live at data.ssb.no/api/v0/no/table/07459 and has kommune 0301, "
    "but it is still not an access_path in the registry and it has no bydel codes. "
    "Joining one Oslo total onto 42 bydels is the same glue the milestone forbids."
)
WHY_11763 = (
    "Table 11763 is a public no-auth SSB PxWeb befolkning/bydel table. "
    "Its Region codes 030101-030117 and 030199 are the same strings Klass 1168 stores. "
    "07459 and 11763 are both absent from stored access_path values."
)


@dataclass
class JoinResult:
    join_key: str
    left_dataset_id: str
    right_dataset_id: str
    left_request_url: str
    right_request_url: str
    left_http_status: int
    right_http_status: int
    right_title: str | None = None
    right_publisher: str | None = None
    counts: HarvestCounts = field(default_factory=HarvestCounts)
    sample: list[dict[str, Any]] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)


def join_bydel_population(
    registry: Registry,
    *,
    klass_dataset_id: str = DEFAULT_KLASS_DATASET,
    ssb_table: str = DEFAULT_SSB_TABLE,
    year: int | None = 2025,
    http: JsonHttp | None = None,
) -> JoinResult:
    """Inner-join Klass bydel codes to SSB 11763 population on the exact code."""

    klass_dataset = registry.get_dataset(klass_dataset_id)
    if klass_dataset is None:
        raise ValueError(f"unknown dataset {klass_dataset_id}")
    right_dataset_id = f"ssb:{ssb_table}"
    started = utc_now()
    run_id = registry.start_join_run(
        join_key=JOIN_KEY,
        left_dataset_id=klass_dataset_id,
        right_dataset_id=right_dataset_id,
        left_request_url=klass_dataset.get("access_path") or "",
        right_request_url=DEFAULT_SSB_TABLE_URL if ssb_table == DEFAULT_SSB_TABLE else f"https://data.ssb.no/api/v0/no/table/{ssb_table}",
        started_at=started,
    )
    counts = HarvestCounts()
    status = "failed"
    left_http = 0
    right_http = 0
    left_url = klass_dataset.get("access_path") or ""
    right_url = ""
    sample: list[dict[str, Any]] = []
    stored: list[dict[str, Any]] = []
    try:
        klass_fetch = fetch_observations(registry, klass_dataset_id, table_id="klass", http=http)
        left_http = klass_fetch.http_status
        left_url = klass_fetch.request_url
        ssb = fetch_ssb_table(ssb_table, year=year, http=http)
        right_http = ssb.http_status
        right_url = ssb.request_url
        right_title = ssb.label
        right_publisher = ssb.source or SSB_PUBLISHER
        klass_by_code = _klass_by_code(registry.list_observations(klass_dataset_id))
        retrieved_left = utc_now()
        for cell in ssb.cells:
            code = _region_code(cell.codes)
            if code is None:
                continue
            klass_row = klass_by_code.get(code)
            if klass_row is None:
                continue
            year_label = cell.labels.get("Tid") or cell.codes.get("Tid") or ""
            why = (
                f"exact {JOIN_KEY} {code} in SSB {ssb_table} Region and "
                f"Klass classificationItems.code"
            )
            payload = {
                "bydel_code": code,
                "year": year_label,
                "age": cell.labels.get("KOKalder0000") or cell.labels.get("Alder"),
                "population": cell.value,
                "population_measure": cell.measure,
                "ssb_region_label": cell.labels.get("KOKbydelsregion0000") or cell.labels.get("Region"),
                "klass_name": json.loads(klass_row["value_json"]),
            }
            record = {
                "id": _joined_id(JOIN_KEY, code, year_label, klass_dataset_id, right_dataset_id),
                "join_key": JOIN_KEY,
                "join_key_value": code,
                "why_matched": why,
                "left_dataset_id": klass_dataset_id,
                "right_dataset_id": right_dataset_id,
                "left_publisher_name": klass_dataset.get("publisher_name"),
                "right_publisher_name": right_publisher,
                "left_license": klass_dataset.get("license"),
                "right_license": None,
                "left_access_path": klass_dataset.get("access_path"),
                "right_access_path": ssb.request_url,
                "left_request_url": left_url,
                "right_request_url": right_url,
                "left_retrieved_at": klass_row.get("retrieved_at") or retrieved_left,
                "right_retrieved_at": ssb.retrieved_at,
                "payload": payload,
            }
            action = registry.upsert_joined_row(record, run_id)
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1
            stored.append({**payload, "why_matched": why})
            if len(sample) < 5:
                sample.append(
                    {
                        "join_key": JOIN_KEY,
                        "join_key_value": code,
                        "why_matched": why,
                        **payload,
                    }
                )
        counts.listed = len(stored)
        status = "completed"
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc)})
        raise
    finally:
        registry.finish_join_run(
            run_id,
            counts,
            status=status,
            left_http_status=left_http or None,
            right_http_status=right_http or None,
        )
    return JoinResult(
        join_key=JOIN_KEY,
        left_dataset_id=klass_dataset_id,
        right_dataset_id=right_dataset_id,
        left_request_url=left_url,
        right_request_url=right_url,
        left_http_status=left_http,
        right_http_status=right_http,
        right_title=right_title,
        right_publisher=right_publisher,
        counts=counts,
        sample=sample,
        rows=stored,
    )


def join_proof_payload(
    result: JoinResult,
    *,
    command: str,
    db: str,
    klass_dataset: dict[str, Any] | None,
    datasets: int | None = None,
    enrichments: int | None = None,
) -> dict[str, Any]:
    return {
        "produced_at": utc_now(),
        "command": command,
        "why_not_m7_m8": WHY_NOT_M7_M8,
        "why_not_07459": WHY_NOT_07459,
        "why_this_table": WHY_11763,
        "join_key": result.join_key,
        "sources": {
            "left": {
                "dataset_id": result.left_dataset_id,
                "title": (klass_dataset or {}).get("title"),
                "publisher_name": (klass_dataset or {}).get("publisher_name"),
                "license": (klass_dataset or {}).get("license"),
                "access_path": (klass_dataset or {}).get("access_path"),
                "request_url": result.left_request_url,
                "http_status": result.left_http_status,
            },
            "right": {
                "dataset_id": result.right_dataset_id,
                "title": result.right_title,
                "publisher_name": result.right_publisher or SSB_PUBLISHER,
                "license": None,
                "access_path": result.right_request_url,
                "request_url": result.right_request_url,
                "http_status": result.right_http_status,
                "auth": "none",
            },
        },
        "db": db,
        "counts": {
            "joined": result.counts.listed,
            "inserted": result.counts.inserted,
            "updated": result.counts.updated,
            "unchanged": result.counts.unchanged,
            "failed": result.counts.failed,
            "datasets_unchanged": datasets,
            "enrichments_unchanged": enrichments,
        },
        "sample": result.sample,
        "rows": result.rows,
    }


def _klass_by_code(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        dims = json.loads(row["dimensions_json"])
        code = dims.get("code")
        if code:
            out[str(code)] = row
    return out


def _region_code(codes: dict[str, str]) -> str | None:
    for key in ("KOKbydelsregion0000", "Region"):
        value = codes.get(key)
        if value and len(value) == 6 and value.isdigit():
            return value
    for value in codes.values():
        if len(value) == 6 and value.isdigit():
            return value
    return None


def _joined_id(
    join_key: str,
    key_value: str,
    year: str,
    left_dataset_id: str,
    right_dataset_id: str,
) -> str:
    raw = "\0".join([join_key, key_value, year, left_dataset_id, right_dataset_id])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]
