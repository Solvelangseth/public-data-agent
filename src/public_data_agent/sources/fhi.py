from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "fhi"
SOURCE_NAME = "Folkehelseinstituttet Statistikk"
LIST_URL = "https://statistikk-data.fhi.no/api/open/v1/Common/source"
API_ROOT = "https://statistikk-data.fhi.no/api/open/v1"
DEFAULT_MAX_ITEMS = 500
INGEST_REASON = (
    "listed as a printed table on the official FHI Statistikk Open API "
    "Common/source registers, walked one register at a time"
)
FHI_RPS = 2.0
FHI_BURST = 4
FHI_HOST = "statistikk-data.fhi.no"
FHI_PATH = "/api/open/v1"


class FhiStatistikkSource(SourceBase):
    """Replaceable ingest adapter for the official FHI Statistikk list API.

    Listing copies printed `id` values on Common/source. Access paths join
    those printed ids to the official `/Table` collection. This first slice
    caps the walk.
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
            limiter=RateLimiter(FHI_RPS, FHI_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None
        self._tables: dict[str, list[dict[str, Any]]] = {}

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        refs: list[DatasetRef] = []
        for item in self._source_items():
            source_id = printed_source_id(item)
            for table in self._register_tables(source_id):
                table_id = table.get("tableId")
                if table_id is None:
                    continue
                refs.append(
                    DatasetRef(
                        source_native_uri=printed_table_data_url(source_id, str(table_id)),
                        source_native_id=f"{source_id}:{table_id}",
                    )
                )
        return refs[offset : offset + cap]

    def _register_tables(self, source_id: str) -> list[dict[str, Any]]:
        if source_id in self._tables:
            return self._tables[source_id]
        try:
            body = self.http.get_json(printed_table_url(source_id))
        except Exception as exc:
            raise SourceError(
                f"FHI Statistikk table list failed for register {source_id}: {exc}"
            ) from exc
        listed = body if isinstance(body, list) else (body or {}).get("items") or []
        tables = [t for t in listed if isinstance(t, dict)]
        self._tables[source_id] = tables
        return tables

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        href = ref.source_native_uri
        source_id, table_id = split_table_url(href)
        ident = ref.source_native_id or f"{source_id}:{table_id}"
        item = self._source_item(source_id)
        table = next(
            (t for t in self._register_tables(source_id) if str(t.get("tableId")) == table_id),
            {},
        )
        # The register title describes a whole register; the table title is what
        # a search for this data would actually match on.
        title = table.get("title") or item.get("title")
        description = item.get("description")
        publisher_name = item.get("publishedBy")
        about = item.get("aboutUrl")
        payload = {
            "id": ident,
            "uri": href,
            "title": {"no": title} if isinstance(title, str) and title.strip() else {"no": ident},
            "description": (
                {"no": description} if isinstance(description, str) and description.strip() else None
            ),
            "publisher": (
                {"name": publisher_name}
                if isinstance(publisher_name, str) and publisher_name.strip()
                else None
            ),
            "license": None,
            "distribution": [
                {
                    "accessURL": [href],
                    "downloadURL": [href],
                }
            ],
            "landingPage": (
                [about] if isinstance(about, str) and about.strip() else [href]
            ),
            "fhi_metadata": item,
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

    def _source_items(self) -> list[dict[str, Any]]:
        if self._listed is not None:
            return self._listed
        try:
            body = self.http.get_json(self.list_url)
        except Exception as exc:
            raise SourceError(f"FHI Statistikk source list failed for {self.list_url}: {exc}") from exc
        if not isinstance(body, list):
            raise SourceError(f"FHI Statistikk source list is not a JSON array: {self.list_url}")
        listed = [item for item in body if isinstance(item, dict) and printed_source_id(item)]
        if not listed:
            raise SourceError("FHI Statistikk source list printed no source ids")
        self._listed = listed
        return listed

    def _source_item(self, ident: str) -> dict[str, Any]:
        for item in self._source_items():
            if printed_source_id(item) == ident:
                return item
        raise SourceError(f"FHI Statistikk source list has no printed source {ident}")


def printed_source_id(item: dict[str, Any]) -> str:
    ident = item.get("id")
    if isinstance(ident, str) and ident.strip():
        return ident.strip()
    raise SourceError("FHI Statistikk source item has no printed id")


def printed_table_url(source_id: str) -> str:
    return f"{API_ROOT}/{source_id}/Table"


def printed_table_data_url(source_id: str, table_id: str) -> str:
    """Address one table. The list URL names a register; this names data."""

    return f"{API_ROOT}/{source_id}/Table/{table_id}"


def split_table_url(access_path: str) -> tuple[str, str]:
    """Return (source_id, table_id) printed in a table URL.

    Raises for a register list URL, which carries no table id and so cannot
    name a numeric cell.
    """

    path = urlparse(access_path).path
    rest = path[len(FHI_PATH):] if path.startswith(FHI_PATH) else path
    parts = [p for p in rest.strip("/").split("/") if p]
    if len(parts) < 3 or parts[1].casefold() != "table":
        raise SourceError(f"FHI URL names no table: {access_path}")
    return parts[0], parts[2]


def is_fhi_table_url(access_path: str | None) -> bool:
    """True only for a URL that addresses one table's data."""

    if not is_fhi_url(access_path):
        return False
    try:
        split_table_url(access_path or "")
    except SourceError:
        return False
    return True


def flatten_categories(categories: Any) -> list[tuple[str, str]]:
    """Flatten FHI's nested category tree into printed (value, label) pairs.

    GEO nests bydel under kommune under fylke under country. A query has to
    name every level it wants, so the tree is walked rather than topped.
    """

    out: list[tuple[str, str]] = []
    for cat in categories or []:
        if not isinstance(cat, dict):
            continue
        value = cat.get("value")
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            out.append((str(value), str(cat.get("label") or value)))
        out.extend(flatten_categories(cat.get("children")))
    return out


def years_in(code: str) -> list[int]:
    """Years printed in a period code.

    FHI prints both plain years and spans such as "2023_2025" for a school
    year, so a code can carry more than one and a range test needs all of them.
    """

    return [int(m) for m in re.findall(r"(?<!\d)(\d{4})(?!\d)", code)]


def printed_native_id(access_path: str) -> str:
    path = urlparse(access_path).path
    prefix = FHI_PATH
    rest = path[len(prefix) :] if path.startswith(prefix) else path
    ident = rest.strip("/").split("/")[0]
    if not ident:
        raise SourceError("FHI Statistikk URL has no printed source id")
    return ident


def is_fhi_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlparse(access_path)
    return parsed.netloc.lower() == FHI_HOST and parsed.path.startswith(FHI_PATH)


def fhi_table_id(access_path: str) -> str:
    return printed_native_id(access_path)


def cells_from_fhi(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed FHI table-list records into observation cells.

    Values are the printed tableId. Titles stay as printed measures.
    Nothing is invented.
    """

    if not isinstance(payload, list):
        raise ValueError("fhi payload is not a JSON array")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        table_id = item.get("tableId")
        title = item.get("title")
        if table_id is None and not isinstance(title, str):
            continue
        dims: dict[str, str] = {}
        if isinstance(table_id, (str, int)) and not isinstance(table_id, bool):
            dims["tableId"] = str(table_id)
        for key in ("publishedAt", "modifiedAt"):
            value = item.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                dims[key] = str(value)
        measure = title if isinstance(title, str) and title.strip() else "tableId"
        value = table_id if table_id is not None else title
        cells.append((measure, value, dims))
    return cells
