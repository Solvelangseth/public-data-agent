from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "sikt"
SOURCE_NAME = "Sikt DataverseNO"
LIST_URL = "https://dataverse.no/api/dataverses/:root/contents"
ROOT_TOKEN = ":root"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a titled dataverse on the official DataverseNO "
    f"/dataverses/:root/contents catalog, capped at {DEFAULT_MAX_ITEMS} collections"
)
SIKT_RPS = 2.0
SIKT_BURST = 4
HOST = "dataverse.no"
NAME_FIELDS = ("title", "name", "identifier", "id")


class SiktSource(SourceBase):
    """Replaceable ingest adapter for the Sikt DataverseNO collection catalog.

    Listing copies titled dataverse ids the official :root/contents list
    prints. It does not invent collection ids. Native ids are the printed
    `id` values. access_path keeps the catalog's own
    `/api/dataverses/:root/contents` path and substitutes the printed id for
    `:root`. This first slice stays inside that list and caps the walk.
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
            limiter=RateLimiter(SIKT_RPS, SIKT_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._catalog()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            ident = printed_dataverse_id(item)
            refs.append(
                DatasetRef(
                    source_native_uri=printed_collection_url(ident, self.list_url),
                    source_native_id=ident,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        item = self._catalog_item(ref)
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            title = printed_dataverse_id(item)
        ident = printed_dataverse_id(item)
        endpoint = printed_collection_url(ident, self.list_url)
        payload = {
            "id": ident,
            "uri": endpoint,
            "title": {"en": title},
            "description": None,
            "publisher": None,
            "license": None,
            "distribution": [
                {
                    "accessURL": [endpoint],
                    "downloadURL": [endpoint],
                }
            ],
            "landingPage": [self.list_url],
            "sikt_dataverse": item,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ident,
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
            raise SourceError(f"DataverseNO list failed for {self.list_url}: {exc}") from exc
        listed = printed_dataverse_entries(body)
        if not listed:
            raise SourceError(f"DataverseNO list printed no titled dataverses: {self.list_url}")
        self._listed = listed
        return listed

    def _catalog_item(self, ref: DatasetRef) -> dict[str, Any]:
        for item in self._catalog():
            ident = printed_dataverse_id(item)
            if printed_collection_url(ident, self.list_url) == ref.source_native_uri:
                return item
            if ident == ref.source_native_id:
                return item
        raise SourceError(
            f"DataverseNO list has no printed dataverse matching {ref.source_native_uri}"
        )


def printed_dataverse_entries(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise SourceError("DataverseNO list is not a JSON object")
    entries = body.get("data")
    if not isinstance(entries, list):
        raise SourceError("DataverseNO list has no printed data array")
    listed: list[dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            continue
        try:
            printed_dataverse_id(item)
        except SourceError:
            continue
        listed.append(item)
    return listed


def printed_dataverse_id(item: dict[str, Any]) -> str:
    ident = item.get("id")
    if isinstance(ident, int):
        return str(ident)
    if isinstance(ident, str) and ident.strip():
        return ident.strip()
    raise SourceError("DataverseNO entry has no printed id")


def printed_collection_url(ident: str, list_url: str) -> str:
    """Keep the catalog path and substitute the printed id for :root.

    The live list is `/api/dataverses/:root/contents`. Child collections use
    the same path with the printed id in place of `:root`. No path is
    invented.
    """

    if ROOT_TOKEN not in list_url:
        raise SourceError("DataverseNO list URL has no printed :root token")
    return list_url.replace(ROOT_TOKEN, ident, 1)


def is_sikt_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    return urlsplit(access_path).netloc.lower() == HOST


def sikt_table_id(access_path: str) -> str:
    parts = [part for part in urlsplit(access_path).path.split("/") if part]
    if len(parts) >= 2 and parts[-1] == "contents":
        return parts[-2]
    return parts[-1] if parts else "sikt"


def cells_from_sikt(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed DataverseNO collection members into observation cells.

    Collection arrays keep printed `title` when present, otherwise
    `identifier` or `name`. Other scalars stay as dimensions. Nested
    objects are not copied. Nothing is invented.
    """

    if not isinstance(payload, dict):
        raise ValueError("sikt payload is not a JSON object")
    entries = payload.get("data")
    if not isinstance(entries, list):
        raise ValueError("sikt payload has no printed data array")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        cells.extend(_cells_from_record(item))
    if not cells:
        raise ValueError("sikt payload printed no collection members")
    return cells


def _cells_from_record(item: dict[str, Any]) -> list[tuple[str, Any, dict[str, str]]]:
    scalars = {key: value for key, value in item.items() if _is_scalar(value)}
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
