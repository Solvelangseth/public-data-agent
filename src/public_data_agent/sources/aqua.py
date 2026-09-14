from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "aqua"
SOURCE_NAME = "Fiskeridirektoratet Offentlig Akvakulturregister"
OPENAPI_URL = "https://api.fiskeridir.no/pub-aqua/api/api-docs"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a collection GET path in the official Offentlig "
    f"Akvakulturregister OpenAPI, capped at {DEFAULT_MAX_ITEMS} paths"
)
AQUA_RPS = 2.0
AQUA_BURST = 4
HOST = "api.fiskeridir.no"
PATH_PREFIX = "/pub-aqua/"
OVERVIEW_PATH = "/pub-aqua/api/v1/licenses-overview"
FISH_CODES_PATH = "/pub-aqua/api/v1/fish-codes"
FISH_CODE_SCHEME = "aqua:fish-code"
CAPACITY_MEASURES = ("current", "accumulated")
AQUA_MAX_CELLS = 100
ALLOWED_SELECT = frozenset({"license-nr"})
NAME_FIELDS = (
    "name",
    "defaultName",
    "nbNoName",
    "regulationName",
    "latinName",
    "code",
    "value",
    "id",
)


class AquaSource(SourceBase):
    """Replaceable ingest adapter for Fiskeridirektoratet Akvakulturregisteret.

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
            limiter=RateLimiter(AQUA_RPS, AQUA_BURST),
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
            raise SourceError(
                f"Akvakulturregisteret OpenAPI has no printed path for {ref.source_native_uri}"
            )
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
            "aqua_openapi_path": path,
            "aqua_openapi_operation": item,
            "aqua_openapi_info": info,
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
                f"Akvakulturregisteret OpenAPI list failed for {self.openapi_url}: {exc}"
            ) from exc
        if not isinstance(spec, dict):
            raise SourceError(
                f"Akvakulturregisteret OpenAPI is not a JSON object: {self.openapi_url}"
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
        raise SourceError("Akvakulturregisteret OpenAPI path has no printed operation id")
    return segment


def printed_endpoint_url(spec: dict[str, Any], path: str, openapi_url: str) -> str:
    """Join a printed path to a printed absolute server or the OpenAPI origin.

    The live Akvakulturregisteret spec prints `servers[0].url` as
    `https://api.fiskeridir.no/pub-aqua`. Relative servers fall back to
    the host that printed the spec. No table id is invented.
    """

    servers = spec.get("servers") if isinstance(spec.get("servers"), list) else []
    if servers and isinstance(servers[0], dict) and isinstance(servers[0].get("url"), str):
        server = servers[0]["url"].strip()
        if server.startswith("http://") or server.startswith("https://"):
            base = server if server.endswith("/") else f"{server}/"
            return urljoin(base, path.lstrip("/"))
    parts = urlsplit(openapi_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Akvakulturregisteret OpenAPI URL has no printed origin")
    origin = f"{parts.scheme}://{parts.netloc}"
    suffix = path if path.startswith("/") else f"/{path}"
    return origin + suffix


def is_aqua_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.lower() == HOST and parsed.path.startswith(PATH_PREFIX)


def aqua_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "aqua"


def is_aqua_overview_url(access_path: str | None) -> bool:
    """License overview with printed capacity. Area/site catalogs are different paths."""

    if not is_aqua_url(access_path):
        return False
    path = urlsplit(access_path).path.rstrip("/").casefold()
    return path == OVERVIEW_PATH


def is_aqua_fish_codes_url(access_path: str | None) -> bool:
    """Fish-code catalog. License/site dumps are different paths."""

    if not is_aqua_url(access_path):
        return False
    path = urlsplit(access_path).path.rstrip("/").casefold()
    return path == FISH_CODES_PATH


def lookups_from_aqua_fish_codes(payload: Any) -> list[dict[str, Any]]:
    """Copy printed aquaculture fish codes into lookup entities.

    Each member is keyed by printed ``code``. Label is printed ``nbNoName``
    when present. Nested objects are not copied. Empty keys are skipped.
    """

    if not isinstance(payload, list):
        raise ValueError("aqua fish-codes payload is not a JSON array")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        code = item.get("code")
        if not isinstance(code, (str, int)) or isinstance(code, bool):
            continue
        code = str(code).strip()
        if not code or code in seen:
            continue
        seen.add(code)
        label = item.get("nbNoName")
        if not isinstance(label, str) or not label.strip():
            label = item.get("latinName")
        if not isinstance(label, str) or not label.strip():
            label = code
        attributes = {
            key: value
            for key, value in item.items()
            if key != "code" and _is_scalar(value) and value is not None
        }
        out.append(
            {
                "subject_scheme": FISH_CODE_SCHEME,
                "subject_code": code,
                "subject_label": label.strip(),
                "attributes": attributes,
            }
        )
    if not out:
        raise ValueError("aqua fish-codes payload printed no code")
    return out


def selected_license_nr(select: dict[str, list[str]] | None) -> str:
    """Copy the printed OpenAPI `license-nr` query parameter from select."""

    select = {str(key): value for key, value in (select or {}).items()}
    unknown = sorted(key for key in select if key not in ALLOWED_SELECT)
    if unknown:
        raise ValueError(
            f"select names field(s) {unknown} that a licenses-overview fetch "
            f"does not filter on; accepted: {sorted(ALLOWED_SELECT)}"
        )
    wanted = select.get("license-nr")
    if not wanted:
        raise ValueError(
            "unfiltered licenses-overview defaults to range 0-9 of the register; "
            "select a printed license-nr"
        )
    values = [wanted] if isinstance(wanted, str) else [str(item) for item in wanted]
    if len(values) != 1 or not values[0].strip():
        raise ValueError("select license-nr to a single printed license number")
    return values[0].strip()


def aqua_overview_request_url(access_path: str, license_nr: str) -> str:
    parts = urlsplit(access_path)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["license-nr"] = license_nr
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


def cells_from_aqua_overview(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed license capacity into observation cells.

    Measures are the printed ``capacity`` keys ``current`` and
    ``accumulated``. Other scalars on the license and capacity object stay
    as dimensions. Nested objects besides ``capacity`` are not copied.
    """

    if not isinstance(payload, list):
        raise ValueError("aqua overview payload is not a JSON array")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        capacity = item.get("capacity")
        if not isinstance(capacity, dict):
            continue
        dims = {
            key: _as_dim(value)
            for key, value in item.items()
            if key != "capacity" and _is_scalar(value)
        }
        for key, value in capacity.items():
            if key in CAPACITY_MEASURES:
                continue
            if _is_scalar(value):
                dims[key] = _as_dim(value)
        for measure in CAPACITY_MEASURES:
            value = capacity.get(measure)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            cells.append((measure, value, dict(dims)))
    if not cells:
        raise ValueError("aqua overview payload printed no capacity cells")
    return cells


def cells_from_aqua(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed Akvakulturregisteret JSON records into observation cells.

    Collection arrays keep printed `name` when it is a non-empty string,
    otherwise `defaultName` / `nbNoName` / `regulationName` / `code`.
    Other scalars stay as dimensions. Nested objects are not copied.
    Nothing is invented.
    """

    if not isinstance(payload, list):
        raise ValueError("aqua payload is not a JSON array")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        cells.extend(_cells_from_record(item))
    if not cells:
        raise ValueError("aqua payload printed no collection members")
    return cells


def _listed_get_paths(spec: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        raise SourceError("Akvakulturregisteret OpenAPI has no printed paths object")
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
    raise SourceError(
        f"Akvakulturregisteret OpenAPI has no printed path matching {ref.source_native_uri}"
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
        if field != "name" and printed is not None and not isinstance(printed, bool):
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
