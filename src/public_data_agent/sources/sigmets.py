from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "sigmets"
SOURCE_NAME = "Meteorologisk institutt Sigmets"
OPENAPI_URL = "https://api.met.no/weatherapi/sigmets/2.0/swagger"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a collection GET path in the official MET Sigmets swagger, "
    f"capped at {DEFAULT_MAX_ITEMS} paths"
)
SIGMETS_RPS = 2.0
SIGMETS_BURST = 4
HOST = "api.met.no"
PATH_PREFIX = "/weatherapi/sigmets/"
NAME_FIELDS = ("name", "title", "id")


class SigmetsSource(SourceBase):
    """Replaceable ingest adapter for MET Sigmets.

    Listing copies collection GET paths the official swagger document prints.
    It skips templated paths and GET operations that print required query
    parameters. The root product path has no last-segment id and is not a
    collection list. This first slice stays inside that document and caps
    the walk. This is not Metalerts (`--source met`), not MET Sigcharts
    (`--source sigcharts`), and not MET Aviationforecast.
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
            limiter=RateLimiter(SIGMETS_RPS, SIGMETS_BURST),
            timeout=60.0,
        )
        self._spec: dict[str, Any] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = _listed_get_paths(self._openapi())
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        spec = self._openapi()
        for path, _item in sliced:
            endpoint = printed_endpoint_url(spec, path, self.openapi_url)
            refs.append(
                DatasetRef(
                    source_native_uri=endpoint,
                    source_native_id=printed_operation_id(path),
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        spec = self._openapi()
        path, item = _path_for_ref(spec, ref)
        operation = item.get("get") if isinstance(item.get("get"), dict) else {}
        description = operation.get("description")
        summary = operation.get("summary")
        title = (
            description
            if isinstance(description, str) and description.strip()
            else summary
            if isinstance(summary, str) and summary.strip()
            else (ref.source_native_id or printed_operation_id(path))
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
            "license": printed_license_url(info),
            "distribution": [
                {
                    "accessURL": [ref.source_native_uri],
                    "downloadURL": [ref.source_native_uri],
                }
            ],
            "landingPage": [self.openapi_url],
            "sigmets_openapi_path": path,
            "sigmets_openapi_operation": item,
            "sigmets_openapi_info": info,
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
                f"MET Sigmets swagger list failed for {self.openapi_url}: {exc}"
            ) from exc
        if not isinstance(spec, dict):
            raise SourceError(
                f"MET Sigmets swagger is not a JSON object: {self.openapi_url}"
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


def printed_operation_id(path: str) -> str:
    segment = path.rstrip("/").split("/")[-1]
    if not segment:
        raise SourceError("MET Sigmets swagger path has no printed operation id")
    return segment


def printed_endpoint_url(spec: dict[str, Any], path: str, openapi_url: str) -> str:
    """Join a printed swagger 2.0 host/basePath/path, or the document origin.

    The live Sigmets spec prints `basePath` and no `host`. Those printed
    values are copied. No type, icao, or format filter is invented.
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
        raise SourceError("MET Sigmets swagger URL has no printed origin")
    return f"{parts.scheme}://{parts.netloc}{prefix}{suffix}"


def is_sigmets_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.lower() == HOST and parsed.path.startswith(PATH_PREFIX)


def sigmets_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "sigmets"


def cells_from_sigmets(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed Sigmets JSON into observation cells.

    `/features` is a GeoJSON FeatureCollection. Live features print `id`
    on the feature and an empty `properties` object. The printed feature
    `id` is copied as the value and into dimensions so each row stays
    distinct. Geometry and `assets` are not copied. `/values` prints an
    object whose members are string arrays. Each printed string is
    copied. Nested objects are not copied. Nothing is invented.
    """

    cells: list[tuple[str, Any, dict[str, str]]] = []
    if isinstance(payload, dict) and payload.get("type") == "FeatureCollection":
        features = payload.get("features")
        if not isinstance(features, list):
            raise ValueError("sigmets FeatureCollection has no features array")
        for feature in features:
            if not isinstance(feature, dict):
                continue
            props = feature.get("properties")
            record: dict[str, Any] = dict(props) if isinstance(props, dict) else {}
            feature_id = feature.get("id")
            if "id" not in record and feature_id is not None and _is_scalar(feature_id):
                record["id"] = feature_id
            for measure, value, dims in _cells_from_record(record):
                if measure == "id" and "id" not in dims and _is_scalar(value):
                    dims = {**dims, "id": _as_dim(value)}
                cells.append((measure, value, dims))
    elif isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, list):
                for item in value:
                    if _is_scalar(item) and item is not None:
                        cells.append((key, item, {key: _as_dim(item)}))
            elif _is_scalar(value) and value is not None:
                cells.append((key, value, {key: _as_dim(value)}))
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                cells.extend(_cells_from_record(item))
            elif _is_scalar(item) and item is not None:
                cells.append(("value", item, {"value": _as_dim(item)}))
    else:
        raise ValueError("sigmets payload is not a JSON object or array")
    if not cells:
        raise ValueError("sigmets payload printed no collection members")
    return cells


def _listed_get_paths(spec: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        raise SourceError("MET Sigmets swagger has no printed paths object")
    listed: list[tuple[str, dict[str, Any]]] = []
    for path, item in paths.items():
        if not isinstance(path, str) or not isinstance(item, dict):
            continue
        if "{" in path:
            continue
        if not path.rstrip("/").split("/")[-1]:
            continue
        operation = item.get("get")
        if not isinstance(operation, dict):
            continue
        if _has_required_parameter(item, operation):
            continue
        listed.append((path, item))
    return listed


def _has_required_parameter(item: dict[str, Any], operation: dict[str, Any]) -> bool:
    """True when the swagger prints a required parameter on the path or GET."""

    for block in (item.get("parameters"), operation.get("parameters")):
        if not isinstance(block, list):
            continue
        for parameter in block:
            if isinstance(parameter, dict) and parameter.get("required") is True:
                return True
    return False


def _path_for_ref(spec: dict[str, Any], ref: DatasetRef) -> tuple[str, dict[str, Any]]:
    for path, item in _listed_get_paths(spec):
        if printed_endpoint_url(spec, path, OPENAPI_URL) == ref.source_native_uri:
            return path, item
        if printed_operation_id(path) == ref.source_native_id:
            return path, item
    raise SourceError(
        f"MET Sigmets swagger has no printed path matching {ref.source_native_uri}"
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
