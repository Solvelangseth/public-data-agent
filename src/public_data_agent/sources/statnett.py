from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "statnett"
SOURCE_NAME = "Statnett Driftsdata"
OPENAPI_URL = "https://driftsdata.statnett.no/restapi/swagger/docs/v1"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a collection GET path in the official Statnett Driftsdata swagger, "
    f"capped at {DEFAULT_MAX_ITEMS} paths"
)
STATNETT_RPS = 2.0
STATNETT_BURST = 4
HOST = "driftsdata.statnett.no"


class StatnettDriftsdataSource(SourceBase):
    """Replaceable ingest adapter for Statnett Driftsdata.

    Listing copies collection GET paths the official swagger document prints.
    It skips templated paths and does not invent endpoint ids. Native ids are
    the printed operationId values so two LastChanges paths stay distinct.
    This first slice stays inside that document and caps the walk.
    """

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = (OPENAPI_URL,)
    ingest_reason = INGEST_REASON

    def __init__(
        self,
        *,
        openapi_url: str = OPENAPI_URL,
        max_items: int = DEFAULT_MAX_ITEMS,
        http: HttpClient | None = None,
    ) -> None:
        self.openapi_url = openapi_url
        self.max_items = max_items
        self.http = http or HttpClient(
            limiter=RateLimiter(STATNETT_RPS, STATNETT_BURST),
            timeout=60.0,
        )
        self._spec: dict[str, Any] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = _listed_get_paths(self._openapi())
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        spec = self._openapi()
        for path, item in sliced:
            endpoint = printed_endpoint_url(spec, path, self.openapi_url)
            refs.append(
                DatasetRef(
                    source_native_uri=endpoint,
                    source_native_id=printed_operation_id(path, item),
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        spec = self._openapi()
        path, item = _path_for_ref(spec, ref)
        operation = item.get("get") if isinstance(item.get("get"), dict) else {}
        summary = operation.get("summary")
        title = (
            summary
            if isinstance(summary, str) and summary.strip()
            else (ref.source_native_id or printed_operation_id(path, item))
        )
        info = spec.get("info") if isinstance(spec.get("info"), dict) else {}
        info_description = info.get("description")
        payload = {
            "id": ref.source_native_id,
            "uri": ref.source_native_uri,
            "title": {"en": title},
            "description": (
                {"en": info_description} if isinstance(info_description, str) else None
            ),
            "publisher": None,
            "license": None,
            "distribution": [
                {
                    "accessURL": [ref.source_native_uri],
                    "downloadURL": [ref.source_native_uri],
                }
            ],
            "landingPage": [self.openapi_url],
            "statnett_openapi_path": path,
            "statnett_openapi_operation": item,
            "statnett_openapi_info": info,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ref.source_native_id,
            source_native_uri=ref.source_native_uri,
            fetched_from=self.openapi_url,
            payload=payload,
        )

    def _openapi(self) -> dict[str, Any]:
        if self._spec is not None:
            return self._spec
        try:
            spec = self.http.get_json(self.openapi_url)
        except Exception as exc:
            raise SourceError(
                f"Statnett Driftsdata swagger list failed for {self.openapi_url}: {exc}"
            ) from exc
        if not isinstance(spec, dict):
            raise SourceError(f"Statnett Driftsdata swagger is not a JSON object: {self.openapi_url}")
        self._spec = spec
        return spec


def printed_operation_id(path: str, item: dict[str, Any] | None = None) -> str:
    if isinstance(item, dict):
        operation = item.get("get") if isinstance(item.get("get"), dict) else {}
        ident = operation.get("operationId")
        if isinstance(ident, str) and ident.strip():
            return ident.strip()
    segment = path.rstrip("/").split("/")[-1]
    if not segment:
        raise SourceError("Statnett swagger path has no printed operation id")
    return segment


def printed_endpoint_url(spec: dict[str, Any], path: str, openapi_url: str) -> str:
    """Join a printed swagger 2.0 host/basePath/path, or the document origin.

    The live Driftsdata spec prints `host`, `basePath`, and `schemes`. Those
    values are copied. No table id is invented.
    """

    host = spec.get("host")
    base_path = spec.get("basePath")
    schemes = spec.get("schemes") if isinstance(spec.get("schemes"), list) else []
    suffix = path if path.startswith("/") else f"/{path}"
    prefix = base_path if isinstance(base_path, str) else ""
    if prefix and not prefix.startswith("/"):
        prefix = f"/{prefix}"
    if prefix.endswith("/"):
        prefix = prefix[:-1]
    if isinstance(host, str) and host.strip():
        doc_scheme = urlsplit(openapi_url).scheme or "https"
        printed_scheme = None
        for candidate in schemes:
            if isinstance(candidate, str) and candidate.strip():
                printed_scheme = candidate.strip()
                if printed_scheme == "https":
                    break
        scheme = printed_scheme or doc_scheme
        return f"{scheme}://{host.strip()}{prefix}{suffix}"
    parts = urlsplit(openapi_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Statnett swagger URL has no printed origin")
    return f"{parts.scheme}://{parts.netloc}{prefix}{suffix}"


def is_statnett_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.lower() == HOST


def statnett_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "statnett"


FREQUENCY_PATHS = frozenset({
    "/restapi/frequency/byminute",
    "/restapi/frequency/bysecond",
})
FREQUENCY_MAX_CELLS = 100


def is_statnett_frequency_url(access_path: str | None) -> bool:
    if not is_statnett_url(access_path):
        return False
    path = urlsplit(access_path).path.rstrip("/").casefold()
    return path in FREQUENCY_PATHS


def cells_from_statnett_frequency(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed Frequency Measurements into observation cells.

    The envelope prints ``StartPointUTC``, ``PeriodTickMs``, and a
    ``Measurements`` array of Hz values. Each cell's time is
    StartPointUTC + i * PeriodTickMs from those printed fields, the same
    reconstruction json-stat does from a printed index. Measure name is the
    printed key ``Measurements``. An empty array is an error, not a zero.
    """

    if not isinstance(payload, dict):
        raise ValueError("statnett frequency payload is not a JSON object")
    measurements = payload.get("Measurements")
    if not isinstance(measurements, list):
        raise ValueError("statnett frequency payload printed no Measurements array")
    start = payload.get("StartPointUTC")
    period = payload.get("PeriodTickMs")
    if not isinstance(start, (int, float)) or isinstance(start, bool):
        raise ValueError("statnett frequency payload printed no numeric StartPointUTC")
    if not isinstance(period, (int, float)) or isinstance(period, bool):
        raise ValueError("statnett frequency payload printed no numeric PeriodTickMs")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for i, value in enumerate(measurements):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        tick = start + i * period
        dims = {
            "StartPointUTC": _as_dim(tick),
            "PeriodTickMs": _as_dim(period),
        }
        cells.append(("Measurements", value, dims))
    if not cells:
        raise ValueError("statnett frequency payload printed no numeric Measurements")
    return cells


def cells_from_statnett(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed Statnett JSON records into observation cells.

    Collection arrays keep printed `elspotId` when present, otherwise `name`
    or `id`. Other scalars stay as dimensions. Nested objects such as
    `translatedText` are not copied.
    """

    if not isinstance(payload, list):
        raise ValueError("statnett payload is not a JSON array")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        cells.extend(_cells_from_record(item))
    return cells


def _listed_get_paths(spec: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        raise SourceError("Statnett swagger has no printed paths object")
    listed: list[tuple[str, dict[str, Any]]] = []
    for path, item in paths.items():
        if not isinstance(path, str) or not isinstance(item, dict):
            continue
        if "{" in path:
            continue
        if not isinstance(item.get("get"), dict):
            continue
        listed.append((path, item))
    return listed


def _path_for_ref(spec: dict[str, Any], ref: DatasetRef) -> tuple[str, dict[str, Any]]:
    for path, item in _listed_get_paths(spec):
        if printed_endpoint_url(spec, path, OPENAPI_URL) == ref.source_native_uri:
            return path, item
        if printed_operation_id(path, item) == ref.source_native_id:
            return path, item
    raise SourceError(
        f"Statnett swagger has no printed path matching {ref.source_native_uri}"
    )


def _cells_from_record(item: dict[str, Any]) -> list[tuple[str, Any, dict[str, str]]]:
    scalars = {key: value for key, value in item.items() if _is_scalar(value)}
    if not scalars:
        return []
    if "elspotId" in scalars:
        measure = "elspotId"
        value = scalars["elspotId"]
    elif "name" in scalars:
        measure = "name"
        value = scalars["name"]
    elif "id" in scalars:
        measure = "id"
        value = scalars["id"]
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
