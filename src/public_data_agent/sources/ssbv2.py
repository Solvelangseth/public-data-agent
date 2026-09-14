from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "ssbv2"
SOURCE_NAME = "SSB PxWebApi 2"
LIST_URL = "https://data.ssb.no/api/pxwebapi/v2/tables"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed table on the official SSB PxWebApi 2 tables catalog, "
    f"capped at {DEFAULT_MAX_ITEMS} tables"
)
SSBV2_RPS = 2.0
SSBV2_BURST = 4
HOST = "data.ssb.no"
PATH_MARK = "/api/pxwebapi/v2/tables"
DATA_REL = "data"
SSBV2_MAX_CELLS = 100


class Ssbv2Source(SourceBase):
    """Replaceable ingest adapter for SSB PxWebApi 2.

    Listing copies printed table `id` values and the printed `data` href.
    It does not invent table ids. This first slice stays inside the first
    printed tables page and caps the walk. This is not the SSB PxWeb v0
    Statbank (`--source ssb`).
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
            limiter=RateLimiter(SSBV2_RPS, SSBV2_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._listed_tables()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            refs.append(
                DatasetRef(
                    source_native_uri=item["data_url"],
                    source_native_id=item["id"],
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident = ref.source_native_id or ssbv2_table_id(ref.source_native_uri or "")
        item = self._table_item(ident)
        href = item["data_url"]
        title = item["title"]
        description = item.get("description")
        source = item.get("source")
        payload = {
            "id": ident,
            "uri": href,
            "title": {"no": title},
            "description": {"no": description} if isinstance(description, str) and description.strip() else None,
            "publisher": (
                {"title": {"no": source}} if isinstance(source, str) and source.strip() else None
            ),
            "license": None,
            "distribution": [
                {
                    "accessURL": [href],
                    "downloadURL": [href],
                }
            ],
            "landingPage": [self.list_url],
            "ssbv2_table": item,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ident,
            source_native_uri=href,
            fetched_from=self.list_url,
            payload=payload,
        )

    def _listed_tables(self) -> list[dict[str, Any]]:
        if self._listed is not None:
            return self._listed
        try:
            body = self.http.get_json(self.list_url)
        except Exception as exc:
            raise SourceError(f"SSB PxWebApi 2 tables catalog failed for {self.list_url}: {exc}") from exc
        listed = printed_tables(body)
        if not listed:
            raise SourceError(f"SSB PxWebApi 2 tables catalog printed no tables: {self.list_url}")
        self._listed = listed
        return listed

    def _table_item(self, ident: str) -> dict[str, Any]:
        for item in self._listed_tables():
            if item["id"] == ident:
                return item
        raise SourceError(f"SSB PxWebApi 2 tables catalog has no printed table {ident}")


def printed_tables(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise SourceError("SSB PxWebApi 2 tables catalog is not a JSON object")
    tables = body.get("tables")
    if not isinstance(tables, list):
        raise SourceError("SSB PxWebApi 2 tables catalog has no printed tables array")
    listed: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in tables:
        if not isinstance(item, dict):
            continue
        ident = item.get("id")
        href = printed_data_url(item)
        if not isinstance(ident, str) or not ident.strip() or href is None:
            continue
        ident = ident.strip()
        if ident in seen:
            continue
        seen.add(ident)
        title = item.get("label")
        description = item.get("description")
        source = item.get("source")
        listed.append(
            {
                "id": ident,
                "title": title.strip() if isinstance(title, str) and title.strip() else ident,
                "description": description if isinstance(description, str) else None,
                "source": source.strip() if isinstance(source, str) else None,
                "data_url": href,
            }
        )
    return listed


def printed_data_url(table: dict[str, Any]) -> str | None:
    """Copy the printed data href. Do not invent a format query."""

    links = table.get("links")
    if not isinstance(links, list):
        return None
    for link in links:
        if not isinstance(link, dict):
            continue
        if link.get("rel") != DATA_REL:
            continue
        href = link.get("href")
        if isinstance(href, str) and href.strip():
            return href.strip()
    return None


def is_ssbv2_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.lower() == HOST and PATH_MARK in parsed.path


def is_ssbv2_data_url(access_path: str | None) -> bool:
    """A table's json-stat2 data href. The tables catalog is a different path."""

    if not is_ssbv2_url(access_path):
        return False
    path = urlsplit(access_path).path.rstrip("/").casefold()
    return "/tables/" in path and path.endswith("/data")


def ssbv2_metadata_url(access_path: str) -> str:
    """The printed table's metadata href. Do not invent a format."""

    parts = urlsplit(access_path)
    path = parts.path.rstrip("/")
    if path.casefold().endswith("/data"):
        path = path[: -len("/data")] + "/metadata"
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.pop("outputFormat", None)
    if "lang" not in query:
        query["lang"] = "no"
    return urlunsplit((parts.scheme, parts.netloc, path, urlencode(query), ""))


def ssbv2_table_id(access_path: str) -> str:
    parts = [part for part in urlsplit(access_path).path.split("/") if part]
    if "tables" in parts:
        index = parts.index("tables")
        if index + 1 < len(parts) and parts[index + 1] != "data":
            return parts[index + 1]
    if parts:
        last = parts[-1]
        if last != "data":
            return last
    return "ssbv2"


def cells_from_ssbv2(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed PxWebApi 2 JSON-stat2 cells.

    A tables catalog falls back to printed table id/label. Nested objects
    other than json-stat dimensions are not copied. Nothing is invented.
    """

    if not isinstance(payload, dict):
        raise ValueError("ssbv2 payload is not a JSON object")
    if isinstance(payload.get("dimension"), dict) and "value" in payload:
        from public_data_agent.ssb_pxweb import cells_from_jsonstat_coded

        coded = cells_from_jsonstat_coded(payload)
        cells = [(cell.measure, cell.value, cell.labels) for cell in coded]
        if not cells:
            raise ValueError("ssbv2 payload printed no json-stat cells")
        return cells
    tables = payload.get("tables")
    if isinstance(tables, list):
        cells: list[tuple[str, Any, dict[str, str]]] = []
        for item in tables:
            if isinstance(item, dict):
                cells.extend(_cells_from_table(item))
        if not cells:
            raise ValueError("ssbv2 payload printed no tables")
        return cells
    raise ValueError("ssbv2 payload is not JSON-stat2 data or a tables catalog")


def _cells_from_table(item: dict[str, Any]) -> list[tuple[str, Any, dict[str, str]]]:
    scalars = {key: value for key, value in item.items() if _is_scalar(value)}
    if not scalars:
        return []
    measure = None
    value: Any = None
    for field in ("label", "id", "source"):
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
