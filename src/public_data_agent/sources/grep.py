from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "grep"
SOURCE_NAME = "Utdanningsdirektoratet Grep"
OPENAPI_URL = "https://data.udir.no/swagger/docs/201906"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a collection GET path in the official Grep swagger, "
    f"capped at {DEFAULT_MAX_ITEMS} paths"
)
GREP_RPS = 2.0
GREP_BURST = 4
HOST = "data.udir.no"
PATH_PREFIX = "/kl06/"
NAME_FIELDS = ("kode", "id", "uri")
SKIP_TEMPLATES = ("{kode}", "{type}", "{filter}", "{format}")


class GrepSource(SourceBase):
    """Replaceable ingest adapter for Udir Grep.

    Listing copies collection GET paths the official Grep swagger prints.
    It skips templated `{kode}` / `{type}` / `{filter}` / `{format}` paths.
    The swagger path uses `{version}`; that token is replaced with the
    printed last segment of the swagger document URL (`201906`). Native
    ids are the printed last path segment so `aarstrinn` stays distinct
    from `dokumenttype`. This first slice stays inside that document and
    caps the walk. The swagger prints no security scheme. Live GET of
    those printed collection paths is HTTP 200 with no token. No token is
    sent. This is not Nasjonalt skoleregister (`--source udir`), not
    Nasjonalt barnehageregister (`--source nbr`), and not NXR
    Fellestjeneste (`--source nxr`).
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
            limiter=RateLimiter(GREP_RPS, GREP_BURST),
            timeout=60.0,
        )
        self._spec: dict[str, Any] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = _listed_get_paths(self._openapi(), self.openapi_url)
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for path, _item in sliced:
            endpoint = printed_endpoint_url(self._openapi(), path, self.openapi_url)
            refs.append(
                DatasetRef(
                    source_native_uri=endpoint,
                    source_native_id=printed_operation_id(path, self.openapi_url),
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        spec = self._openapi()
        path = _path_for_ref(spec, ref, self.openapi_url)
        item = (spec.get("paths") or {}).get(path)
        if not isinstance(item, dict):
            raise SourceError(f"Grep swagger has no printed path for {ref.source_native_uri}")
        operation = item.get("get") if isinstance(item.get("get"), dict) else {}
        summary = operation.get("summary")
        title = (
            summary
            if isinstance(summary, str) and summary.strip()
            else (ref.source_native_id or printed_operation_id(path, self.openapi_url))
        )
        info = spec.get("info") if isinstance(spec.get("info"), dict) else {}
        info_description = info.get("description")
        endpoint = printed_endpoint_url(spec, path, self.openapi_url)
        license_url = printed_license_url(info)
        payload = {
            "id": ref.source_native_id or printed_operation_id(path, self.openapi_url),
            "uri": endpoint,
            "title": {"no": title},
            "description": info_description if isinstance(info_description, str) else None,
            "publisher": None,
            "license": license_url,
            "distribution": [
                {
                    "accessURL": [endpoint],
                    "downloadURL": [endpoint],
                }
            ],
            "landingPage": [self.openapi_url],
            "grep_swagger_path": path,
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
            raise SourceError(f"Grep swagger failed for {self.openapi_url}: {exc}") from exc
        if not isinstance(spec, dict):
            raise SourceError(f"Grep swagger is not a JSON object: {self.openapi_url}")
        self._spec = spec
        return spec


def _listed_get_paths(spec: dict[str, Any], openapi_url: str) -> list[tuple[str, dict[str, Any]]]:
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        raise SourceError("Grep swagger has no printed paths object")
    listed: list[tuple[str, dict[str, Any]]] = []
    for path, item in paths.items():
        if not isinstance(path, str) or not isinstance(item, dict):
            continue
        if not _is_collection_path(path):
            continue
        operation = item.get("get")
        if not isinstance(operation, dict):
            continue
        if _has_required_query(operation):
            continue
        listed.append((path, item))
    return listed


def _is_collection_path(path: str) -> bool:
    if any(token in path for token in SKIP_TEMPLATES):
        return False
    leftover = path.replace("{version}", "")
    return "{" not in leftover and "}" not in leftover


def _has_required_query(operation: dict[str, Any]) -> bool:
    params = operation.get("parameters")
    if not isinstance(params, list):
        return False
    for param in params:
        if not isinstance(param, dict):
            continue
        if param.get("in") == "query" and param.get("required") is True:
            return True
    return False


def printed_version(openapi_url: str) -> str:
    """Copy the printed swagger document version from the docs URL path."""

    ident = urlsplit(openapi_url).path.rstrip("/").split("/")[-1]
    if not ident:
        raise SourceError("Grep swagger URL has no printed version segment")
    return ident


def printed_concrete_path(path: str, openapi_url: str) -> str:
    return path.replace("{version}", printed_version(openapi_url))


def printed_endpoint_url(spec: dict[str, Any], path: str, openapi_url: str) -> str:
    """Join a printed path to a printed host/basePath/server or the swagger origin."""

    concrete = printed_concrete_path(path, openapi_url)
    host = spec.get("host")
    base_path = spec.get("basePath")
    schemes = spec.get("schemes") if isinstance(spec.get("schemes"), list) else []
    suffix = concrete if concrete.startswith("/") else f"/{concrete}"
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
            return urljoin(base, concrete.lstrip("/"))
        parts = urlsplit(openapi_url)
        if not parts.scheme or not parts.netloc:
            raise SourceError("Grep swagger URL has no printed origin")
        origin = f"{parts.scheme}://{parts.netloc}"
        rel = server if server.startswith("/") else f"/{server}"
        return origin + rel.rstrip("/") + suffix
    parts = urlsplit(openapi_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Grep swagger URL has no printed origin")
    return f"{parts.scheme}://{parts.netloc}{prefix}{suffix}"


def printed_operation_id(path: str, openapi_url: str) -> str:
    concrete = printed_concrete_path(path, openapi_url)
    ident = concrete.rstrip("/").split("/")[-1]
    if not ident:
        raise SourceError("Grep swagger path has no printed operation id")
    return ident


def printed_license_url(info: dict[str, Any]) -> str | None:
    license_obj = info.get("license")
    if not isinstance(license_obj, dict):
        return None
    url = license_obj.get("url")
    if isinstance(url, str) and url.strip():
        return url.strip()
    return None


def is_grep_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.lower() == HOST and parsed.path.startswith(PATH_PREFIX)


def grep_table_id(access_path: str) -> str:
    path = urlsplit(access_path).path.rstrip("/")
    ident = path.split("/")[-1] if path else ""
    return ident or "grep"


def cells_from_grep(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed Grep JSON records into observation cells.

    A printed array keeps each member. Each record keeps printed `kode`
    when present, otherwise `id` or `uri`. Other scalars stay as
    dimensions. Nested objects and arrays are not copied. Nothing is
    invented.
    """

    cells: list[tuple[str, Any, dict[str, str]]] = []
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                cells.extend(_cells_from_record(item))
            elif _is_scalar(item) and item is not None:
                cells.append(("value", item, {"value": _as_dim(item)}))
    elif isinstance(payload, dict):
        cells.extend(_cells_from_record(payload))
    elif _is_scalar(payload) and payload is not None:
        cells.append(("value", payload, {"value": _as_dim(payload)}))
    else:
        raise ValueError("grep payload is not a JSON object, array, or scalar")
    if not cells:
        raise ValueError("grep payload printed no collection members")
    return cells


def _path_for_ref(spec: dict[str, Any], ref: DatasetRef, openapi_url: str) -> str:
    for path, _item in _listed_get_paths(spec, openapi_url):
        if printed_endpoint_url(spec, path, openapi_url) == ref.source_native_uri:
            return path
        if printed_operation_id(path, openapi_url) == ref.source_native_id:
            return path
    raise SourceError(f"Grep swagger has no printed path matching {ref.source_native_uri}")


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
