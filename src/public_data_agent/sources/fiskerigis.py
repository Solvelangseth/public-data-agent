from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "fiskerigis"
SOURCE_NAME = "Fiskeridirektoratet GIS"
LIST_URL = "https://gis.fiskeridir.no/arcgis/rest/services?f=json"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed name+type service on the official Fiskeridirektoratet "
    f"ArcGIS REST services catalog, capped at {DEFAULT_MAX_ITEMS} paths"
)
FISKERIGIS_RPS = 2.0
FISKERIGIS_BURST = 4
HOST = "gis.fiskeridir.no"
PATH_MARK = "/arcgis/rest/services"
JSON_QUERY = "f=json"
NAME_FIELDS = ("name", "mapName", "title", "id")
PRINTED_ARRAY_KEYS = ("layers", "services")
SERVER_TYPES = ("MapServer", "FeatureServer", "ImageServer", "GPServer")


class FiskerigisSource(SourceBase):
    """Replaceable ingest adapter for Fiskeridirektoratet ArcGIS REST services.

    Listing copies printed `services` entries the official JSON catalog
    prints. It skips folders and entries with no name or type. Native
    ids are the printed last path segment of `name` so
    `AIS_density_Norge_2016` stays distinct from
    `AIS_Route_Density_2020`. Access URLs keep the printed name, printed
    type, and the catalog's `f=json` query. This first slice stays inside
    that catalog and caps the walk. This is not Fartøyregisteret
    (`--source fiskeridir`), not Kjøperregisteret (`--source buyer`),
    not NYTEK (`--source nytek`), not Akvakulturregister
    (`--source aqua`), not NVE Mapservices (`--source nvemap`),
    and not Norsk Polarinstitutt ArcticSDI (`--source arcticsdi`).
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
            limiter=RateLimiter(FISKERIGIS_RPS, FISKERIGIS_BURST),
            timeout=60.0,
        )
        self._listed: list[tuple[str, str, str]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._listed_services()
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
        ident, href, title = _href_for_ref(self._listed_services(), ref)
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
            "fiskerigis_service_id": ident,
            "fiskerigis_service_href": href,
            "fiskerigis_service_title": title,
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

    def _listed_services(self) -> list[tuple[str, str, str]]:
        if self._listed is not None:
            return self._listed
        try:
            body = self.http.get_json(self.list_url)
        except Exception as exc:
            raise SourceError(
                f"Fiskeridirektoratet GIS services catalog failed for {self.list_url}: {exc}"
            ) from exc
        listed = printed_services(body, self.list_url)
        if not listed:
            raise SourceError(
                f"Fiskeridirektoratet GIS services catalog printed no services: {self.list_url}"
            )
        self._listed = listed
        return listed


def printed_services(body: Any, list_url: str) -> list[tuple[str, str, str]]:
    """Copy printed name+type entries from the services catalog."""

    if not isinstance(body, dict):
        raise SourceError("Fiskeridirektoratet GIS services catalog is not a JSON object")
    services = body.get("services")
    if not isinstance(services, list):
        raise SourceError(
            "Fiskeridirektoratet GIS services catalog has no printed services array"
        )
    origin = _catalog_origin(list_url)
    listed: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for item in services:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        typ = item.get("type")
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(typ, str) or not typ.strip():
            continue
        name = name.strip()
        typ = typ.strip()
        ident = printed_service_id(name)
        if ident is None or ident in seen:
            continue
        seen.add(ident)
        href = f"{origin}{PATH_MARK}/{name}/{typ}?{JSON_QUERY}"
        listed.append((ident, href, ident))
    return listed


def printed_service_id(name: str) -> str | None:
    segment = name.rstrip("/").split("/")[-1] if name else ""
    if not segment:
        return None
    return segment


def is_fiskerigis_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.lower() == HOST and PATH_MARK in parsed.path


def fiskerigis_table_id(access_path: str) -> str:
    path = urlsplit(access_path).path.rstrip("/")
    parts = [part for part in path.split("/") if part]
    if len(parts) >= 2 and parts[-1] in SERVER_TYPES:
        return parts[-2]
    ident = printed_service_id(path)
    return ident or "fiskerigis"


def cells_from_fiskerigis(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed Fiskeridirektoratet GIS JSON into cells.

    MapServer catalogs keep the printed `layers` array. Folder catalogs
    keep the printed `services` array. A single metadata object keeps
    printed `name` when present, otherwise `mapName`, `title`, or `id`.
    Other scalars stay as dimensions. Nested objects and arrays are not
    copied. Nothing is invented.
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
            folders = payload.get("folders")
            if isinstance(folders, list):
                for item in folders:
                    if _is_scalar(item) and item is not None:
                        cells.append(("value", item, {}))
            else:
                cells.extend(_cells_from_record(payload))
    elif _is_scalar(payload) and payload is not None:
        cells.append(("value", payload, {}))
    else:
        raise ValueError("fiskerigis payload is not a JSON object, array, or scalar")
    if not cells:
        raise ValueError("fiskerigis payload printed no collection members")
    return cells


def _catalog_origin(list_url: str) -> str:
    parsed = urlsplit(list_url)
    if not parsed.scheme or not parsed.netloc:
        raise SourceError("Fiskeridirektoratet GIS catalog URL has no printed origin")
    return f"{parsed.scheme}://{parsed.netloc}"


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
        "Fiskeridirektoratet GIS services catalog has no printed service "
        f"matching {ref.source_native_uri}"
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
