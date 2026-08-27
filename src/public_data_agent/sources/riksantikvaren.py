from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "riksantikvaren"
SOURCE_NAME = "Riksantikvaren MABYGIS"
LIST_URL = (
    "https://kart.ra.no/arcgis/rest/services/MABYGIS/MABYGIS_rest_ro/FeatureServer?f=json"
)
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a layer name on the official Riksantikvaren MABYGIS "
    f"FeatureServer, capped at {DEFAULT_MAX_ITEMS} layers"
)
RIKSANTIKVAREN_RPS = 2.0
RIKSANTIKVAREN_BURST = 4
HOST = "kart.ra.no"
PATH_PREFIX = "/arcgis/rest/services/MABYGIS/MABYGIS_rest_ro/FeatureServer"
NAME_FIELDS = ("name", "alias")


class RiksantikvarenSource(SourceBase):
    """Replaceable ingest adapter for Riksantikvaren MABYGIS.

    Listing copies layer names the official FeatureServer JSON prints. It
    does not invent ids. Native ids are those printed names. access_path is
    the printed layer id joined to the FeatureServer origin with the same
    f=json format the list API uses. This first slice stays inside that
    printed layers array and caps the walk.
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
            limiter=RateLimiter(RIKSANTIKVAREN_RPS, RIKSANTIKVAREN_BURST),
            timeout=60.0,
        )
        self._spec: dict[str, Any] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = printed_layers(self._catalog())
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            name = printed_layer_name(item)
            refs.append(
                DatasetRef(
                    source_native_uri=printed_layer_url(item["id"], self.list_url),
                    source_native_id=name,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        spec = self._catalog()
        item = _layer_for_ref(spec, ref, self.list_url)
        name = printed_layer_name(item)
        endpoint = printed_layer_url(item["id"], self.list_url)
        payload = {
            "id": name,
            "uri": endpoint,
            "title": {"en": name},
            "description": None,
            "publisher": printed_publisher(spec),
            "license": None,
            "distribution": [
                {
                    "accessURL": [endpoint],
                    "downloadURL": [endpoint],
                }
            ],
            "landingPage": [self.list_url],
            "riksantikvaren_layer": item,
            "riksantikvaren_service": {
                key: spec.get(key)
                for key in ("copyrightText", "serviceDescription", "documentInfo")
                if key in spec
            },
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=name,
            source_native_uri=endpoint,
            fetched_from=self.list_url,
            payload=payload,
        )

    def _catalog(self) -> dict[str, Any]:
        if self._spec is not None:
            return self._spec
        try:
            spec = self.http.get_json(self.list_url)
        except Exception as exc:
            raise SourceError(
                f"Riksantikvaren MABYGIS list failed for {self.list_url}: {exc}"
            ) from exc
        if not isinstance(spec, dict):
            raise SourceError(
                f"Riksantikvaren MABYGIS list is not a JSON object: {self.list_url}"
            )
        if not printed_layers(spec):
            raise SourceError(
                f"Riksantikvaren MABYGIS printed no layers: {self.list_url}"
            )
        self._spec = spec
        return spec


def printed_layers(spec: dict[str, Any]) -> list[dict[str, Any]]:
    layers = spec.get("layers")
    if not isinstance(layers, list):
        raise SourceError("Riksantikvaren MABYGIS list has no printed layers array")
    listed: list[dict[str, Any]] = []
    for item in layers:
        if not isinstance(item, dict):
            continue
        if item.get("id") is None:
            continue
        try:
            printed_layer_name(item)
        except SourceError:
            continue
        listed.append(item)
    return listed


def printed_layer_name(item: dict[str, Any]) -> str:
    name = item.get("name")
    if not isinstance(name, str) or not name.strip():
        raise SourceError("Riksantikvaren MABYGIS layer has no printed name")
    return name.strip()


def printed_layer_url(layer_id: Any, list_url: str) -> str:
    """Join a printed layer id to the FeatureServer origin.

    The live list API is the MABYGIS FeatureServer with f=json. Layer
    documents live at /{id} on that same path and keep the same f=json
    format. No layer id or query filter is invented.
    """

    parts = urlsplit(list_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Riksantikvaren MABYGIS list URL has no printed origin")
    path = parts.path.rstrip("/")
    return f"{parts.scheme}://{parts.netloc}{path}/{layer_id}?f=json"


def printed_publisher(spec: dict[str, Any]) -> dict[str, Any] | None:
    copyright_text = spec.get("copyrightText")
    if not isinstance(copyright_text, str) or not copyright_text.strip():
        return None
    return {"title": {"en": copyright_text.strip()}}


def is_riksantikvaren_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    if parsed.netloc.lower() != HOST:
        return False
    path = parsed.path.rstrip("/")
    if not path.startswith(PATH_PREFIX):
        return False
    rest = path[len(PATH_PREFIX) :].lstrip("/")
    return bool(rest) and rest.isdigit()


def riksantikvaren_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "riksantikvaren"


def cells_from_riksantikvaren(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    if not isinstance(payload, dict):
        raise ValueError("riksantikvaren payload is not a JSON object")
    fields = payload.get("fields")
    if not isinstance(fields, list):
        raise ValueError("riksantikvaren payload has no printed fields array")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in fields:
        if isinstance(item, dict):
            cells.extend(_cells_from_record(item))
    if not cells:
        raise ValueError("riksantikvaren payload printed no fields")
    return cells


def _layer_for_ref(spec: dict[str, Any], ref: DatasetRef, list_url: str) -> dict[str, Any]:
    for item in printed_layers(spec):
        if printed_layer_url(item["id"], list_url) == ref.source_native_uri:
            return item
        if printed_layer_name(item) == ref.source_native_id:
            return item
    raise SourceError(
        f"Riksantikvaren MABYGIS has no printed layer matching {ref.source_native_uri}"
    )


def _cells_from_record(item: dict[str, Any]) -> list[tuple[str, Any, dict[str, str]]]:
    scalars = {key: value for key, value in item.items() if _is_scalar(value)}
    if not scalars:
        return []
    measure = None
    value: Any = None
    for field in NAME_FIELDS:
        printed = scalars.get(field)
        if isinstance(printed, str) and printed.strip():
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
