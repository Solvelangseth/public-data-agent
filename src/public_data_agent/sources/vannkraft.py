from __future__ import annotations

import html as html_lib
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "vannkraft"
SOURCE_NAME = "NVE Vannkraftdatabase"
DOCS_URL = "https://api.nve.no/doc/vannkraftdatabase/"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as an untemplated collection GET path in the official NVE "
    f"Vannkraftdatabase documentation, capped at {DEFAULT_MAX_ITEMS} paths"
)
VANNKRAFT_RPS = 2.0
VANNKRAFT_BURST = 4
HOST = "api.nve.no"
PATH_PREFIX = "/web/Powerplant/"
NAME_FIELDS = ("Navn", "VannKraftverkID", "VannKVType")
GET_RE = re.compile(
    r'opblock-summary-method">GET</span>\s*'
    r'<span class="opblock-summary-path"><span>(/[^<{]+)</span></span>'
    r'\s*</div>\s*<div>\s*'
    r'<div class="opblock-summary-description">([^<]*)</div>',
    re.IGNORECASE,
)
BASE_RE = re.compile(
    r'Base url:</b>\s*<span class="currentScheme">https://</span>([^\]<\s]+)',
    re.IGNORECASE,
)


class VannkraftSource(SourceBase):
    """Replaceable ingest adapter for NVE Vannkraftdatabase.

    Listing copies untemplated collection GET paths the official
    documentation prints. It skips templated paths and does not invent
    endpoint ids. Native ids are the printed last path segment so
    `GetHydroPowerPlantsInOperation` stays distinct from
    `GetHydroPowerPlants`. Access URLs join each printed path onto the
    printed `https://` base. This first slice stays inside that document
    and caps the walk. This is not Magasinstatistikk (`--source nve`).
    """

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = (DOCS_URL,)
    ingest_reason = INGEST_REASON

    def __init__(
        self,
        *,
        docs_url: str = DOCS_URL,
        max_items: int = DEFAULT_MAX_ITEMS,
        http: HttpClient | None = None,
    ) -> None:
        self.docs_url = docs_url
        self.max_items = max_items
        self.http = http or HttpClient(
            limiter=RateLimiter(VANNKRAFT_RPS, VANNKRAFT_BURST),
            timeout=60.0,
        )
        self._listed: list[tuple[str, str, str]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._listed_paths()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for path, _title, base in sliced:
            refs.append(
                DatasetRef(
                    source_native_uri=printed_endpoint_url(path, base),
                    source_native_id=printed_operation_id(path),
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        path, title, base = _path_for_ref(self._listed_paths(), ref)
        endpoint = printed_endpoint_url(path, base)
        payload = {
            "id": printed_operation_id(path),
            "uri": endpoint,
            "title": {"no": title},
            "description": None,
            "publisher": None,
            "license": None,
            "distribution": [
                {
                    "accessURL": [endpoint],
                    "downloadURL": [endpoint],
                }
            ],
            "landingPage": [self.docs_url],
            "vannkraft_docs_path": path,
            "vannkraft_docs_base": base,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ref.source_native_id,
            source_native_uri=endpoint,
            fetched_from=self.docs_url,
            payload=payload,
        )

    def _listed_paths(self) -> list[tuple[str, str, str]]:
        if self._listed is not None:
            return self._listed
        try:
            page = self.http.get_text(self.docs_url)
        except Exception as exc:
            raise SourceError(
                f"NVE Vannkraftdatabase documentation list failed for {self.docs_url}: {exc}"
            ) from exc
        if not isinstance(page, str) or not page.strip():
            raise SourceError(f"NVE Vannkraftdatabase documentation is empty: {self.docs_url}")
        listed = printed_get_paths(page)
        if not listed:
            raise SourceError(
                f"NVE Vannkraftdatabase documentation printed no collection GET paths: {self.docs_url}"
            )
        self._listed = listed
        return listed


def printed_get_paths(page: str) -> list[tuple[str, str, str]]:
    """Copy untemplated collection GET paths the documentation prints."""

    base = printed_base_url(page)
    listed: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for raw_path, raw_title in GET_RE.findall(page):
        path = html_lib.unescape(raw_path).strip()
        if not path.startswith("/") or "{" in path or "}" in path:
            continue
        if "/" in path.strip("/"):
            continue
        if path in seen:
            continue
        seen.add(path)
        title = html_lib.unescape(raw_title).strip() or printed_operation_id(path)
        listed.append((path, title, base))
    return listed


def printed_base_url(page: str) -> str:
    match = BASE_RE.search(page)
    if match is None:
        raise SourceError("NVE Vannkraftdatabase documentation printed no https base url")
    host_path = html_lib.unescape(match.group(1)).strip().rstrip("/")
    if not host_path:
        raise SourceError("NVE Vannkraftdatabase documentation printed an empty https base url")
    return f"https://{host_path}"


def printed_endpoint_url(path: str, base: str) -> str:
    parts = urlsplit(base)
    if not parts.scheme or not parts.netloc:
        raise SourceError("NVE Vannkraftdatabase documentation URL has no printed origin")
    suffix = path if path.startswith("/") else f"/{path}"
    root = parts.path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, root + suffix, "", ""))


def printed_operation_id(path: str) -> str:
    ident = path.rstrip("/").split("/")[-1]
    if not ident:
        raise SourceError("NVE Vannkraftdatabase documentation path has no printed operation id")
    return ident


def is_vannkraft_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.lower() == HOST and parsed.path.startswith(PATH_PREFIX)


def vannkraft_table_id(access_path: str) -> str:
    path = urlsplit(access_path).path
    if path.startswith(PATH_PREFIX):
        ident = path[len(PATH_PREFIX) :].strip("/")
        if ident:
            return ident
    ident = path.rstrip("/").split("/")[-1]
    return ident or "vannkraft"


def cells_from_vannkraft(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed Vannkraftdatabase JSON records into observation cells.

    Collection arrays keep printed `Navn` when present. Other scalars stay
    as dimensions. Nested objects and arrays are not copied. Nothing is
    invented.
    """

    if not isinstance(payload, list):
        raise ValueError("vannkraft payload is not a JSON array")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in payload:
        if isinstance(item, dict):
            cells.extend(_cells_from_record(item))
        elif _is_scalar(item) and item is not None:
            cells.append(("value", item, {"value": _as_dim(item)}))
    if not cells:
        raise ValueError("vannkraft payload printed no collection members")
    return cells


def _path_for_ref(listed: list[tuple[str, str, str]], ref: DatasetRef) -> tuple[str, str, str]:
    for path, title, base in listed:
        if printed_endpoint_url(path, base) == ref.source_native_uri:
            return path, title, base
        if printed_operation_id(path) == ref.source_native_id:
            return path, title, base
    raise SourceError(
        f"NVE Vannkraftdatabase documentation has no printed path matching {ref.source_native_uri}"
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
