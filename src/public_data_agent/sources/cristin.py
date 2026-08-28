from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "cristin"
SOURCE_NAME = "Cristin Current Research Information System"
DOCS_URL = "https://api.cristin.no/v2/"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a collection GET path in the official Cristin v2 documentation, "
    f"capped at {DEFAULT_MAX_ITEMS} paths"
)
CRISTIN_RPS = 2.0
CRISTIN_BURST = 4
HOST = "api.cristin.no"
PATH_PREFIX = "/v2/"
NAME_FIELDS = (
    "institution_name",
    "unit_name",
    "title",
    "name",
    "first_name",
    "surname",
    "code",
    "acronym",
    "id",
)
GET_TITLE_RE = re.compile(r'<span class="font-medium">(GET [^<]+)</span>')
OPTIONAL_QUERY = "?{parameters}"
LANG_ORDER = ("en", "nb", "nn", "no")


class CristinSource(SourceBase):
    """Replaceable ingest adapter for Cristin API v2.

    Listing copies untemplated collection GET paths the official v2
    documentation prints. It skips templated `{id}` / `{pid}` paths. Optional
    `?{parameters}` on a printed title is not treated as a required query.
    Native ids are the printed paths so `results/categories` and
    `projects/categories` stay distinct. This first slice stays inside that
    document and caps the walk.
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
            limiter=RateLimiter(CRISTIN_RPS, CRISTIN_BURST),
            timeout=60.0,
        )
        self._listed: list[tuple[str, str]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._listed_paths()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for path, _title in sliced:
            refs.append(
                DatasetRef(
                    source_native_uri=printed_endpoint_url(path, self.docs_url),
                    source_native_id=path,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        path, title = _path_for_ref(self._listed_paths(), ref, self.docs_url)
        endpoint = printed_endpoint_url(path, self.docs_url)
        payload = {
            "id": path,
            "uri": endpoint,
            "title": {"en": title},
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
            "cristin_docs_path": path,
            "cristin_docs_title": title,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=path,
            source_native_uri=endpoint,
            fetched_from=self.docs_url,
            payload=payload,
        )

    def _listed_paths(self) -> list[tuple[str, str]]:
        if self._listed is not None:
            return self._listed
        try:
            html = self.http.get_text(self.docs_url)
        except Exception as exc:
            raise SourceError(
                f"Cristin documentation list failed for {self.docs_url}: {exc}"
            ) from exc
        if not isinstance(html, str) or not html.strip():
            raise SourceError(f"Cristin documentation is empty: {self.docs_url}")
        listed = printed_get_paths(html)
        if not listed:
            raise SourceError(
                f"Cristin documentation printed no collection GET paths: {self.docs_url}"
            )
        self._listed = listed
        return listed


def printed_get_paths(html: str) -> list[tuple[str, str]]:
    """Copy untemplated collection GET paths the v2 documentation prints."""

    listed: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in GET_TITLE_RE.findall(html):
        title = raw.strip()
        path = printed_path_from_title(title)
        if path is None or path in seen:
            continue
        seen.add(path)
        listed.append((path, title))
    return listed


def printed_path_from_title(title: str) -> str | None:
    if not title.startswith("GET "):
        return None
    remainder = title[4:].strip()
    if remainder.endswith(OPTIONAL_QUERY):
        remainder = remainder[: -len(OPTIONAL_QUERY)]
    remainder = remainder.strip()
    if not remainder or remainder.startswith("/"):
        return None
    if "{" in remainder or "}" in remainder:
        return None
    return remainder


def printed_endpoint_url(path: str, docs_url: str) -> str:
    parts = urlsplit(docs_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Cristin documentation URL has no printed origin")
    suffix = path if path.startswith("/") else f"/{path}"
    prefix = parts.path.rstrip("/") or "/v2"
    return f"{parts.scheme}://{parts.netloc}{prefix}{suffix}"


def printed_operation_id(path: str) -> str:
    if not path.strip():
        raise SourceError("Cristin documentation path has no printed operation id")
    return path


def is_cristin_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    if parsed.netloc.lower() != HOST:
        return False
    return parsed.path.startswith(PATH_PREFIX)


def cristin_table_id(access_path: str) -> str:
    path = urlsplit(access_path).path
    if path.startswith(PATH_PREFIX):
        ident = path[len(PATH_PREFIX) :].strip("/")
        if ident:
            return ident
    segment = path.rstrip("/").split("/")[-1]
    return segment or "cristin"


def cells_from_cristin(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed Cristin JSON records into observation cells.

    Collection arrays keep a printed name field when present. Localized
    `name` / `title` objects copy the first printed language among en, nb,
    nn, no. Other scalars stay as dimensions. Nested objects and arrays
    are not copied. Nothing is invented.
    """

    cells: list[tuple[str, Any, dict[str, str]]] = []
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                cells.extend(_cells_from_record(item))
            elif _is_scalar(item) and item is not None:
                cells.append(("value", item, {}))
    elif isinstance(payload, dict):
        cells.extend(_cells_from_record(payload))
    elif _is_scalar(payload) and payload is not None:
        cells.append(("value", payload, {}))
    else:
        raise ValueError("cristin payload is not a JSON object, array, or scalar")
    if not cells:
        raise ValueError("cristin payload printed no collection members")
    return cells


def _path_for_ref(
    listed: list[tuple[str, str]],
    ref: DatasetRef,
    docs_url: str,
) -> tuple[str, str]:
    for path, title in listed:
        if printed_endpoint_url(path, docs_url) == ref.source_native_uri:
            return path, title
        if path == ref.source_native_id:
            return path, title
    raise SourceError(
        f"Cristin documentation has no printed path matching {ref.source_native_uri}"
    )


def _cells_from_record(item: dict[str, Any]) -> list[tuple[str, Any, dict[str, str]]]:
    values: dict[str, Any] = {}
    for key, value in item.items():
        copied = _copy_value(value)
        if copied is not None:
            values[key] = copied
    if not values:
        return []
    measure = None
    value: Any = None
    for field in NAME_FIELDS:
        printed = values.get(field)
        if printed is None:
            continue
        if isinstance(printed, str) and not printed.strip():
            continue
        measure = field
        value = printed
        break
    if measure is None:
        measure, value = next(iter(values.items()))
    dims = {key: _as_dim(other) for key, other in values.items() if key != measure}
    return [(measure, value, dims)]


def _copy_value(value: Any) -> Any:
    if _is_scalar(value):
        return value
    if isinstance(value, dict):
        return _localized_text(value)
    return None


def _localized_text(value: dict[str, Any]) -> str | None:
    for lang in LANG_ORDER:
        printed = value.get(lang)
        if isinstance(printed, str) and printed.strip():
            return printed
    return None


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _as_dim(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
