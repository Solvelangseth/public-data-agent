from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "entur"
SOURCE_NAME = "Entur mobility GBFS"
LIST_URL = "https://api.entur.io/mobility/v2/gbfs"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed system on the official Entur mobility GBFS list, "
    f"capped at {DEFAULT_MAX_ITEMS} systems"
)
ENTUR_RPS = 2.0
ENTUR_BURST = 4
HOST = "api.entur.io"
PATH_PREFIX = "/mobility/v2/gbfs"
VEHICLE_TYPES_FEED = "vehicle_types"


class EnturGbfsSource(SourceBase):
    """Replaceable ingest adapter for the official Entur mobility GBFS list.

    Listing copies printed `id` and `url` values from the systems array.
    It does not invent system ids. This first slice caps the walk.
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
            limiter=RateLimiter(ENTUR_RPS, ENTUR_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, str]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._system_items()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            refs.append(
                DatasetRef(
                    source_native_uri=item["url"],
                    source_native_id=item["id"],
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident = ref.source_native_id or printed_system_id(ref.source_native_uri)
        item = self._system_item(ident)
        href = item["url"]
        payload = {
            "id": ident,
            "uri": href,
            "title": {"en": ident},
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
            "entur_system": item,
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

    def _system_items(self) -> list[dict[str, str]]:
        if self._listed is not None:
            return self._listed
        try:
            body = self.http.get_json(self.list_url)
        except Exception as exc:
            raise SourceError(f"Entur GBFS system list failed for {self.list_url}: {exc}") from exc
        listed = printed_systems(body)
        if not listed:
            raise SourceError("Entur GBFS system list printed no systems")
        self._listed = listed
        return listed

    def _system_item(self, ident: str) -> dict[str, str]:
        for item in self._system_items():
            if item["id"] == ident:
                return item
        raise SourceError(f"Entur GBFS system list has no printed system {ident}")


def printed_systems(body: Any) -> list[dict[str, str]]:
    if not isinstance(body, dict):
        raise SourceError("Entur GBFS system list is not a JSON object")
    systems = body.get("systems")
    if not isinstance(systems, list):
        raise SourceError("Entur GBFS system list has no printed systems array")
    listed: list[dict[str, str]] = []
    for item in systems:
        if not isinstance(item, dict):
            continue
        ident = item.get("id")
        url = item.get("url")
        if isinstance(ident, str) and ident.strip() and isinstance(url, str) and url.strip():
            listed.append({"id": ident.strip(), "url": url.strip()})
    return listed


def printed_feeds(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    if isinstance(data.get("feeds"), list):
        return [item for item in data["feeds"] if isinstance(item, dict)]
    for value in data.values():
        if isinstance(value, dict) and isinstance(value.get("feeds"), list):
            return [item for item in value["feeds"] if isinstance(item, dict)]
    return []


def printed_feed_url(payload: Any, name: str) -> str | None:
    for feed in printed_feeds(payload):
        feed_name = feed.get("name")
        url = feed.get("url")
        if feed_name == name and isinstance(url, str) and url.strip():
            return url.strip()
    return None


def printed_system_id(access_path: str) -> str:
    parts = [part for part in urlsplit(access_path).path.split("/") if part]
    if len(parts) >= 2 and parts[-1] == "gbfs":
        return parts[-2]
    if parts:
        return parts[-1]
    raise SourceError("Entur GBFS URL has no printed system id")


def is_entur_gbfs_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.lower() == HOST and parsed.path.startswith(PATH_PREFIX)


def entur_table_id(access_path: str) -> str:
    return printed_system_id(access_path)


def cells_from_entur(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed GBFS records into observation cells.

    Vehicle-type, station, and bike arrays keep a printed name or id.
    Discovery documents fall back to printed feed name/url. Nothing is
    invented.
    """

    if not isinstance(payload, dict):
        raise ValueError("entur payload is not a JSON object")
    records = _records(payload)
    if not records:
        raise ValueError("entur payload printed no records")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in records:
        cells.extend(_cells_from_record(item))
    return cells


def _records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("vehicle_types", "stations", "bikes", "regions", "plans", "alerts"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if "system_id" in data:
            return [data]
    feeds = printed_feeds(payload)
    return feeds


def _cells_from_record(item: dict[str, Any]) -> list[tuple[str, Any, dict[str, str]]]:
    scalars = {key: value for key, value in item.items() if _is_scalar(value)}
    if not scalars:
        return []
    for key in ("name", "vehicle_type_id", "station_id", "bike_id", "url"):
        if key in scalars:
            measure = key
            value = scalars[key]
            break
    else:
        measure, value = next(iter(scalars.items()))
    dims = {key: _as_dim(other) for key, other in scalars.items() if key != measure}
    return [(measure, value, dims)]


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _as_dim(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
