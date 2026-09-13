from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase
from public_data_agent.sources.strepresent import (
    SUBJECT_SCHEME,
    entity_from_representant,
    shape_from_representanter,
)

SOURCE_ID = "stperioder"
SOURCE_NAME = "Stortinget leftover stortingsperioder representanter"
LIST_URL = "https://data.stortinget.no/eksport/stortingsperioder?format=json"
REPRESENTANTER_PATH = "/eksport/representanter"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed stortingsperiode on the official Stortinget "
    f"stortingsperioder catalog, capped at {DEFAULT_MAX_ITEMS} periods"
)
STPERIODER_RPS = 2.0
STPERIODER_BURST = 4
HOST = "data.stortinget.no"
FORMAT_QUERY = "json"
PERIODE_QUERY = "stortingsperiodeid"
NAME_FIELDS = ("fornavn", "etternavn", "id", "navn")
LIST_KEY = "representanter_liste"
DEFAULT_LIMIT = 10
MAX_LIMIT = 100


class StperioderSource(SourceBase):
    """Replaceable ingest adapter for leftover Stortinget period representanter.

    Listing copies printed `stortingsperioder_liste[].id` values from the
    official `/eksport/stortingsperioder?format=json` catalog. It does not
    invent ids. `access_path` joins each printed id onto the leftover
    `/eksport/representanter` collection the official technical
    documentation prints, keeping the documented `stortingsperiodeid` and
    `format=json` query. Live GET of those joined paths is HTTP 200. This
    first slice stays inside that catalog and caps the walk. This is not
    the leftover untemplated Stortinget documentation paths
    (`--source stortinget`).
    """

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = (LIST_URL,)
    ingest_reason = INGEST_REASON

    def __init__(
        self,
        *,
        list_url: str = LIST_URL,
        max_items: int = DEFAULT_MAX_ITEMS,
        http: HttpClient | None = None,
    ) -> None:
        self.list_url = list_url
        self.max_items = max_items
        self.http = http or HttpClient(
            limiter=RateLimiter(STPERIODER_RPS, STPERIODER_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._catalog()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            ident = printed_periode_id(item)
            refs.append(
                DatasetRef(
                    source_native_uri=printed_item_url(item, self.list_url),
                    source_native_id=ident,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident = ref.source_native_id or stperioder_table_id(ref.source_native_uri or "")
        item = self._catalog_item(ident)
        endpoint = printed_item_url(item, self.list_url)
        title = printed_title(item, ident)
        payload = {
            "id": ident,
            "uri": endpoint,
            "title": title,
            "description": None,
            "publisher": None,
            "license": None,
            "distribution": [
                {
                    "accessURL": [endpoint],
                    "downloadURL": [endpoint],
                }
            ],
            "landingPage": [self.list_url],
            "stperioder_periode": {
                key: item[key]
                for key in item
                if _is_scalar(item[key])
            },
            "stperioder_self_href": endpoint,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ident,
            source_native_uri=endpoint,
            fetched_from=self.list_url,
            payload=payload,
        )

    def _catalog(self) -> list[dict[str, Any]]:
        if self._listed is not None:
            return self._listed
        try:
            body = self.http.get_json(self.list_url)
        except Exception as exc:
            raise SourceError(
                f"Stortinget stortingsperioder catalog failed for {self.list_url}: {exc}"
            ) from exc
        listed = printed_perioder(body)
        if not listed:
            raise SourceError("Stortinget stortingsperioder catalog printed no periods")
        self._listed = listed
        return listed

    def _catalog_item(self, ident: str) -> dict[str, Any]:
        for item in self._catalog():
            if printed_periode_id(item) == ident:
                return item
        raise SourceError(
            f"Stortinget stortingsperioder catalog has no printed period {ident}"
        )


def printed_perioder(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise SourceError("Stortinget stortingsperioder catalog is not a JSON object")
    items = body.get("stortingsperioder_liste")
    if not isinstance(items, list):
        raise SourceError(
            "Stortinget stortingsperioder catalog has no printed stortingsperioder_liste"
        )
    listed: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            printed_periode_id(item)
        except SourceError:
            continue
        listed.append(item)
    return listed


def printed_periode_id(item: dict[str, Any]) -> str:
    ident = item.get("id")
    if isinstance(ident, bool):
        raise SourceError("Stortinget stortingsperiode has no printed id")
    if isinstance(ident, int):
        return str(ident)
    if isinstance(ident, str) and ident.strip():
        return ident.strip()
    raise SourceError("Stortinget stortingsperiode has no printed id")


def printed_item_url(item: dict[str, Any], list_url: str) -> str:
    """Join printed periode id onto the leftover representanter collection.

    The official technical documentation prints
    `/eksport/representanter?stortingsperiodeid=` and `format=json`.
    The catalog prints each `id`. Those printed values are copied.
    No other query filter is invented.
    """

    parts = urlsplit(list_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Stortinget stortingsperioder catalog URL has no printed origin")
    ident = printed_periode_id(item)
    query = urlencode({PERIODE_QUERY: ident, "format": FORMAT_QUERY})
    return f"{parts.scheme}://{parts.netloc}{REPRESENTANTER_PATH}?{query}"


def printed_title(item: dict[str, Any], ident: str) -> dict[str, str]:
    return {"no": ident}


def is_stperioder_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    if parsed.netloc.lower() != HOST:
        return False
    if parsed.path.rstrip("/") != REPRESENTANTER_PATH:
        return False
    query = parse_qs(parsed.query, keep_blank_values=True)
    values = query.get(PERIODE_QUERY) or []
    return bool(values) and bool(values[0].strip())


def stperioder_table_id(access_path: str) -> str:
    query = parse_qs(urlsplit(access_path).query, keep_blank_values=True)
    values = query.get(PERIODE_QUERY) or []
    if values and values[0].strip():
        return values[0].strip()
    return "stperioder"


def cells_from_stperioder(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    if not isinstance(payload, dict):
        raise ValueError("stperioder payload is not a JSON object")
    items = payload.get("representanter_liste")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                cells.extend(_cells_from_record(item))
    if not cells:
        cells.extend(_cells_from_record(payload))
    if not cells:
        raise ValueError("stperioder payload printed no representant members")
    return cells


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


def representanter_from_payload(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("representanter payload is not a JSON object")
    listed = payload.get(LIST_KEY)
    if not isinstance(listed, list) or not listed:
        raise ValueError("representanter payload printed no members")
    out = []
    for item in listed:
        if isinstance(item, dict):
            out.append(entity_from_representant(item))
    if not out:
        raise ValueError("representanter payload printed no member objects")
    return out


def selected_member(
    select: dict[str, list[str]] | None,
) -> tuple[list[str] | None, int]:
    select = {str(k): v for k, v in (select or {}).items()}
    allowed = {"id", "antall"}
    unknown = sorted(key for key in select if key not in allowed)
    if unknown:
        raise ValueError(
            f"select names field(s) {unknown} that a period-representanter fetch "
            f"does not filter on; accepted: {sorted(allowed)}"
        )
    limit = DEFAULT_LIMIT
    if "antall" in select:
        wanted = select["antall"]
        wanted = [wanted] if isinstance(wanted, str) else list(wanted)
        try:
            limit = int(str(wanted[0]))
        except (ValueError, IndexError) as exc:
            raise ValueError(f"select[antall]={select['antall']!r} is not a number") from exc
        if limit < 1:
            raise ValueError(f"select[antall]={limit} must be at least 1")
    if "id" not in select:
        return None, limit
    values = select["id"]
    values = [values] if isinstance(values, str) else [str(v) for v in values]
    if len(values) != 1:
        raise ValueError("select id accepts exactly one representant id")
    return values, 1

