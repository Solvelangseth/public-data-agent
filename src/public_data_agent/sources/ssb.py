from __future__ import annotations

import re
from collections import deque
from typing import Any
from urllib.parse import urljoin

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "ssb"
SOURCE_NAME = "SSB Statistikkbank"
API_ROOT = "https://data.ssb.no/api/v0/no"
SUBJECT_LIST_URL = f"{API_ROOT}/table"
DEFAULT_SUBJECT = "be"
DEFAULT_MAX_TABLES = 8
INGEST_REASON = (
    "listed as type=t under the printed SSB PxWeb subject "
    f"{DEFAULT_SUBJECT} (Befolkning), capped at {DEFAULT_MAX_TABLES} BFS tables"
)
TABLE_NUMBER_RE = re.compile(r"^(\d{5})\b")
SSB_RPS = 2.0
SSB_BURST = 4


class SsbStatbankSource(SourceBase):
    """Replaceable ingest adapter for SSB's public PxWeb catalog.

    Listing walks the JSON folders SSB prints at /api/v0/no/table. It does
    not invent table ids. This first slice stays inside one printed subject
    and caps the walk.
    """

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = (API_ROOT, SUBJECT_LIST_URL)
    ingest_reason = INGEST_REASON

    def __init__(
        self,
        *,
        api_root: str = API_ROOT,
        subject: str = DEFAULT_SUBJECT,
        max_tables: int = DEFAULT_MAX_TABLES,
        http: HttpClient | None = None,
    ) -> None:
        self.api_root = api_root.rstrip("/")
        self.subject = subject
        self.max_tables = max_tables
        self.http = http or HttpClient(
            limiter=RateLimiter(SSB_RPS, SSB_BURST),
            timeout=60.0,
        )

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_tables if limit is None else limit
        listed = _walk_tables(self.http, f"{self.api_root}/table/{self.subject}", cap + offset)
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            table_id = printed_table_id(item)
            table_url = f"{self.api_root}/table/{table_id}"
            refs.append(
                DatasetRef(
                    source_native_uri=table_url,
                    source_native_id=table_id,
                    catalog_modified=item.get("updated") if isinstance(item.get("updated"), str) else None,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        try:
            meta = self.http.get_json(ref.source_native_uri)
        except Exception as exc:
            raise SourceError(f"SSB table metadata failed for {ref.source_native_uri}: {exc}") from exc
        if not isinstance(meta, dict):
            raise SourceError(f"SSB table metadata is not a JSON object: {ref.source_native_uri}")
        title = str(meta.get("title") or ref.source_native_id or ref.source_native_uri)
        payload = {
            "id": ref.source_native_id,
            "uri": ref.source_native_uri,
            "title": {"no": title},
            "description": None,
            "publisher": None,
            "license": None,
            "distribution": [
                {
                    "accessURL": [ref.source_native_uri],
                    "downloadURL": [ref.source_native_uri],
                }
            ],
            "landingPage": [ref.source_native_uri],
            "ssb_table_metadata": meta,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ref.source_native_id,
            source_native_uri=ref.source_native_uri,
            fetched_from=ref.source_native_uri,
            payload=payload,
            catalog_modified=ref.catalog_modified,
        )


def printed_table_id(item: dict[str, Any]) -> str:
    """Copy the table id SSB printed. Prefer the leading 5-digit number in text."""

    text = str(item.get("text") or "")
    match = TABLE_NUMBER_RE.match(text.strip())
    if match:
        return match.group(1)
    listed_id = item.get("id")
    if listed_id is None or str(listed_id).strip() == "":
        raise SourceError("SSB list item has no printed table id")
    return str(listed_id)


def _walk_tables(http: HttpClient, start_url: str, cap: int) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    queue: deque[str] = deque([start_url])
    seen = {start_url}
    while queue and len(tables) < cap:
        url = queue.popleft()
        try:
            body = http.get_json(url)
        except Exception as exc:
            raise SourceError(f"SSB catalog list failed for {url}: {exc}") from exc
        if not isinstance(body, list):
            raise SourceError(f"SSB catalog list is not a JSON array: {url}")
        for item in body:
            if not isinstance(item, dict):
                continue
            kind = item.get("type")
            listed_id = item.get("id")
            if kind == "t":
                tables.append(item)
                if len(tables) >= cap:
                    break
            elif kind == "l" and listed_id:
                next_url = urljoin(url.rstrip("/") + "/", str(listed_id))
                if next_url not in seen:
                    seen.add(next_url)
                    queue.append(next_url)
    return tables
