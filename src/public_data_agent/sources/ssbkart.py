from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "ssbkart"
SOURCE_NAME = "Statistisk sentralbyrå kart OGC API Features"
LIST_URL = "https://kart.ssb.no/api/core/v1/ogc/features/collections"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed collection on the official Statistisk sentralbyrå "
    f"kart OGC API Features collections list, capped at {DEFAULT_MAX_ITEMS} collections"
)
SSBKART_RPS = 2.0
SSBKART_BURST = 4
HOST = "kart.ssb.no"
PATH_MARK = "/ogc/features/collections"
ITEMS_JSON_TYPE = "application/json"
NAME_FIELDS = ("navn", "title", "name", "id", "nr")
SKIP_FIELDS = frozenset({"geom", "geometry", "links"})


class SsbkartSource(SourceBase):
    """Replaceable ingest adapter for SSB kart OGC API Features.

    Listing copies printed collection ids and the printed
    `application/json` items href. Native ids are the printed last
    path segment of that href so `fylker_2024` stays distinct from
    `kommuner_2024`. It does not invent collection ids. This first
    slice stays inside that collections document and caps the walk.
    This is not the SSB PxWeb Statbank (`--source ssb`).
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
            limiter=RateLimiter(SSBKART_RPS, SSBKART_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._collection_items()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            refs.append(
                DatasetRef(
                    source_native_uri=item["items_url"],
                    source_native_id=item["id"],
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident = ref.source_native_id or ssbkart_table_id(ref.source_native_uri)
        item = self._collection_item(ident)
        href = item["items_url"]
        title = item["title"]
        description = item.get("description")
        payload = {
            "id": ident,
            "uri": href,
            "title": {"en": title},
            "description": {"en": description} if isinstance(description, str) else None,
            "publisher": None,
            "license": None,
            "distribution": [
                {
                    "accessURL": [href],
                    "downloadURL": [href],
                }
            ],
            "landingPage": [self.list_url],
            "ssbkart_collection": item,
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

    def _collection_items(self) -> list[dict[str, Any]]:
        if self._listed is not None:
            return self._listed
        try:
            body = self.http.get_json(self.list_url)
        except Exception as exc:
            raise SourceError(
                f"SSB kart collections list failed for {self.list_url}: {exc}"
            ) from exc
        listed = printed_collections(body)
        if not listed:
            raise SourceError("SSB kart collections list printed no collections")
        self._listed = listed
        return listed

    def _collection_item(self, ident: str) -> dict[str, Any]:
        for item in self._collection_items():
            if item["id"] == ident:
                return item
        raise SourceError(f"SSB kart collections list has no printed collection {ident}")


def printed_collections(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise SourceError("SSB kart collections list is not a JSON object")
    collections = body.get("collections")
    if not isinstance(collections, list):
        raise SourceError("SSB kart collections list has no printed collections array")
    listed: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in collections:
        if not isinstance(item, dict):
            continue
        href = printed_items_url(item)
        if href is None:
            continue
        ident = printed_collection_id(href)
        catalog_id = item.get("id")
        if ident is None and isinstance(catalog_id, str) and catalog_id.strip():
            ident = catalog_id.strip()
        if ident is None or ident in seen:
            continue
        seen.add(ident)
        title = item.get("title")
        description = item.get("description")
        listed.append(
            {
                "id": ident,
                "catalog_id": catalog_id.strip() if isinstance(catalog_id, str) else None,
                "title": title.strip() if isinstance(title, str) and title.strip() else ident,
                "description": description if isinstance(description, str) else None,
                "items_url": href,
            }
        )
    return listed


def printed_items_url(collection: dict[str, Any]) -> str | None:
    """Copy the printed application/json items href. Do not invent a format."""

    links = collection.get("links")
    if not isinstance(links, list):
        return None
    for link in links:
        if not isinstance(link, dict):
            continue
        if link.get("rel") != "items":
            continue
        if link.get("type") != ITEMS_JSON_TYPE:
            continue
        href = link.get("href")
        if isinstance(href, str) and href.strip():
            return href.strip()
    return None


def printed_collection_id(access_path: str) -> str | None:
    parts = [part for part in urlsplit(access_path).path.split("/") if part]
    if "collections" not in parts:
        return None
    index = parts.index("collections")
    if index + 1 >= len(parts):
        return None
    segment = parts[index + 1]
    if not segment or segment.startswith("items"):
        return None
    return segment


def is_ssbkart_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.lower() == HOST and PATH_MARK in parsed.path


def ssbkart_table_id(access_path: str) -> str:
    ident = printed_collection_id(access_path)
    if ident:
        return ident
    parts = [part for part in urlsplit(access_path).path.split("/") if part]
    if parts:
        last = parts[-1]
        if last.endswith(".json"):
            last = last[: -len(".json")]
        if last and last != "items":
            return last
    return "ssbkart"


def cells_from_ssbkart(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed SSB kart JSON records into observation cells.

    The printed items.json wrapper keeps the `data` array. GeoJSON
    FeatureCollection properties keep a printed name field when present.
    Nested geometry, `geom`, and links are not copied. A collections
    catalog falls back to printed collection id/title.
    """

    records = _records(payload)
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in records:
        cells.extend(_cells_from_record(item))
    if not cells:
        raise ValueError("ssbkart payload printed no records")
    return cells


def _records(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("ssbkart payload is not a JSON object")
    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    features = payload.get("features")
    if isinstance(features, list):
        records: list[dict[str, Any]] = []
        for feature in features:
            if not isinstance(feature, dict):
                continue
            props = feature.get("properties")
            if isinstance(props, dict):
                records.append(props)
            elif _feature_scalars(feature):
                records.append(_feature_scalars(feature))
        return records
    collections = payload.get("collections")
    if isinstance(collections, list):
        return [item for item in collections if isinstance(item, dict)]
    raise ValueError("ssbkart payload is not a printed items wrapper, FeatureCollection, or collections catalog")


def _feature_scalars(feature: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in feature.items()
        if key not in {"properties", "geometry", "type"} and _is_scalar(value)
    }


def _cells_from_record(item: dict[str, Any]) -> list[tuple[str, Any, dict[str, str]]]:
    scalars = {
        key: value
        for key, value in item.items()
        if key not in SKIP_FIELDS and _is_scalar(value)
    }
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
