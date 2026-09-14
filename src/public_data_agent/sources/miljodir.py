from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "miljodir"
SOURCE_NAME = "Miljødirektoratet Vannmiljø"
OPENAPI_URL = "https://vannmiljoapi.miljodirektoratet.no/swagger/docs/v1"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a collection GET path in the official Vannmiljø swagger, "
    f"capped at {DEFAULT_MAX_ITEMS} paths"
)
MILJODIR_RPS = 2.0
MILJODIR_BURST = 4
HOST = "vannmiljoapi.miljodirektoratet.no"
PATH_PREFIX = "/api/"
UNIT_LIST_PATH = "/api/public/getunitlist"
UNIT_SCHEME = "miljodir:UnitID"
MEDIUM_LIST_PATH = "/api/public/getmediumlist"
MEDIUM_SCHEME = "miljodir:MediumID"
ACTIVITY_LIST_PATH = "/api/public/getactivitylist"
ACTIVITY_SCHEME = "miljodir:ActivityID"
NAME_FIELDS = ("Name", "name", "title", "MediumID", "id")


class MiljodirVannmiljoSource(SourceBase):
    """Replaceable ingest adapter for the Miljødirektoratet Vannmiljø swagger.

    Listing copies collection GET paths the official swagger document prints.
    It skips templated paths and does not invent endpoint ids. Native ids are
    the printed operationId values. This first slice stays inside that
    document and caps the walk.
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
            limiter=RateLimiter(MILJODIR_RPS, MILJODIR_BURST),
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
            "title": {"no": title},
            "description": (
                {"no": info_description} if isinstance(info_description, str) else None
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
            "miljodir_openapi_path": path,
            "miljodir_openapi_operation": item,
            "miljodir_openapi_info": info,
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
                f"Vannmiljø swagger list failed for {self.openapi_url}: {exc}"
            ) from exc
        if not isinstance(spec, dict):
            raise SourceError(f"Vannmiljø swagger is not a JSON object: {self.openapi_url}")
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
        raise SourceError("Vannmiljø swagger path has no printed operation id")
    return segment


def printed_endpoint_url(spec: dict[str, Any], path: str, openapi_url: str) -> str:
    """Join a printed swagger 2.0 host/basePath/path, or the document origin.

    The live Vannmiljø spec prints `host`, `basePath`, and `schemes`. Those
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
        raise SourceError("Vannmiljø swagger URL has no printed origin")
    return f"{parts.scheme}://{parts.netloc}{prefix}{suffix}"


def is_miljodir_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.lower() == HOST and parsed.path.startswith(PATH_PREFIX)


def is_miljodir_unit_list_url(access_path: str | None) -> bool:
    """Unit catalog. Medium and other leftover name lists are other paths."""

    if not is_miljodir_url(access_path):
        return False
    path = urlsplit(access_path).path.rstrip("/").casefold()
    return path == UNIT_LIST_PATH


def lookups_from_miljodir_units(payload: Any) -> list[dict[str, Any]]:
    """Copy printed Vannmiljø units into lookup entities.

    Each member is keyed by printed ``UnitID``. Label is printed ``Name``.
    Nested objects are not copied. Empty keys are skipped.
    """

    if not isinstance(payload, list):
        raise ValueError("miljodir unit-list payload is not a JSON array")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        code = item.get("UnitID")
        if not isinstance(code, (str, int)) or isinstance(code, bool):
            continue
        code = str(code).strip()
        if not code or code in seen:
            continue
        seen.add(code)
        label = item.get("Name")
        if not isinstance(label, str) or not label.strip():
            label = code
        attributes = {
            key: value
            for key, value in item.items()
            if key != "UnitID" and _is_scalar(value) and value is not None
        }
        out.append(
            {
                "subject_scheme": UNIT_SCHEME,
                "subject_code": code,
                "subject_label": label.strip(),
                "attributes": attributes,
            }
        )
    if not out:
        raise ValueError("miljodir unit-list payload printed no UnitID")
    return out


def is_miljodir_medium_list_url(access_path: str | None) -> bool:
    """Medium catalog. Unit and other leftover name lists are other paths."""

    if not is_miljodir_url(access_path):
        return False
    path = urlsplit(access_path).path.rstrip("/").casefold()
    return path == MEDIUM_LIST_PATH


def lookups_from_miljodir_mediums(payload: Any) -> list[dict[str, Any]]:
    """Copy printed Vannmiljø media into lookup entities.

    Each member is keyed by printed ``MediumID``. Label is printed ``Name``.
    Nested objects are not copied. Empty keys are skipped.
    """

    if not isinstance(payload, list):
        raise ValueError("miljodir medium-list payload is not a JSON array")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        code = item.get("MediumID")
        if not isinstance(code, (str, int)) or isinstance(code, bool):
            continue
        code = str(code).strip()
        if not code or code in seen:
            continue
        seen.add(code)
        label = item.get("Name")
        if not isinstance(label, str) or not label.strip():
            label = code
        attributes = {
            key: value
            for key, value in item.items()
            if key != "MediumID" and _is_scalar(value) and value is not None
        }
        out.append(
            {
                "subject_scheme": MEDIUM_SCHEME,
                "subject_code": code,
                "subject_label": label.strip(),
                "attributes": attributes,
            }
        )
    if not out:
        raise ValueError("miljodir medium-list payload printed no MediumID")
    return out


def is_miljodir_activity_list_url(access_path: str | None) -> bool:
    """Activity catalog. Unit, medium, and leftover name lists are other paths."""

    if not is_miljodir_url(access_path):
        return False
    path = urlsplit(access_path).path.rstrip("/").casefold()
    return path == ACTIVITY_LIST_PATH


def lookups_from_miljodir_activities(payload: Any) -> list[dict[str, Any]]:
    """Copy printed Vannmiljø activities into lookup entities.

    Each member is keyed by printed ``ActivityID``. Label is printed ``Name``.
    Nested objects are not copied. Empty keys are skipped.
    """

    if not isinstance(payload, list):
        raise ValueError("miljodir activity-list payload is not a JSON array")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        code = item.get("ActivityID")
        if not isinstance(code, (str, int)) or isinstance(code, bool):
            continue
        code = str(code).strip()
        if not code or code in seen:
            continue
        seen.add(code)
        label = item.get("Name")
        if not isinstance(label, str) or not label.strip():
            label = code
        attributes = {
            key: value
            for key, value in item.items()
            if key != "ActivityID" and _is_scalar(value) and value is not None
        }
        out.append(
            {
                "subject_scheme": ACTIVITY_SCHEME,
                "subject_code": code,
                "subject_label": label.strip(),
                "attributes": attributes,
            }
        )
    if not out:
        raise ValueError("miljodir activity-list payload printed no ActivityID")
    return out


def miljodir_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "miljodir"


def cells_from_miljodir(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed Vannmiljø JSON records into observation cells.

    Collection arrays keep a printed name field when present. Other scalars
    stay as dimensions. Nested objects are not copied.
    """

    if not isinstance(payload, list):
        raise ValueError("miljodir payload is not a JSON array")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        cells.extend(_cells_from_record(item))
    return cells


def _listed_get_paths(spec: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        raise SourceError("Vannmiljø swagger has no printed paths object")
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
        f"Vannmiljø swagger has no printed path matching {ref.source_native_uri}"
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
