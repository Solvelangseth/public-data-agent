from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "hi"
SOURCE_NAME = "Havforskningsinstituttet OGC API Features"
LIST_URL = "https://kart.hi.no/data/ogc/features/v1/collections"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed collection on the official Havforskningsinstituttet "
    f"OGC API Features collections list, capped at {DEFAULT_MAX_ITEMS} collections"
)
HI_RPS = 2.0
HI_BURST = 4
HOST = "kart.hi.no"
PATH_MARK = "/data/ogc/features/v1/"
ITEMS_JSON_TYPE = "application/json"
NAME_FIELDS = ("navn", "Description", "Station", "title", "name", "id", "fid")


class HiFeaturesSource(SourceBase):
    """Replaceable ingest adapter for Havforskningsinstituttet OGC API Features.

    Listing copies printed collection `id` values and the printed
    `application/json` items href. It does not invent collection ids. This
    first slice stays inside that collections document and caps the walk.
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
            limiter=RateLimiter(HI_RPS, HI_BURST),
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
        ident = ref.source_native_id or hi_table_id(ref.source_native_uri)
        item = self._collection_item(ident)
        href = item["items_url"]
        title = item["title"]
        description = item.get("description")
        payload = {
            "id": ident,
            "uri": href,
            "title": {"no": title},
            "description": {"no": description} if isinstance(description, str) else None,
            "publisher": None,
            "license": None,
            "distribution": [
                {
                    "accessURL": [href],
                    "downloadURL": [href],
                }
            ],
            "landingPage": [self.list_url],
            "hi_collection": item,
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
                f"Havforskningsinstituttet collections list failed for {self.list_url}: {exc}"
            ) from exc
        listed = printed_collections(body)
        if not listed:
            raise SourceError("Havforskningsinstituttet collections list printed no collections")
        self._listed = listed
        return listed

    def _collection_item(self, ident: str) -> dict[str, Any]:
        for item in self._collection_items():
            if item["id"] == ident:
                return item
        raise SourceError(
            f"Havforskningsinstituttet collections list has no printed collection {ident}"
        )


def printed_collections(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise SourceError("Havforskningsinstituttet collections list is not a JSON object")
    collections = body.get("collections")
    if not isinstance(collections, list):
        raise SourceError("Havforskningsinstituttet collections list has no printed collections array")
    listed: list[dict[str, Any]] = []
    for item in collections:
        if not isinstance(item, dict):
            continue
        ident = item.get("id")
        href = printed_items_url(item)
        if not isinstance(ident, str) or not ident.strip() or href is None:
            continue
        title = item.get("title")
        description = item.get("description")
        listed.append(
            {
                "id": ident.strip(),
                "title": title.strip() if isinstance(title, str) and title.strip() else ident.strip(),
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


def is_hi_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.lower() == HOST and PATH_MARK in parsed.path


def hi_table_id(access_path: str) -> str:
    parts = [part for part in urlsplit(access_path).path.split("/") if part]
    if "collections" in parts:
        index = parts.index("collections")
        if index + 1 < len(parts) and parts[index + 1] != "items":
            return parts[index + 1]
    if parts:
        return parts[-1]
    raise SourceError("Havforskningsinstituttet URL has no printed collection id")


def cells_from_hi(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed HI JSON records into observation cells.

    GeoJSON FeatureCollection properties keep a printed name field when
    present. Nested geometry and links are not copied. A collections
    catalog falls back to printed collection id/title.
    """

    records = _records(payload)
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in records:
        cells.extend(_cells_from_record(item))
    if not cells:
        raise ValueError("hi payload printed no records")
    return cells


def _records(payload: Any) -> list[dict[str, Any]]:
    return [props for props, _geometry in _records_with_geometry(payload)]


def _records_with_geometry(payload: Any) -> list[tuple[dict[str, Any], Any]]:
    """Each member's properties, and the geometry published beside them.

    One traversal for both, because the alternative is two that have to agree
    about which members were skipped. A collections catalog and a feature with
    no properties object have no geometry to carry, and that is `None` rather
    than an empty shape.
    """

    if not isinstance(payload, dict):
        raise ValueError("hi payload is not a JSON object")
    features = payload.get("features")
    if isinstance(features, list):
        records: list[tuple[dict[str, Any], Any]] = []
        for feature in features:
            if not isinstance(feature, dict):
                continue
            geometry = feature.get("geometry")
            props = feature.get("properties")
            if isinstance(props, dict):
                records.append((props, geometry))
            elif _feature_scalars(feature):
                records.append((_feature_scalars(feature), geometry))
        return records
    collections = payload.get("collections")
    if isinstance(collections, list):
        return [(item, None) for item in collections if isinstance(item, dict)]
    raise ValueError("hi payload is not a GeoJSON FeatureCollection or collections catalog")


def cells_and_geometry_from_hi(
    payload: Any,
) -> list[tuple[tuple[str, Any, dict[str, str]], Any]]:
    """Cells as `cells_from_hi` builds them, each paired with its geometry.

    A feature without its geometry is half a feature: `omraader_inkludert_i_
    raadgivningskart_2025` says a spawning ground is a high-concentration
    area and never says where. The cell carries the properties, as it always
    has, and the geometry rides alongside so a record can keep it.
    """

    paired: list[tuple[tuple[str, Any, dict[str, str]], Any]] = []
    for props, geometry in _records_with_geometry(payload):
        for cell in _cells_from_record(props):
            paired.append((cell, geometry))
    if not paired:
        raise ValueError("hi payload printed no records")
    return paired


def _feature_scalars(feature: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in feature.items()
        if key not in {"properties", "geometry", "type"} and _is_scalar(value)
    }


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
