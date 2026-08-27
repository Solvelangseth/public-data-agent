from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "mattilsynet"
SOURCE_NAME = "Mattilsynet Plantevernmidler"
OPENAPI_URL = "https://api.plantevernmidler.mattilsynet.io/json"
PRINTED_PUBLISHER = "Mattilsynet"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a GET path in the official Mattilsynet Plantevernmidler OpenAPI, "
    f"capped at {DEFAULT_MAX_ITEMS} paths"
)
MATTILSYNET_RPS = 2.0
MATTILSYNET_BURST = 4
HOST = "api.plantevernmidler.mattilsynet.io"


class MattilsynetPlantevernSource(SourceBase):
    """Replaceable ingest adapter for Mattilsynet Plantevernmidler.

    Listing copies collection GET paths the official OpenAPI document prints.
    It skips templated paths and does not invent endpoint ids. This first
    slice stays inside that document and caps the walk.
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
            limiter=RateLimiter(MATTILSYNET_RPS, MATTILSYNET_BURST),
            timeout=60.0,
        )
        self._spec: dict[str, Any] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = _listed_get_paths(self._openapi())
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for path, _item in sliced:
            endpoint = printed_endpoint_url(self._openapi(), path, self.openapi_url)
            refs.append(
                DatasetRef(
                    source_native_uri=endpoint,
                    source_native_id=printed_operation_id(path),
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        spec = self._openapi()
        path = _path_for_ref(spec, ref)
        item = (spec.get("paths") or {}).get(path)
        if not isinstance(item, dict):
            raise SourceError(f"Mattilsynet OpenAPI has no printed path for {ref.source_native_uri}")
        operation = item.get("get") if isinstance(item.get("get"), dict) else {}
        description = operation.get("description")
        title = (
            description
            if isinstance(description, str) and description.strip()
            else (ref.source_native_id or printed_operation_id(path))
        )
        info = spec.get("info") if isinstance(spec.get("info"), dict) else {}
        info_description = info.get("description")
        publisher_name = printed_publisher(info)
        payload = {
            "id": ref.source_native_id,
            "uri": ref.source_native_uri,
            "title": {"no": title},
            "description": (
                {"no": info_description} if isinstance(info_description, str) else None
            ),
            "publisher": {"name": publisher_name} if publisher_name else None,
            "license": printed_license_url(info),
            "distribution": [
                {
                    "accessURL": [ref.source_native_uri],
                    "downloadURL": [ref.source_native_uri],
                }
            ],
            "landingPage": [self.openapi_url],
            "mattilsynet_openapi_path": path,
            "mattilsynet_openapi_operation": item,
            "mattilsynet_openapi_info": info,
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
            raise SourceError(f"Mattilsynet OpenAPI list failed for {self.openapi_url}: {exc}") from exc
        if not isinstance(spec, dict):
            raise SourceError(f"Mattilsynet OpenAPI is not a JSON object: {self.openapi_url}")
        self._spec = spec
        return spec


def printed_publisher(info: dict[str, Any]) -> str | None:
    text = info.get("description")
    if isinstance(text, str) and PRINTED_PUBLISHER in text:
        return PRINTED_PUBLISHER
    return None


def printed_license_url(info: dict[str, Any]) -> str | None:
    license_info = info.get("license")
    if not isinstance(license_info, dict):
        return None
    url = license_info.get("url")
    if isinstance(url, str) and url.strip():
        return url
    return None


def printed_operation_id(path: str) -> str:
    segment = path.rstrip("/").split("/")[-1]
    if not segment:
        raise SourceError("Mattilsynet OpenAPI path has no printed operation id")
    return segment


def printed_endpoint_url(spec: dict[str, Any], path: str, openapi_url: str) -> str:
    servers = spec.get("servers") if isinstance(spec.get("servers"), list) else []
    server = ""
    if servers and isinstance(servers[0], dict) and isinstance(servers[0].get("url"), str):
        server = servers[0]["url"]
    base = urljoin(openapi_url, server if server.endswith("/") else f"{server}/")
    return urljoin(base, path.lstrip("/"))


def is_mattilsynet_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    return urlsplit(access_path).netloc == HOST


def mattilsynet_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "mattilsynet"


def cells_from_mattilsynet(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed Mattilsynet JSON records into observation cells.

    `preparater` lists keep printed `navn` as the measure. Other payloads
    reuse a small name-only record walk. Nothing is invented.
    """

    if isinstance(payload, dict) and isinstance(payload.get("preparater"), list):
        records = [item for item in payload["preparater"] if isinstance(item, dict)]
    elif isinstance(payload, (dict, list)):
        records = _records(payload)
    else:
        raise ValueError("mattilsynet payload is not a JSON object or array")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in records:
        cells.extend(_cells_from_record(item))
    return cells


def _listed_get_paths(spec: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        raise SourceError("Mattilsynet OpenAPI has no printed paths object")
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


def _path_for_ref(spec: dict[str, Any], ref: DatasetRef) -> str:
    for path, _item in _listed_get_paths(spec):
        if printed_endpoint_url(spec, path, OPENAPI_URL) == ref.source_native_uri:
            return path
        if printed_operation_id(path) == ref.source_native_id:
            return path
    raise SourceError(f"Mattilsynet OpenAPI has no printed path matching {ref.source_native_uri}")


def _records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        out: list[dict[str, Any]] = []
        for item in payload:
            out.extend(_records(item))
        return out
    if not isinstance(payload, dict):
        return []
    scalars = {key: value for key, value in payload.items() if _is_scalar(value)}
    nested = [value for value in payload.values() if isinstance(value, (list, dict))]
    out: list[dict[str, Any]] = []
    if scalars:
        out.append(scalars)
    for value in nested:
        out.extend(_records(value))
    return out


def _cells_from_record(item: dict[str, Any]) -> list[tuple[str, Any, dict[str, str]]]:
    scalars = {key: value for key, value in item.items() if _is_scalar(value)}
    if not scalars:
        return []
    if "navn" in scalars:
        measure = "navn"
        value = scalars["navn"]
    else:
        measure, value = next(iter(scalars.items()))
    dims = {
        key: _as_dim(other)
        for key, other in scalars.items()
        if key != measure
    }
    return [(measure, value, dims)]


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _as_dim(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
