from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "stsporre"
SOURCE_NAME = "Stortinget leftover sesjoner sporretimesporsmal"
LIST_URL = "https://data.stortinget.no/eksport/sesjoner?format=json"
SPORRE_PATH = "/eksport/sporretimesporsmal"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed sesjon on the official Stortinget "
    f"sesjoner catalog, capped at {DEFAULT_MAX_ITEMS} sessions"
)
STSPORRE_RPS = 2.0
STSPORRE_BURST = 4
HOST = "data.stortinget.no"
FORMAT_QUERY = "json"
SESJON_QUERY = "sesjonid"
NAME_FIELDS = ("tittel", "id")
SUBJECT_SCHEME = "stortinget:sporsmal_id"
LIST_KEY = "sporsmal_liste"
DEFAULT_LIMIT = 10
MAX_LIMIT = 100
_SKIP_KEYS = {"respons_dato_tid", "versjon"}


class StsporreSource(SourceBase):
    """Replaceable ingest adapter for leftover Stortinget session sporretimesporsmal.

    Listing copies printed `sesjoner_liste[].id` values from the official
    `/eksport/sesjoner?format=json` catalog. It does not invent ids.
    `access_path` joins each printed id onto the leftover
    `/eksport/sporretimesporsmal` collection the official technical
    documentation prints, keeping the documented `sesjonid` and
    `format=json` query. Live GET of those joined paths is HTTP 200. This
    first slice stays inside that catalog and caps the walk. This is not
    the leftover untemplated Stortinget documentation paths
    (`--source stortinget`), not leftover stortingsperioder representanter
    (`--source stperioder`), not leftover sesjoner saker
    (`--source stsaker`), not leftover sesjoner komiteer
    (`--source stkomiteer`), and not leftover sesjoner partier
    (`--source stpartier`).
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
            limiter=RateLimiter(STSPORRE_RPS, STSPORRE_BURST),
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
        ident = ref.source_native_id or stsporre_table_id(ref.source_native_uri or "")
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
            "stsporre_sesjon": {
                key: item[key]
                for key in item
                if _is_scalar(item[key])
            },
            "stsporre_self_href": endpoint,
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
    """Join printed sesjon id onto the leftover sporretimesporsmal collection.

    The official technical documentation prints
    `/eksport/sporretimesporsmal?sesjonid=` and `format=json`.
    The catalog prints each `id`. Those printed values are copied.
    No other query filter is invented.
    """

    parts = urlsplit(list_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Stortinget sesjoner catalog URL has no printed origin")
    ident = printed_sesjon_id(item)
    query = urlencode({SESJON_QUERY: ident, "format": FORMAT_QUERY})
    return f"{parts.scheme}://{parts.netloc}{SPORRE_PATH}?{query}"


def printed_title(item: dict[str, Any], ident: str) -> dict[str, str]:
    return {"no": ident}


def is_stsporre_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    if parsed.netloc.lower() != HOST:
        return False
    if parsed.path.rstrip("/") != SPORRE_PATH:
        return False
    query = parse_qs(parsed.query, keep_blank_values=True)
    values = query.get(SESJON_QUERY) or []
    return bool(values) and bool(values[0].strip())


def stsporre_table_id(access_path: str) -> str:
    query = parse_qs(urlsplit(access_path).query, keep_blank_values=True)
    values = query.get(SESJON_QUERY) or []
    if values and values[0].strip():
        return values[0].strip()
    return "stsporre"


def cells_from_stsporre(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    if not isinstance(payload, dict):
        raise ValueError("stsporre payload is not a JSON object")
    items = payload.get("sporsmal_liste")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                cells.extend(_cells_from_record(item))
    if not cells:
        cells.extend(_cells_from_record(payload))
    if not cells:
        raise ValueError("stsporre payload printed no sporsmal members")
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


def document_from_sporsmal(item: dict[str, Any]) -> dict[str, Any]:
    code = _id_code(item.get("id"))
    if not code:
        raise ValueError("Stortinget question printed no id")
    label = _string(item.get("tittel")) or code
    attributes: dict[str, Any] = {}
    for key, value in item.items():
        if key in _SKIP_KEYS:
            continue
        if isinstance(value, dict):
            _flatten_nested(attributes, key, value)
            continue
        if isinstance(value, list):
            continue
        if value is None:
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


def documents_from_payload(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("sporretimesporsmal payload is not a JSON object")
    listed = payload.get(LIST_KEY)
    if not isinstance(listed, list) or not listed:
        raise ValueError("sporretimesporsmal payload printed no questions")
    out = []
    for item in listed:
        if isinstance(item, dict):
            out.append(document_from_sporsmal(item))
    if not out:
        raise ValueError("sporretimesporsmal payload printed no question objects")
    return out


def shape_from_sporsmal(
    documents: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ids = [
        {"value_code": item["subject_code"], "value_label": item["subject_label"]}
        for item in documents[:20]
    ]
    fields = [
        {
            "field_code": "id",
            "field_label": "id",
            "field_role": "key",
            "values": ids,
        },
        {
            "field_code": "tittel",
            "field_label": "tittel",
            "field_role": "attribute",
            "values": [],
        },
        {
            "field_code": "sesjon_id",
            "field_label": "sesjon",
            "field_role": "attribute",
            "values": [],
        },
        {
            "field_code": "sporsmal_fra.id",
            "field_label": "spørsmål fra",
            "field_role": "attribute",
            "values": [],
        },
        {
            "field_code": "sporsmal_til_minister_tittel",
            "field_label": "til minister",
            "field_role": "attribute",
            "values": [],
        },
    ]
    keys = [
        {
            "scheme": SUBJECT_SCHEME,
            "field_code": "id",
            "coverage_count": len(documents),
        }
    ]
    return fields, keys


def selected_question(
    select: dict[str, list[str]] | None,
) -> tuple[list[str] | None, int]:
    """Return (ids or None for a page, page size). Unknown fields error."""

    select = {str(k): v for k, v in (select or {}).items()}
    allowed = {"id", "antall"}
    unknown = sorted(key for key in select if key not in allowed)
    if unknown:
        raise ValueError(
            f"select names field(s) {unknown} that a sporretimesporsmal fetch "
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
        raise ValueError("select id accepts exactly one question id")
    return values, 1


def _flatten_nested(attributes: dict[str, Any], prefix: str, value: dict[str, Any]) -> None:
    nested_id = _id_code(value.get("id")) or _string(value.get("id"))
    nested_fornavn = _string(value.get("fornavn"))
    nested_etternavn = _string(value.get("etternavn"))
    nested_navn = _string(value.get("navn"))
    if nested_id:
        attributes[f"{prefix}.id"] = nested_id
    if nested_fornavn:
        attributes[f"{prefix}.fornavn"] = nested_fornavn
    if nested_etternavn:
        attributes[f"{prefix}.etternavn"] = nested_etternavn
    if nested_navn:
        attributes[f"{prefix}.navn"] = nested_navn
    for child_key in ("parti", "fylke"):
        child = value.get(child_key)
        if isinstance(child, dict):
            _flatten_nested(attributes, f"{prefix}.{child_key}", child)


def _id_code(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
