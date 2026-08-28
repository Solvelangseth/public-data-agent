from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "hitiles"
SOURCE_NAME = "Havforskningsinstituttet OGC Tiles"
LIST_URL = "https://kart.hi.no/data/ogc/tiles/v1"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed application/json GET href on the official "
    f"Havforskningsinstituttet OGC Tiles landing page, capped at {DEFAULT_MAX_ITEMS} paths"
)
HITILES_RPS = 2.0
HITILES_BURST = 4
HOST = "kart.hi.no"
PATH_MARK = "/data/ogc/tiles/v1"
JSON_TYPE = "application/json"
SKIP_RELS = ("self", "alternate")
NAME_FIELDS = ("title", "name", "id")
PRINTED_ARRAY_KEYS = ("collections", "tileMatrixSets")


class HitilesSource(SourceBase):
    """Replaceable ingest adapter for Havforskningsinstituttet OGC API Tiles.

    Listing copies printed `application/json` GET hrefs the official landing
    page prints. It skips `self` / `alternate` links and hrefs with no last
    path segment. Native ids are the printed last path segment so
    `/tileMatrixSets` stays distinct from `/conformance`. This first slice
    stays inside that landing page and caps the walk. This is not
    Havforskningsinstituttet OGC Features (`--source hi`), not
    Havforskningsinstituttet OGC Coverages (`--source hicoverages`), not
    Havforskningsinstituttet OGC Maps (`--source himaps`), and not
    Havforskningsinstituttet OGC Styles (`--source histyles`).
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
            limiter=RateLimiter(HITILES_RPS, HITILES_BURST),
            timeout=60.0,
        )
        self._listed: list[tuple[str, str, str]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._listed_hrefs()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for ident, href, _title in sliced:
            refs.append(
                DatasetRef(
                    source_native_uri=href,
                    source_native_id=ident,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident, href, title = _href_for_ref(self._listed_hrefs(), ref)
        payload = {
            "id": ident,
            "uri": href,
            "title": {"en": title},
            "description": None,
            "publisher": None,
            "license": None,
            "distribution": [
                {
                    "accessURL": [href],
                    "downloadURL": [href],
                }
            ],
            "landingPage": [self.list_url],
            "hitiles_landing_id": ident,
            "hitiles_landing_href": href,
            "hitiles_landing_title": title,
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

    def _listed_hrefs(self) -> list[tuple[str, str, str]]:
        if self._listed is not None:
            return self._listed
        try:
            body = self.http.get_json(self.list_url)
        except Exception as exc:
            raise SourceError(
                f"Havforskningsinstituttet OGC Tiles landing page failed for {self.list_url}: {exc}"
            ) from exc
        listed = printed_json_get_hrefs(body)
        if not listed:
            raise SourceError(
                f"Havforskningsinstituttet OGC Tiles landing page printed no JSON GET hrefs: {self.list_url}"
            )
        self._listed = listed
        return listed


def printed_json_get_hrefs(body: Any) -> list[tuple[str, str, str]]:
    """Copy printed application/json GET hrefs from the landing-page links array."""

    if not isinstance(body, dict):
        raise SourceError("Havforskningsinstituttet OGC Tiles landing page is not a JSON object")
    links = body.get("links")
    if not isinstance(links, list):
        raise SourceError(
            "Havforskningsinstituttet OGC Tiles landing page has no printed links array"
        )
    listed: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for link in links:
        if not isinstance(link, dict):
            continue
        if link.get("type") != JSON_TYPE:
            continue
        rel = link.get("rel")
        if isinstance(rel, str) and rel in SKIP_RELS:
            continue
        href = link.get("href")
        if not isinstance(href, str) or not href.strip():
            continue
        href = href.strip()
        ident = printed_operation_id(href)
        if ident is None or ident in seen:
            continue
        seen.add(ident)
        title = link.get("title")
        printed_title = (
            title.strip()
            if isinstance(title, str) and title.strip()
            else ident
        )
        listed.append((ident, href, printed_title))
    return listed


def printed_operation_id(href: str) -> str | None:
    path = urlsplit(href).path.rstrip("/")
    segment = path.split("/")[-1] if path else ""
    if not segment:
        return None
    return segment


def is_hitiles_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.lower() == HOST and PATH_MARK in parsed.path


def hitiles_table_id(access_path: str) -> str:
    ident = printed_operation_id(access_path)
    return ident or "hitiles"


def cells_from_hitiles(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed Havforskningsinstituttet OGC Tiles JSON into cells.

    Tile-matrix catalogs keep the printed `tileMatrixSets` array. Collection
    catalogs keep the printed `collections` array. Conformance catalogs keep
    printed `conformsTo` URIs. A single metadata object keeps printed
    `title` when present, otherwise `name` or `id`. Other scalars stay as
    dimensions. Nested objects and arrays are not copied. Nothing is invented.
    """

    cells: list[tuple[str, Any, dict[str, str]]] = []
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                cells.extend(_cells_from_record(item))
            elif _is_scalar(item) and item is not None:
                cells.append(("value", item, {}))
    elif isinstance(payload, dict):
        for key in PRINTED_ARRAY_KEYS:
            printed = payload.get(key)
            if isinstance(printed, list):
                for item in printed:
                    if isinstance(item, dict):
                        cells.extend(_cells_from_record(item))
                    elif _is_scalar(item) and item is not None:
                        cells.append(("value", item, {}))
                break
        else:
            conforms = payload.get("conformsTo")
            if isinstance(conforms, list):
                for item in conforms:
                    if _is_scalar(item) and item is not None:
                        cells.append(("value", item, {}))
            else:
                cells.extend(_cells_from_record(payload))
    elif _is_scalar(payload) and payload is not None:
        cells.append(("value", payload, {}))
    else:
        raise ValueError("hitiles payload is not a JSON object, array, or scalar")
    if not cells:
        raise ValueError("hitiles payload printed no collection members")
    return cells


def _href_for_ref(
    listed: list[tuple[str, str, str]],
    ref: DatasetRef,
) -> tuple[str, str, str]:
    for ident, href, title in listed:
        if href == ref.source_native_uri:
            return ident, href, title
        if ident == ref.source_native_id:
            return ident, href, title
    raise SourceError(
        f"Havforskningsinstituttet OGC Tiles landing page has no printed href matching {ref.source_native_uri}"
    )


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
