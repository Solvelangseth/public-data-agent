from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "npolar"
SOURCE_NAME = "Norsk Polarinstitutt Open Data API"
LIST_URL = "https://api.npolar.no/service/?q=*&format=json"
COLLECTION_QUERY = "q=*&format=json"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a service path in the official Norsk Polarinstitutt "
    f"/service catalog, capped at {DEFAULT_MAX_ITEMS} services"
)
NPOLAR_RPS = 2.0
NPOLAR_BURST = 4
HOST = "api.npolar.no"
NAME_FIELDS = ("name", "title", "native", "code", "id")


class NpolarSource(SourceBase):
    """Replaceable ingest adapter for the Norsk Polarinstitutt service catalog.

    Listing copies service ids and paths the official /service list prints.
    It does not invent endpoint ids. Native ids are the printed service `id`
    values. access_path joins each printed path to the catalog origin and the
    same `q=*&format=json` query the catalog uses to print members. This first
    slice stays inside that list and caps the walk.
    """

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = (LIST_URL,)
    ingest_reason = INGEST_REASON

    def __init__(
        self,
        *,
        list_url: str = LIST_URL,
        max_items: int = DEFAULT_MAX_ITEMS,
        http: HttpClient | None = None,
    ) -> None:
        self.list_url = list_url
        self.max_items = max_items
        self.http = http or HttpClient(
            limiter=RateLimiter(NPOLAR_RPS, NPOLAR_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._catalog()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            path = printed_service_path(item)
            refs.append(
                DatasetRef(
                    source_native_uri=printed_collection_url(path, self.list_url),
                    source_native_id=printed_service_id(item),
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        item = self._catalog_item(ref)
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            title = printed_service_id(item)
        summary = item.get("summary")
        path = printed_service_path(item)
        endpoint = printed_collection_url(path, self.list_url)
        payload = {
            "id": printed_service_id(item),
            "uri": endpoint,
            "title": {"en": title},
            "description": {"en": summary} if isinstance(summary, str) and summary.strip() else None,
            "publisher": None,
            "license": None,
            "distribution": [
                {
                    "accessURL": [endpoint],
                    "downloadURL": [endpoint],
                }
            ],
            "landingPage": [self.list_url],
            "npolar_service_path": path,
            "npolar_service": item,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=printed_service_id(item),
            source_native_uri=endpoint,
            fetched_from=self.list_url,
            payload=payload,
        )

    def _catalog(self) -> list[dict[str, Any]]:
        if self._listed is not None:
            return self._listed
        try:
            body = self.http.get_json(self.list_url)
        except Exception as exc:
            raise SourceError(f"NPI service list failed for {self.list_url}: {exc}") from exc
        listed = printed_service_entries(body)
        if not listed:
            raise SourceError(f"NPI service list printed no services: {self.list_url}")
        self._listed = listed
        return listed

    def _catalog_item(self, ref: DatasetRef) -> dict[str, Any]:
        for item in self._catalog():
            path = printed_service_path(item)
            if printed_collection_url(path, self.list_url) == ref.source_native_uri:
                return item
            if printed_service_id(item) == ref.source_native_id:
                return item
        raise SourceError(f"NPI service list has no printed service matching {ref.source_native_uri}")


def printed_service_entries(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise SourceError("NPI service list is not a JSON object")
    feed = body.get("feed")
    if not isinstance(feed, dict):
        raise SourceError("NPI service list has no printed feed object")
    entries = feed.get("entries")
    if not isinstance(entries, list):
        raise SourceError("NPI service list has no printed feed.entries array")
    listed: list[dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        try:
            printed_service_id(item)
            printed_service_path(item)
        except SourceError:
            continue
        listed.append(item)
    return listed


def printed_service_id(item: dict[str, Any]) -> str:
    ident = item.get("id")
    if isinstance(ident, str) and ident.strip():
        return ident.strip()
    raise SourceError("NPI service entry has no printed id")


def printed_service_path(item: dict[str, Any]) -> str:
    path = item.get("path")
    if not isinstance(path, str) or not path.strip():
        raise SourceError("NPI service entry has no printed path")
    return path.strip()


def printed_collection_url(path: str, list_url: str) -> str:
    """Join a printed service path to the catalog origin.

    The live /service list uses `q=*&format=json` to print members. A bare
    collection path prints only a count object. The same query is copied onto
    each printed path. No service id is invented.
    """

    parts = urlsplit(list_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("NPI service list URL has no printed origin")
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{parts.scheme}://{parts.netloc}{suffix}/?{COLLECTION_QUERY}"


def is_npolar_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    return urlsplit(access_path).netloc.lower() == HOST


def npolar_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "npolar"


def cells_from_npolar(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed NPI feed entries into observation cells.

    Collection feeds keep printed `name` or `title` when present. Other
    scalars stay as dimensions. Nested objects are not copied. Nothing is
    invented.
    """

    if not isinstance(payload, dict):
        raise ValueError("npolar payload is not a JSON object")
    feed = payload.get("feed")
    if not isinstance(feed, dict):
        raise ValueError("npolar payload has no printed feed object")
    entries = feed.get("entries")
    if not isinstance(entries, list):
        raise ValueError("npolar payload has no printed feed.entries array")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        cells.extend(_cells_from_record(item))
    if not cells:
        raise ValueError("npolar payload printed no feed entries")
    return cells


def _cells_from_record(item: dict[str, Any]) -> list[tuple[str, Any, dict[str, str]]]:
    scalars = {key: value for key, value in item.items() if _is_scalar(value) and key != "_rev"}
    if not scalars:
        return []
    measure = None
    value: Any = None
    for field in NAME_FIELDS:
        if field in scalars:
            measure = field
            value = scalars[field]
            break
    if measure is None:
        measure, value = next(iter(scalars.items()))
    dims = {key: _as_dim(other) for key, other in scalars.items() if key != measure}
    return [(measure, value, dims)]


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _as_dim(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
