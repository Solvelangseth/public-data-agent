from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "stpartier"
SOURCE_NAME = "Stortinget leftover sesjoner partier"
LIST_URL = "https://data.stortinget.no/eksport/sesjoner?format=json"
PARTIER_PATH = "/eksport/partier"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed sesjon on the official Stortinget "
    f"sesjoner catalog, capped at {DEFAULT_MAX_ITEMS} sessions"
)
STPARTIER_RPS = 2.0
STPARTIER_BURST = 4
HOST = "data.stortinget.no"
FORMAT_QUERY = "json"
SESJON_QUERY = "sesjonid"
NAME_FIELDS = ("navn", "id")
SUBJECT_SCHEME = "stortinget:parti_id"
LIST_KEY = "partier_liste"
_SKIP_KEYS = {"respons_dato_tid", "versjon"}


class StpartierSource(SourceBase):
    """Replaceable ingest adapter for leftover Stortinget session partier.

    Listing copies printed `sesjoner_liste[].id` values from the official
    `/eksport/sesjoner?format=json` catalog. It does not invent ids.
    `access_path` joins each printed id onto the leftover `/eksport/partier`
    collection the official technical documentation prints, keeping the
    documented `sesjonid` and `format=json` query. Live GET of those joined
    paths is HTTP 200. This first slice stays inside that catalog and caps
    the walk. This is not the leftover untemplated Stortinget documentation
    paths (`--source stortinget`), not leftover stortingsperioder
    representanter (`--source stperioder`), and not leftover sesjoner saker
    (`--source stsaker`).
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
            limiter=RateLimiter(STPARTIER_RPS, STPARTIER_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._catalog()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            ident = printed_sesjon_id(item)
            refs.append(
                DatasetRef(
                    source_native_uri=printed_item_url(item, self.list_url),
                    source_native_id=ident,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident = ref.source_native_id or stpartier_table_id(ref.source_native_uri or "")
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
            "stpartier_sesjon": {
                key: item[key]
                for key in item
                if _is_scalar(item[key])
            },
            "stpartier_self_href": endpoint,
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
                f"Stortinget sesjoner catalog failed for {self.list_url}: {exc}"
            ) from exc
        listed = printed_sesjoner(body)
        if not listed:
            raise SourceError("Stortinget sesjoner catalog printed no sessions")
        self._listed = listed
        return listed

    def _catalog_item(self, ident: str) -> dict[str, Any]:
        for item in self._catalog():
            if printed_sesjon_id(item) == ident:
                return item
        raise SourceError(
            f"Stortinget sesjoner catalog has no printed session {ident}"
        )


def printed_sesjoner(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise SourceError("Stortinget sesjoner catalog is not a JSON object")
    items = body.get("sesjoner_liste")
    if not isinstance(items, list):
        raise SourceError(
            "Stortinget sesjoner catalog has no printed sesjoner_liste"
        )
    listed: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            printed_sesjon_id(item)
        except SourceError:
            continue
        listed.append(item)
    return listed


def printed_sesjon_id(item: dict[str, Any]) -> str:
    ident = item.get("id")
    if isinstance(ident, bool):
        raise SourceError("Stortinget sesjon has no printed id")
    if isinstance(ident, int):
        return str(ident)
    if isinstance(ident, str) and ident.strip():
        return ident.strip()
    raise SourceError("Stortinget sesjon has no printed id")


def printed_item_url(item: dict[str, Any], list_url: str) -> str:
    """Join printed sesjon id onto the leftover partier collection.

    The official technical documentation prints
    `/eksport/partier?sesjonid=` and `format=json`.
    The catalog prints each `id`. Those printed values are copied.
    No other query filter is invented.
    """

    parts = urlsplit(list_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Stortinget sesjoner catalog URL has no printed origin")
    ident = printed_sesjon_id(item)
    query = urlencode({SESJON_QUERY: ident, "format": FORMAT_QUERY})
    return f"{parts.scheme}://{parts.netloc}{PARTIER_PATH}?{query}"


def printed_title(item: dict[str, Any], ident: str) -> dict[str, str]:
    return {"no": ident}


def is_stpartier_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    if parsed.netloc.lower() != HOST:
        return False
    if parsed.path.rstrip("/") != PARTIER_PATH:
        return False
    query = parse_qs(parsed.query, keep_blank_values=True)
    values = query.get(SESJON_QUERY) or []
    return bool(values) and bool(values[0].strip())


def stpartier_table_id(access_path: str) -> str:
    query = parse_qs(urlsplit(access_path).query, keep_blank_values=True)
    values = query.get(SESJON_QUERY) or []
    if values and values[0].strip():
        return values[0].strip()
    return "stpartier"


def cells_from_stpartier(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    if not isinstance(payload, dict):
        raise ValueError("stpartier payload is not a JSON object")
    items = payload.get("partier_liste")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                cells.extend(_cells_from_record(item))
    if not cells:
        cells.extend(_cells_from_record(payload))
    if not cells:
        raise ValueError("stpartier payload printed no parti members")
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


def entity_from_parti(item: dict[str, Any]) -> dict[str, Any]:
    code = _string(item.get("id"))
    if not code:
        raise ValueError("Stortinget party printed no id")
    label = _string(item.get("navn")) or code
    attributes: dict[str, Any] = {}
    for key, value in item.items():
        if key in _SKIP_KEYS:
            continue
        if isinstance(value, (dict, list)) or value is None:
            continue
        if key == "id":
            attributes[key] = code
            continue
        attributes[key] = value
    return {
        "subject_scheme": SUBJECT_SCHEME,
        "subject_code": code,
        "subject_label": label,
        "attributes": attributes,
    }


def parties_from_payload(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("partier payload is not a JSON object")
    listed = payload.get(LIST_KEY)
    if not isinstance(listed, list) or not listed:
        raise ValueError("partier payload printed no parties")
    out = []
    for item in listed:
        if isinstance(item, dict):
            out.append(entity_from_parti(item))
    if not out:
        raise ValueError("partier payload printed no party objects")
    return out


def shape_from_partier(
    parties: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ids = [
        {"value_code": item["subject_code"], "value_label": item["subject_label"]}
        for item in parties
    ]
    fields = [
        {
            "field_code": "id",
            "field_label": "id",
            "field_role": "key",
            "values": ids,
        },
        {
            "field_code": "navn",
            "field_label": "navn",
            "field_role": "attribute",
            "values": [],
        },
        {
            "field_code": "representert_parti",
            "field_label": "representert",
            "field_role": "attribute",
            "values": [],
        },
    ]
    keys = [
        {
            "scheme": SUBJECT_SCHEME,
            "field_code": "id",
            "coverage_count": len(parties),
        }
    ]
    return fields, keys


def selected_ids(select: dict[str, list[str]] | None) -> list[str] | None:
    if not select:
        return None
    unknown = sorted(key for key in select if key != "id")
    if unknown:
        raise ValueError(
            f"select names field(s) {unknown} that a partier fetch does not filter on; "
            "only id is accepted, or omit select for the session list"
        )
    wanted = select.get("id") or []
    wanted = [wanted] if isinstance(wanted, str) else [str(item) for item in wanted]
    if not wanted:
        raise ValueError("select id is empty")
    return wanted


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None

