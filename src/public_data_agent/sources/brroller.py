from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "brroller"
SOURCE_NAME = "Brønnøysundregistrene Enhetsregisteret roller"
OPENAPI_URL = "https://data.brreg.no/enhetsregisteret/api/dokumentasjon/no/openapi.json"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a leftover collection GET path under /enhetsregisteret/api/roller/ "
    f"in the official Enhetsregisteret OpenAPI, capped at {DEFAULT_MAX_ITEMS} paths"
)
BRROLLER_RPS = 2.0
BRROLLER_BURST = 4
HOST = "data.brreg.no"
PATH_PREFIX = "/enhetsregisteret/api/roller/"
NAME_FIELDS = ("beskrivelse", "kode")
SKIP_LAST_SEGMENTS = ("totalbestand",)


class BrrollerSource(SourceBase):
    """Replaceable ingest adapter for leftover Enhetsregisteret roller lists."""

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
            limiter=RateLimiter(BRROLLER_RPS, BRROLLER_BURST),
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
        summary = operation.get("summary")
        title = (
            summary
            if isinstance(summary, str) and summary.strip()
            else (ref.source_native_id or printed_operation_id(path))
        )
        info = spec.get("info") if isinstance(spec.get("info"), dict) else {}
        info_description = info.get("description")
        payload = {
            "id": ref.source_native_id,
            "uri": ref.source_native_uri,
            "title": {"no": title},
            "description": (
                {"no": info_description} if isinstance(info_description, str) else None
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
            "brroller_openapi_path": path,
            "brroller_openapi_operation": item,
            "brroller_openapi_info": info,
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
                f"Enhetsregisteret roller OpenAPI list failed for {self.openapi_url}: {exc}"
            ) from exc
        if not isinstance(spec, dict):
            raise SourceError(
                f"Enhetsregisteret roller OpenAPI is not a JSON object: {self.openapi_url}"
            )
        self._spec = spec
        return spec


def printed_license_url(info: dict[str, Any]) -> str | None:
    license_info = info.get("license")
    if not isinstance(license_info, dict):
        return None
    url = license_info.get("url")
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        return url.strip()
    return None


def printed_operation_id(path: str) -> str:
    segment = path.rstrip("/").split("/")[-1]
    if not segment:
        raise SourceError("Enhetsregisteret roller OpenAPI path has no printed operation id")
    return segment


def printed_endpoint_url(spec: dict[str, Any], path: str, openapi_url: str) -> str:
    """Join a printed path to a printed host/basePath/server or the OpenAPI origin."""

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
    servers = spec.get("servers") if isinstance(spec.get("servers"), list) else []
    if servers and isinstance(servers[0], dict) and isinstance(servers[0].get("url"), str):
        server = servers[0]["url"].strip()
        if server.startswith("http://") or server.startswith("https://"):
            base = server if server.endswith("/") else f"{server}/"
            return urljoin(base, path.lstrip("/"))
        parts = urlsplit(openapi_url)
        if not parts.scheme or not parts.netloc:
            raise SourceError("Enhetsregisteret roller OpenAPI URL has no printed origin")
        origin = f"{parts.scheme}://{parts.netloc}"
        rel = server if server.startswith("/") else f"/{server}"
        return origin + rel.rstrip("/") + suffix
    parts = urlsplit(openapi_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Enhetsregisteret roller OpenAPI URL has no printed origin")
    return f"{parts.scheme}://{parts.netloc}{prefix}{suffix}"


def is_brroller_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.lower() == HOST and parsed.path.startswith(PATH_PREFIX)


def brroller_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "brroller"


def cells_from_brroller(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed Enhetsregisteret roller HAL records into observation cells."""

    cells: list[tuple[str, Any, dict[str, str]]] = []
    if isinstance(payload, dict):
        embedded = payload.get("_embedded")
        lists: list[Any] = []
        if isinstance(embedded, dict):
            lists = [value for value in embedded.values() if isinstance(value, list)]
        if not lists:
            lists = [value for value in payload.values() if isinstance(value, list)]
        if lists:
            for block in lists:
                for item in block:
                    if isinstance(item, dict):
                        cells.extend(_cells_from_record(item))
                    elif _is_scalar(item) and item is not None:
                        cells.append(("value", item, {"value": _as_dim(item)}))
        else:
            cells.extend(_cells_from_record(payload))
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                cells.extend(_cells_from_record(item))
            elif _is_scalar(item) and item is not None:
                cells.append(("value", item, {"value": _as_dim(item)}))
    elif _is_scalar(payload) and payload is not None:
        cells.append(("value", payload, {"value": _as_dim(payload)}))
    else:
        raise ValueError("brroller payload is not a JSON object, array, or scalar")
    if not cells:
        raise ValueError("brroller payload printed no collection members")
    return cells


def _listed_get_paths(spec: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        raise SourceError("Enhetsregisteret roller OpenAPI has no printed paths object")
    listed: list[tuple[str, dict[str, Any]]] = []
    for path, item in paths.items():
        if not isinstance(path, str) or not isinstance(item, dict):
            continue
        if not path.startswith(PATH_PREFIX):
            continue
        if "{" in path:
            continue
        segment = path.rstrip("/").split("/")[-1]
        if not segment or segment in SKIP_LAST_SEGMENTS:
            continue
        operation = item.get("get")
        if not isinstance(operation, dict):
            continue
        if _has_required_parameter(item, operation):
            continue
        listed.append((path, item))
    return listed


def _has_required_parameter(item: dict[str, Any], operation: dict[str, Any]) -> bool:
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
        f"Enhetsregisteret roller OpenAPI has no printed path matching {ref.source_native_uri}"
    )


def _cells_from_record(item: dict[str, Any]) -> list[tuple[str, Any, dict[str, str]]]:
    scalars = {
        key: value
        for key, value in item.items()
        if key != "_links" and _is_scalar(value)
    }
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
