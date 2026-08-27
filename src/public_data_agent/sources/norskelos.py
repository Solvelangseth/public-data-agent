from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "norskelos"
SOURCE_NAME = "Kartverket Den norske los"
OPENAPI_URL = "https://dnl.kartverket.no/api/ogc/v1/openapi"
COLLECTIONS_URL = "https://dnl.kartverket.no/api/ogc/v1/collections"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a collection id on the official Kartverket Den norske los "
    f"OGC API Features catalog, capped at {DEFAULT_MAX_ITEMS} collections"
)
NORSKELOS_RPS = 2.0
NORSKELOS_BURST = 4
HOST = "dnl.kartverket.no"
PATH_PREFIX = "/api/ogc/v1/"
NAME_FIELDS = ("title", "title_no", "title_en", "name", "id")


class NorskelosSource(SourceBase):
    """Replaceable ingest adapter for Kartverket Den norske los.

    Listing copies collection ids the official OGC API Features catalog
    prints. It skips collections that print no id or no items GET href.
    Native ids are the last printed collection-id segment. access_path is
    the printed GeoJSON items href. License is the printed OpenAPI license
    URL. This first slice stays inside that catalog and caps the walk.
    """

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = (COLLECTIONS_URL,)
    ingest_reason = INGEST_REASON

    def __init__(
        self,
        *,
        collections_url: str = COLLECTIONS_URL,
        openapi_url: str = OPENAPI_URL,
        max_items: int = DEFAULT_MAX_ITEMS,
        http: HttpClient | None = None,
    ) -> None:
        self.collections_url = collections_url
        self.openapi_url = openapi_url
        self.max_items = max_items
        self.http = http or HttpClient(
            limiter=RateLimiter(NORSKELOS_RPS, NORSKELOS_BURST),
            timeout=60.0,
        )
        self._catalog: dict[str, Any] | None = None
        self._spec: dict[str, Any] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = printed_collections(self._collections())
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            refs.append(
                DatasetRef(
                    source_native_uri=printed_items_url(item),
                    source_native_id=printed_collection_id(item),
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        catalog = self._collections()
        item = _collection_for_ref(catalog, ref)
        ident = printed_collection_id(item)
        endpoint = printed_items_url(item)
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            title = ident
        description = item.get("description")
        info = self._openapi().get("info")
        info = info if isinstance(info, dict) else {}
        payload = {
            "id": ident,
            "uri": endpoint,
            "title": {"en": title},
            "description": (
                {"en": description} if isinstance(description, str) else None
            ),
            "publisher": None,
            "license": printed_license_url(info),
            "distribution": [
                {
                    "accessURL": [endpoint],
                    "downloadURL": [endpoint],
                }
            ],
            "landingPage": [self.collections_url],
            "norskelos_collection": item,
            "norskelos_openapi_info": info,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ident,
            source_native_uri=endpoint,
            fetched_from=self.collections_url,
            payload=payload,
        )

    def _collections(self) -> dict[str, Any]:
        if self._catalog is not None:
            return self._catalog
        try:
            spec = self.http.get_json(self.collections_url)
        except Exception as exc:
            raise SourceError(
                f"Kartverket Den norske los catalog failed for {self.collections_url}: {exc}"
            ) from exc
        if not isinstance(spec, dict):
            raise SourceError(
                f"Kartverket Den norske los catalog is not a JSON object: {self.collections_url}"
            )
        if not printed_collections(spec):
            raise SourceError(
                f"Kartverket Den norske los catalog printed no collections: {self.collections_url}"
            )
        self._catalog = spec
        return spec

    def _openapi(self) -> dict[str, Any]:
        if self._spec is not None:
            return self._spec
        try:
            spec = self.http.get_json(self.openapi_url)
        except Exception as exc:
            raise SourceError(
                f"Kartverket Den norske los OpenAPI failed for {self.openapi_url}: {exc}"
            ) from exc
        if not isinstance(spec, dict):
            raise SourceError(
                f"Kartverket Den norske los OpenAPI is not a JSON object: {self.openapi_url}"
            )
        self._spec = spec
        return spec


def printed_license_url(info: dict[str, Any]) -> str | None:
    license_info = info.get("license")
    if not isinstance(license_info, dict):
        return None
    url = license_info.get("url")
    if isinstance(url, str) and url.strip():
        return url.strip()
    return None


def printed_collection_id(item: dict[str, Any]) -> str:
    ident = item.get("id")
    if not isinstance(ident, str) or not ident.strip():
        raise SourceError("Kartverket Den norske los collection has no printed id")
    segment = ident.strip().rstrip("/").split("/")[-1]
    if not segment:
        raise SourceError("Kartverket Den norske los collection id has no last segment")
    return segment


def printed_items_url(item: dict[str, Any]) -> str:
    """Copy the printed GeoJSON items href. Do not invent a path."""

    links = item.get("links")
    if not isinstance(links, list):
        raise SourceError("Kartverket Den norske los collection has no printed links")
    fallback = None
    for link in links:
        if not isinstance(link, dict):
            continue
        if link.get("rel") != "items":
            continue
        href = link.get("href")
        if not isinstance(href, str) or not href.strip():
            continue
        href = href.strip()
        typ = link.get("type")
        if typ in ("application/geo+json", "application/json"):
            return href
        if fallback is None:
            fallback = href
    if fallback is not None:
        return fallback
    raise SourceError("Kartverket Den norske los collection has no printed items href")


def is_norskelos_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.lower() == HOST and parsed.path.startswith(PATH_PREFIX)


def norskelos_table_id(access_path: str) -> str:
    parts = urlsplit(access_path).path.rstrip("/").split("/")
    if parts and parts[-1] == "items" and len(parts) >= 2:
        return parts[-2]
    return parts[-1] if parts and parts[-1] else "norskelos"


def cells_from_norskelos(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed Den norske los GeoJSON feature properties into cells.

    Feature `properties` keep printed `title` when present, otherwise
    `title_no`, `title_en`, `name`, or `id`. A printed Feature `id` is
    copied into the record when properties have no `id`. Other scalars
    stay as dimensions. Geometry and nested objects are not copied.
    """

    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        raise ValueError("norskelos payload is not a GeoJSON FeatureCollection")
    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("norskelos FeatureCollection has no features array")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for feature in features:
        if not isinstance(feature, dict):
            continue
        props = feature.get("properties")
        if not isinstance(props, dict):
            continue
        record = dict(props)
        feature_id = feature.get("id")
        if "id" not in record and feature_id is not None and _is_scalar(feature_id):
            record["id"] = feature_id
        cells.extend(_cells_from_record(record))
    return cells


def printed_collections(spec: dict[str, Any]) -> list[dict[str, Any]]:
    collections = spec.get("collections")
    if not isinstance(collections, list):
        raise SourceError(
            "Kartverket Den norske los catalog has no printed collections array"
        )
    listed: list[dict[str, Any]] = []
    for item in collections:
        if not isinstance(item, dict):
            continue
        try:
            printed_collection_id(item)
            printed_items_url(item)
        except SourceError:
            continue
        listed.append(item)
    return listed


def _collection_for_ref(spec: dict[str, Any], ref: DatasetRef) -> dict[str, Any]:
    for item in printed_collections(spec):
        if printed_items_url(item) == ref.source_native_uri:
            return item
        if printed_collection_id(item) == ref.source_native_id:
            return item
    raise SourceError(
        f"Kartverket Den norske los catalog has no printed collection matching {ref.source_native_uri}"
    )


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
