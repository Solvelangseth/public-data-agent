from __future__ import annotations

from typing import Any
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "nve"
SOURCE_NAME = "NVE Magasinstatistikk"
OPENAPI_URL = "https://biapi.nve.no/magasinstatistikk/swagger/v1/swagger.json"
PRINTED_PUBLISHER = "Norges vassdrags- og energidirektorat (NVE)"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a GET path in the printed NVE Magasinstatistikk OpenAPI, "
    f"capped at {DEFAULT_MAX_ITEMS} paths"
)
NVE_RPS = 2.0
NVE_BURST = 4
NVE_HOST = "biapi.nve.no"
NVE_PATH_MARK = "/magasinstatistikk/"
SISTE_UKE_PATH = "/magasinstatistikk/api/magasinstatistikk/hentoffentligdatasisteuke"
OMRADER_PATH = "/magasinstatistikk/api/magasinstatistikk/hentområder"
MINMAX_PATH = (
    "/magasinstatistikk/api/magasinstatistikk/hentoffentligdataminmaxmedian"
)
MAGASIN_MAX_CELLS = 100
OMRADE_SCHEME = "nve:magasin_omrade"
OMRADE_GROUPS = ("land", "elspot", "vassdrag")
ALLOWED_MINMAX_SELECT = frozenset({"iso_uke"})


class NveMagasinSource(SourceBase):
    """Replaceable ingest adapter for NVE Magasinstatistikk.

    Listing copies GET paths the official OpenAPI document prints. It does
    not invent endpoint ids. This first slice stays inside that document
    and caps the walk.
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
            limiter=RateLimiter(NVE_RPS, NVE_BURST),
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
            raise SourceError(f"NVE OpenAPI has no printed path for {ref.source_native_uri}")
        operation = item.get("get") if isinstance(item.get("get"), dict) else {}
        title = str(operation.get("summary") or ref.source_native_id or path)
        info = spec.get("info") if isinstance(spec.get("info"), dict) else {}
        description = info.get("description")
        publisher_name = printed_publisher(info)
        payload = {
            "id": ref.source_native_id,
            "uri": ref.source_native_uri,
            "title": {"no": title},
            "description": {"no": description} if isinstance(description, str) else None,
            "publisher": {"name": publisher_name} if publisher_name else None,
            "license": None,
            "distribution": [
                {
                    "accessURL": [ref.source_native_uri],
                    "downloadURL": [ref.source_native_uri],
                }
            ],
            "landingPage": [self.openapi_url],
            "nve_openapi_path": path,
            "nve_openapi_operation": item,
            "nve_openapi_info": info,
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
            raise SourceError(f"NVE OpenAPI list failed for {self.openapi_url}: {exc}") from exc
        if not isinstance(spec, dict):
            raise SourceError(f"NVE OpenAPI is not a JSON object: {self.openapi_url}")
        self._spec = spec
        return spec


def printed_publisher(info: dict[str, Any]) -> str | None:
    text = info.get("description")
    if isinstance(text, str) and PRINTED_PUBLISHER in text:
        return PRINTED_PUBLISHER
    return None


def printed_operation_id(path: str) -> str:
    segment = path.rstrip("/").split("/")[-1]
    if not segment:
        raise SourceError("NVE OpenAPI path has no printed operation id")
    return segment


def printed_endpoint_url(spec: dict[str, Any], path: str, openapi_url: str) -> str:
    servers = spec.get("servers") if isinstance(spec.get("servers"), list) else []
    server = ""
    if servers and isinstance(servers[0], dict) and isinstance(servers[0].get("url"), str):
        server = servers[0]["url"]
    base = urljoin(openapi_url, server if server.endswith("/") else f"{server}/")
    return urljoin(base, path.lstrip("/"))


def is_nve_magasin_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc == NVE_HOST and NVE_PATH_MARK in parsed.path


def is_nve_siste_uke_url(access_path: str | None) -> bool:
    """Last-week reservoir cells. The full weekly dump is a different path."""

    if not is_nve_magasin_url(access_path):
        return False
    path = urlsplit(access_path).path.rstrip("/").casefold()
    return path == SISTE_UKE_PATH


def is_nve_omrader_url(access_path: str | None) -> bool:
    """Area catalog. Last-week cells and the weekly dump are different paths."""

    if not is_nve_magasin_url(access_path):
        return False
    path = urlsplit(access_path).path.rstrip("/").casefold()
    return path == OMRADER_PATH


def is_nve_minmax_url(access_path: str | None) -> bool:
    """Twenty-year extrema. Last-week cells and the weekly dump differ."""

    if not is_nve_magasin_url(access_path):
        return False
    path = urlsplit(access_path).path.rstrip("/").casefold()
    return path == MINMAX_PATH


def selected_nve_iso_uke(select: dict[str, list[str]] | None) -> str:
    """Copy the printed ``iso_uke`` for a MinMaxMedian slice."""

    select = {str(key): value for key, value in (select or {}).items()}
    unknown = sorted(key for key in select if key not in ALLOWED_MINMAX_SELECT)
    if unknown:
        raise ValueError(
            f"select names field(s) {unknown} that a MinMaxMedian fetch "
            f"does not filter on; accepted: {sorted(ALLOWED_MINMAX_SELECT)}"
        )
    wanted = select.get("iso_uke")
    if not wanted:
        raise ValueError(
            "unfiltered HentOffentligDataMinMaxMedian is 477 twenty-year "
            "extrema rows; select a printed iso_uke"
        )
    values = [wanted] if isinstance(wanted, str) else [str(item) for item in wanted]
    if len(values) != 1 or not values[0].strip():
        raise ValueError("select iso_uke to a single printed ISO week")
    return values[0].strip()


def rows_matching_iso_uke(payload: Any, iso_uke: str) -> list[dict[str, Any]]:
    """Keep MinMaxMedian rows whose printed iso_uke matches."""

    if not isinstance(payload, list):
        raise ValueError("nve MinMaxMedian payload is not a JSON array")
    matched: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        printed = item.get("iso_uke")
        if printed is None:
            continue
        if str(printed) == iso_uke:
            matched.append(item)
    if not matched:
        raise ValueError(
            f"HentOffentligDataMinMaxMedian has no row matching "
            f"iso_uke={iso_uke!r}; iso_uke must be a printed ISO week"
        )
    return matched


def lookups_from_nve_omrader(payload: Any) -> list[dict[str, Any]]:
    """Copy printed magasin areas into lookup entities.

    Each nested land/elspot/vassdrag member is keyed by printed
    ``omrType`` and ``omrnr`` joined with ``:``. Empty keys are skipped.
    Nested objects besides those arrays are not copied.
    """

    if isinstance(payload, list):
        if len(payload) == 1 and isinstance(payload[0], dict):
            payload = payload[0]
        else:
            raise ValueError("nve områder payload is not a JSON object")
    if not isinstance(payload, dict):
        raise ValueError("nve områder payload is not a JSON object")
    out: list[dict[str, Any]] = []
    for group in OMRADE_GROUPS:
        rows = payload.get(group)
        if not isinstance(rows, list):
            continue
        for item in rows:
            if not isinstance(item, dict):
                continue
            omr_type = item.get("omrType")
            omrnr = item.get("omrnr")
            if not isinstance(omr_type, str) or not omr_type.strip():
                continue
            if omrnr is None or isinstance(omrnr, bool):
                continue
            if not isinstance(omrnr, (str, int, float)):
                continue
            code = f"{omr_type.strip()}:{omrnr}"
            label = item.get("navn")
            if not isinstance(label, str) or not label.strip():
                label = item.get("navn_langt")
            if not isinstance(label, str) or not label.strip():
                label = code
            attributes = {
                key: value
                for key, value in item.items()
                if key not in {"omrType", "omrnr"} and _is_scalar(value) and value is not None
            }
            attributes["group"] = group
            out.append(
                {
                    "subject_scheme": OMRADE_SCHEME,
                    "subject_code": code,
                    "subject_label": label.strip(),
                    "attributes": attributes,
                }
            )
    if not out:
        raise ValueError("nve områder payload printed no area members")
    return out


def requestable_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(
        (parts.scheme, parts.netloc, quote(parts.path, safe="/"), parts.query, parts.fragment)
    )


def nve_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "nve"


def cells_from_nve(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed NVE JSON records into observation cells.

    Numeric fields keep their printed keys as measures. Name-only records
    copy the printed navn/name. Nothing is invented.
    """

    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in _records(payload):
        floats = [
            (key, value) for key, value in item.items() if isinstance(value, float)
        ]
        ints = [
            (key, value)
            for key, value in item.items()
            if isinstance(value, int) and not isinstance(value, bool)
        ]
        name_key = "navn" if "navn" in item else "name" if "name" in item else None
        measures = floats or (ints if name_key is None else [])
        if measures:
            for key, value in measures:
                dims = {
                    other: _as_dim(other_value)
                    for other, other_value in item.items()
                    if other != key and _is_scalar(other_value)
                }
                cells.append((key, value, dims))
            continue
        if name_key is None:
            continue
        dims = {
            key: _as_dim(value)
            for key, value in item.items()
            if key != name_key and _is_scalar(value)
        }
        cells.append((name_key, item[name_key], dims))
    return cells


def _listed_get_paths(spec: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        raise SourceError("NVE OpenAPI has no printed paths object")
    listed: list[tuple[str, dict[str, Any]]] = []
    for path, item in paths.items():
        if not isinstance(path, str) or not isinstance(item, dict):
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
    raise SourceError(f"NVE OpenAPI has no printed path matching {ref.source_native_uri}")


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
    out = []
    if scalars and (
        any(_is_number(value) for value in scalars.values()) or "navn" in scalars or "name" in scalars
    ):
        out.append(scalars)
    for value in nested:
        out.extend(_records(value))
    return out


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _as_dim(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
