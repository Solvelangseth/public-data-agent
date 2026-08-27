from __future__ import annotations

from collections import deque
from typing import Any
from urllib.parse import quote, urlparse

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "oslo"
SOURCE_NAME = "Oslo kommune Statistikkbank"
API_ROOT = "https://statistikkbanken.oslo.kommune.no/statbank/api/v1/no"
DEFAULT_DATABASE = "db1"
DEFAULT_SUBJECT = "Befolkning"
DEFAULT_MAX_TABLES = 10
INGEST_REASON = (
    "listed as type=t under the printed Oslo PxWeb subject "
    f"{DEFAULT_SUBJECT}, capped at {DEFAULT_MAX_TABLES} tables"
)
OSLO_RPS = 2.0
OSLO_BURST = 4
HOST = "statistikkbanken.oslo.kommune.no"
PATH_PREFIX = "/statbank/api/v1/"


class OsloStatbankSource(SourceBase):
    """Replaceable ingest adapter for Oslo kommune's public PxWeb catalog.

    Listing walks the JSON folders the official list API prints under the
    printed `db1` / `Befolkning` path. It does not invent table ids. This
    first slice stays inside that printed subject and caps the walk.
    """

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = (API_ROOT,)
    ingest_reason = INGEST_REASON

    def __init__(
        self,
        *,
        api_root: str = API_ROOT,
        database: str = DEFAULT_DATABASE,
        subject: str = DEFAULT_SUBJECT,
        max_tables: int = DEFAULT_MAX_TABLES,
        http: HttpClient | None = None,
    ) -> None:
        self.api_root = api_root.rstrip("/")
        self.database = database
        self.subject = subject
        self.max_tables = max_tables
        self.http = http or HttpClient(
            limiter=RateLimiter(OSLO_RPS, OSLO_BURST),
            timeout=60.0,
        )

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_tables if limit is None else limit
        start_url = join_catalog_url(self.api_root, self.database, self.subject)
        listed = _walk_tables(self.http, start_url, cap + offset)
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for folder_url, item in sliced:
            table_id = printed_table_id(item)
            table_url = join_catalog_url(folder_url, table_id)
            refs.append(
                DatasetRef(
                    source_native_uri=table_url,
                    source_native_id=table_id,
                    catalog_modified=(
                        item.get("updated") if isinstance(item.get("updated"), str) else None
                    ),
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        try:
            meta = self.http.get_json(ref.source_native_uri)
        except Exception as exc:
            raise SourceError(
                f"Oslo table metadata failed for {ref.source_native_uri}: {exc}"
            ) from exc
        if not isinstance(meta, dict):
            raise SourceError(
                f"Oslo table metadata is not a JSON object: {ref.source_native_uri}"
            )
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
            "oslo_table_metadata": meta,
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
    """Copy the table id Oslo printed on the list item."""

    listed_id = item.get("id")
    if listed_id is None or str(listed_id).strip() == "":
        raise SourceError("Oslo list item has no printed table id")
    return str(listed_id)


def join_catalog_url(base: str, *segments: str) -> str:
    url = base.rstrip("/")
    for segment in segments:
        url = f"{url}/{quote(str(segment), safe='.-_')}"
    return url


def is_oslo_statbank_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlparse(access_path)
    return parsed.netloc.lower() == HOST and parsed.path.startswith(PATH_PREFIX)


def oslo_table_id(access_path: str) -> str:
    segment = urlparse(access_path).path.rstrip("/").split("/")[-1]
    return segment or "oslo"


def _walk_tables(http: HttpClient, start_url: str, cap: int) -> list[tuple[str, dict[str, Any]]]:
    tables: list[tuple[str, dict[str, Any]]] = []
    queue: deque[str] = deque([start_url])
    seen = {start_url}
    while queue and len(tables) < cap:
        url = queue.popleft()
        try:
            body = http.get_json(url)
        except Exception as exc:
            raise SourceError(f"Oslo catalog list failed for {url}: {exc}") from exc
        if not isinstance(body, list):
            raise SourceError(f"Oslo catalog list is not a JSON array: {url}")
        for item in body:
            if not isinstance(item, dict):
                continue
            kind = item.get("type")
            listed_id = item.get("id")
            if kind == "t":
                tables.append((url, item))
                if len(tables) >= cap:
                    break
            elif kind == "l" and listed_id:
                next_url = join_catalog_url(url, str(listed_id))
                if next_url not in seen:
                    seen.add(next_url)
                    queue.append(next_url)
    return tables
