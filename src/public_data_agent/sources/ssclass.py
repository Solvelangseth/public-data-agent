from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "ssclass"
SOURCE_NAME = "SSB Klass Classifications"
LIST_URL = "https://data.ssb.no/api/klass/v1/classifications"
OPENAPI_URL = "https://data.ssb.no/api/klass/v3/api-docs"
PATH_PREFIX = "/api/klass/v1/classifications"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed classification on the official Klass classifications "
    f"catalog, capped at {DEFAULT_MAX_ITEMS} classifications"
)
SSCLASS_RPS = 2.0
SSCLASS_BURST = 4
HOST = "data.ssb.no"
NAME_FIELDS = ("name", "id")


class SsclassSource(SourceBase):
    """Replaceable ingest adapter for leftover SSB Klass classifications.

    Listing copies printed `_embedded.classifications[].id` values and the
    printed `_links.self.href` from the official
    `/api/klass/v1/classifications` collection. The Klass OpenAPI names that
    collection GET and prints no required query. No `size`, `language`, or
    other optional filter is added. Native ids are the printed `id` values
    so `1` stays distinct from `2`. This first slice stays inside that
    catalog and caps the walk. This is not the SSB PxWeb v0 Statbank
    (`--source ssb`), not PxWebApi 2 (`--source ssbv2`), and not Klass
    version fetch on `/api/klass/v1/versions`.
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
            limiter=RateLimiter(SSCLASS_RPS, SSCLASS_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._catalog()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            ident = printed_classification_id(item)
            refs.append(
                DatasetRef(
                    source_native_uri=printed_item_url(item, self.list_url),
                    source_native_id=ident,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident = ref.source_native_id or ssclass_table_id(ref.source_native_uri or "")
        item = self._catalog_item(ident)
        endpoint = printed_item_url(item, self.list_url)
        title = printed_title(item, ident)
        payload = {
            "id": ident,
            "uri": endpoint,
            "title": title,
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
            "ssclass_classification": {
                key: item[key]
                for key in item
                if key not in ("_links", "versions")
            },
            "ssclass_self_href": endpoint,
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
            raise SourceError(
                f"Klass classifications catalog failed for {self.list_url}: {exc}"
            ) from exc
        listed = printed_classifications(body)
        if not listed:
            raise SourceError("Klass classifications catalog printed no classifications")
        self._listed = listed
        return listed

    def _catalog_item(self, ident: str) -> dict[str, Any]:
        for item in self._catalog():
            if printed_classification_id(item) == ident:
                return item
        raise SourceError(
            f"Klass classifications catalog has no printed classification {ident}"
        )


def printed_classifications(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise SourceError("Klass classifications catalog is not a JSON object")
    embedded = body.get("_embedded")
    if not isinstance(embedded, dict):
        raise SourceError("Klass classifications catalog has no printed _embedded object")
    items = embedded.get("classifications")
    if not isinstance(items, list):
        raise SourceError(
            "Klass classifications catalog has no printed classifications array"
        )
    listed: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            printed_classification_id(item)
        except SourceError:
            continue
        listed.append(item)
    return listed


def printed_classification_id(item: dict[str, Any]) -> str:
    ident = item.get("id")
    if isinstance(ident, bool):
        raise SourceError("Klass classification has no printed id")
    if isinstance(ident, int):
        return str(ident)
    if isinstance(ident, str) and ident.strip():
        return ident.strip()
    raise SourceError("Klass classification has no printed id")


def printed_item_url(item: dict[str, Any], list_url: str) -> str:
    """Copy the printed `_links.self.href`, or join the printed id onto the list path.

    The official Klass OpenAPI names GET `/api/klass/v1/classifications/{id}`.
    The catalog also prints `_links.self.href` for each member. The printed
    href is used when present. No query filter is added.
    """

    links = item.get("_links")
    if isinstance(links, dict):
        self_link = links.get("self")
        if isinstance(self_link, dict):
            href = self_link.get("href")
            if isinstance(href, str) and href.strip():
                return href.strip()
    parts = urlsplit(list_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Klass classifications catalog URL has no printed origin")
    ident = printed_classification_id(item)
    return f"{parts.scheme}://{parts.netloc}{PATH_PREFIX}/{ident}"


def printed_title(item: dict[str, Any], ident: str) -> dict[str, str]:
    name = item.get("name")
    if isinstance(name, str) and name.strip():
        return {"no": name.strip()}
    return {"no": ident}


def is_ssclass_url(access_path: str | None) -> bool:
    """Match the printed collection or `/classifications/{id}` integer path.

    The Klass OpenAPI prints `{id}` as an integer. That rejects leftover
    printed paths under the same prefix such as `/classifications/search`
    and `/classifications/{id}/codes`.
    """

    if not access_path:
        return False
    parsed = urlsplit(access_path)
    if parsed.netloc.lower() != HOST:
        return False
    path = parsed.path.rstrip("/")
    if path == PATH_PREFIX:
        return True
    prefix = PATH_PREFIX + "/"
    if not path.startswith(prefix):
        return False
    rest = path[len(prefix) :]
    return bool(rest) and "/" not in rest and rest.isdigit()


def ssclass_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "ssclass"


def cells_from_ssclass(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed Klass classification versions into observation cells.

    A classification object keeps each printed `versions[]` member. Each
    record keeps printed `name` when present, otherwise `id`. Other
    scalars stay as dimensions. Nested `_links`, `published`, and other
    objects are not copied. If `versions` is absent, the classification
    scalars themselves are copied. Nothing is invented.
    """

    if not isinstance(payload, dict):
        raise ValueError("ssclass payload is not a JSON object")
    versions = payload.get("versions")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    if isinstance(versions, list):
        for item in versions:
            if isinstance(item, dict):
                cells.extend(_cells_from_record(item))
    if not cells:
        cells.extend(_cells_from_record(payload))
    if not cells:
        raise ValueError("ssclass payload printed no classification members")
    return cells


def _cells_from_record(item: dict[str, Any]) -> list[tuple[str, Any, dict[str, str]]]:
    scalars = {key: value for key, value in item.items() if _is_scalar(value)}
    if not scalars:
        return []
    measure = None
    value: Any = None
    for field in NAME_FIELDS:
        printed = scalars.get(field)
        if printed is None:
            continue
        if isinstance(printed, str) and not printed.strip():
            continue
        measure = field
        value = printed
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
