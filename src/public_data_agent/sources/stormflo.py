from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "stormflo"
SOURCE_NAME = "Kartverket Stormflo og havnivå"
OPENAPI_URL = "https://stormflo-konsekvens.kartverket.no/openapi.yaml"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a collection GET path in the official Kartverket Stormflo "
    f"OpenAPI, capped at {DEFAULT_MAX_ITEMS} paths"
)
STORMFLO_RPS = 2.0
STORMFLO_BURST = 4
HOST = "stormflo-konsekvens.kartverket.no"
PATH_PREFIX = "/public/api/v1/"
NATIONAL_PATH = "/public/api/v1/national.json"
STORMFLO_MAX_CELLS = 200
_SERVER_RE = re.compile(r"^servers:\n  - url:\s*(\S+)", re.M)
_TITLE_RE = re.compile(r"^  title:\s*(.+)$", re.M)
_LICENSE_URL_RE = re.compile(r"^  license:\n    name:.*\n    url:\s*(\S+)", re.M)
_PATH_RE = re.compile(
    r"^  (/[^\n]+):\n    get:\n(?P<body>(?:      .*\n)+)",
    re.M,
)
_SUMMARY_RE = re.compile(r"^      summary:\s*(.+)$", re.M)
_DESCRIPTION_RE = re.compile(r"^      description:\s*(.+)$", re.M)


class StormfloSource(SourceBase):
    """Replaceable ingest adapter for Kartverket Stormflo JSON.

    Listing copies collection GET paths the official OpenAPI document prints.
    It skips templated `{kommune}` paths and does not invent kommunenummer
    values. Native ids are the printed last path segment so `national.json`
    stays distinct from `alle_kommuner.json`. This first slice stays inside
    that document and caps the walk. This is not Kommuneinfo, not
    Transformering, and not leftover Kartverket WMS.
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
            limiter=RateLimiter(STORMFLO_RPS, STORMFLO_BURST),
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
            "stormflo_openapi_path": path,
            "stormflo_openapi_operation": item,
            "stormflo_openapi_info": info,
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
            text = self.http.get_text(self.openapi_url)
        except Exception as exc:
            raise SourceError(
                f"Kartverket Stormflo OpenAPI list failed for {self.openapi_url}: {exc}"
            ) from exc
        spec = openapi_from_yaml(text)
        self._spec = spec
        return spec


def openapi_from_yaml(text: str) -> dict[str, Any]:
    """Copy printed OpenAPI 3 fields this Kartverket YAML document prints."""

    if not isinstance(text, str) or "openapi:" not in text[:80]:
        raise SourceError("Kartverket Stormflo OpenAPI is not a printed YAML document")
    info: dict[str, Any] = {}
    title = _TITLE_RE.search(text)
    if title:
        info["title"] = title.group(1).strip()
    license_url = _LICENSE_URL_RE.search(text)
    if license_url:
        info["license"] = {"url": license_url.group(1).strip()}
    servers: list[dict[str, str]] = []
    server = _SERVER_RE.search(text)
    if server:
        servers.append({"url": server.group(1).strip()})
    paths: dict[str, Any] = {}
    for match in _PATH_RE.finditer(text):
        path = match.group(1)
        body = match.group("body")
        operation: dict[str, Any] = {}
        summary = _SUMMARY_RE.search(body)
        if summary:
            operation["summary"] = summary.group(1).strip()
        description = _DESCRIPTION_RE.search(body)
        if description:
            operation["description"] = description.group(1).strip()
        paths[path] = {"get": operation}
    if not paths:
        raise SourceError("Kartverket Stormflo OpenAPI has no printed paths object")
    return {"info": info, "servers": servers, "paths": paths}


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
        raise SourceError("Kartverket Stormflo OpenAPI path has no printed operation id")
    return segment


def printed_endpoint_url(spec: dict[str, Any], path: str, openapi_url: str) -> str:
    """Join a printed OpenAPI 3 server URL and path, or the document origin."""

    servers = spec.get("servers") if isinstance(spec.get("servers"), list) else []
    server = ""
    if servers and isinstance(servers[0], dict) and isinstance(servers[0].get("url"), str):
        server = servers[0]["url"].strip()
    suffix = path if path.startswith("/") else f"/{path}"
    if server:
        base = server if server.endswith("/") else f"{server}/"
        return urljoin(base, suffix.lstrip("/"))
    parts = urlsplit(openapi_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Kartverket Stormflo OpenAPI URL has no printed origin")
    return f"{parts.scheme}://{parts.netloc}{suffix}"


def is_stormflo_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.lower() == HOST and parsed.path.startswith(PATH_PREFIX)


def is_stormflo_national_url(access_path: str | None) -> bool:
    """National storm-surge totals. alle_kommuner.json is a different path."""

    if not is_stormflo_url(access_path):
        return False
    path = urlsplit(access_path).path.rstrip("/").casefold()
    return path == NATIONAL_PATH


def stormflo_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "stormflo"


def cells_from_stormflo(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed Stormflo JSON numbers into observation cells.

    National objects keep printed scenario keys and year keys as
    dimensions. Kommune arrays keep printed `kommunenummer`, `code`, and
    `year`. Each printed integer or float becomes its own measure.
    Nested objects beyond those records are not copied.
    """

    if isinstance(payload, dict):
        cells = _cells_from_national(payload)
    elif isinstance(payload, list):
        cells = _cells_from_kommuner(payload)
    else:
        raise ValueError("stormflo payload is not a JSON object or array")
    if not cells:
        raise ValueError("stormflo payload printed no numeric cells")
    return cells


def _listed_get_paths(spec: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        raise SourceError("Kartverket Stormflo OpenAPI has no printed paths object")
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
        listed.append((path, item))
    return listed


def _path_for_ref(spec: dict[str, Any], ref: DatasetRef) -> tuple[str, dict[str, Any]]:
    for path, item in _listed_get_paths(spec):
        if printed_endpoint_url(spec, path, OPENAPI_URL) == ref.source_native_uri:
            return path, item
        if printed_operation_id(path) == ref.source_native_id:
            return path, item
    raise SourceError(
        f"Kartverket Stormflo OpenAPI has no printed path matching {ref.source_native_uri}"
    )


def _cells_from_national(payload: dict[str, Any]) -> list[tuple[str, Any, dict[str, str]]]:
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for code, years in payload.items():
        if not isinstance(years, dict):
            continue
        for year, record in years.items():
            if not isinstance(record, dict):
                continue
            dims = {"code": _as_dim(code), "year": _as_dim(year)}
            cells.extend(_numeric_cells(record, dims))
    return cells


def _cells_from_kommuner(payload: list[Any]) -> list[tuple[str, Any, dict[str, str]]]:
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        kommune = item.get("kommunenummer")
        rows = item.get("data")
        if isinstance(rows, list):
            for record in rows:
                if not isinstance(record, dict):
                    continue
                dims: dict[str, str] = {}
                if _is_scalar(kommune):
                    dims["kommunenummer"] = _as_dim(kommune)
                code = record.get("code")
                year = record.get("year")
                if _is_scalar(code):
                    dims["code"] = _as_dim(code)
                if _is_scalar(year):
                    dims["year"] = _as_dim(year)
                cells.extend(_numeric_cells(record, dims, skip=("code", "year")))
            continue
        dims = {}
        if _is_scalar(kommune):
            dims["kommunenummer"] = _as_dim(kommune)
        cells.extend(_numeric_cells(item, dims, skip=("kommunenummer",)))
    return cells


def _numeric_cells(
    record: dict[str, Any],
    dims: dict[str, str],
    *,
    skip: tuple[str, ...] = (),
) -> list[tuple[str, Any, dict[str, str]]]:
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for key, value in record.items():
        if key in skip:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        cells.append((key, value, dict(dims)))
    return cells


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _as_dim(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
