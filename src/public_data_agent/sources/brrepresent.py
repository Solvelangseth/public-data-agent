from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "brrepresent"
SOURCE_NAME = "Brønnøysundregistrene Enhetsregisteret rollerepresentanter"
LIST_URL = "https://data.brreg.no/enhetsregisteret/api/roller/representanter"
PATH_PREFIX = "/enhetsregisteret/api/roller/representanter"
DEFAULT_MAX_ITEMS = 100
INGEST_REASON = (
    "listed as a printed representant on the official Enhetsregisteret "
    f"representanter catalog, with a safety ceiling of {DEFAULT_MAX_ITEMS} codes"
)
BRREPRESENT_RPS = 2.0
BRREPRESENT_BURST = 4
HOST = "data.brreg.no"
NAME_FIELDS = ("beskrivelse", "kode")
REPRESENTANT_SCHEME = "brreg:representant"


class BrrepresentSource(SourceBase):
    """Replaceable ingest adapter for leftover Enhetsregisteret representanter.

    Listing copies printed `_embedded.representanter[].kode` values from the
    official `/enhetsregisteret/api/roller/representanter` collection. Native
    ids are the printed `kode` strings so `A-AK` stays distinct from
    `AREP`. `access_path` joins each printed kode onto that same public
    collection path. Printed `_links.self.href` values point at
    `/enhetsregisteret/autorisert-api/roller/representanter/{kode}` and that
    host path is HTTP 401, so those hrefs are not copied. This first
    slice stays inside that catalog and caps the walk. This is not the
    Enhetsregisteret HAL root (`--source brreg`), not leftover roller
    OpenAPI paths (`--source brroller`), not rolletyper
    (`--source brrolletype`), and not organisasjonsformer
    (`--source brorgform`).
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
            limiter=RateLimiter(BRREPRESENT_RPS, BRREPRESENT_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._catalog()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            ident = printed_kode(item)
            refs.append(
                DatasetRef(
                    source_native_uri=printed_item_url(item, self.list_url),
                    source_native_id=ident,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident = ref.source_native_id or brrepresent_table_id(ref.source_native_uri or "")
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
            "brrepresent_representant": {
                key: item[key]
                for key in item
                if key != "_links"
            },
            "brrepresent_self_href": endpoint,
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
                f"Enhetsregisteret representanter catalog failed for {self.list_url}: {exc}"
            ) from exc
        listed = printed_representanter(body)
        if not listed:
            raise SourceError("Enhetsregisteret representanter catalog printed no representanter")
        self._listed = listed
        return listed

    def _catalog_item(self, ident: str) -> dict[str, Any]:
        for item in self._catalog():
            if printed_kode(item) == ident:
                return item
        raise SourceError(f"Enhetsregisteret representanter catalog has no printed kode {ident}")


def printed_representanter(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise SourceError("Enhetsregisteret representanter catalog is not a JSON object")
    embedded = body.get("_embedded")
    if not isinstance(embedded, dict):
        raise SourceError("Enhetsregisteret representanter catalog has no printed _embedded object")
    items = embedded.get("representanter")
    if not isinstance(items, list):
        raise SourceError("Enhetsregisteret representanter catalog has no printed representanter array")
    listed: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            printed_kode(item)
        except SourceError:
            continue
        listed.append(item)
    return listed


def printed_kode(item: dict[str, Any]) -> str:
    kode = item.get("kode")
    if isinstance(kode, str) and kode.strip():
        return kode.strip()
    raise SourceError("Enhetsregisteret representant has no printed kode")


def printed_item_url(item: dict[str, Any], list_url: str) -> str:
    """Join printed kode onto the printed /api/roller/representanter path.

    The catalog is `/enhetsregisteret/api/roller/representanter`. Each printed
    member has `kode`. That printed field is copied onto that same public
    path. Printed `self` hrefs point at `/enhetsregisteret/autorisert-api/`
    and that path is HTTP 401, so they are not copied. No kode is invented.
    """

    parts = urlsplit(list_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Enhetsregisteret representanter catalog URL has no printed origin")
    kode = printed_kode(item)
    return f"{parts.scheme}://{parts.netloc}{PATH_PREFIX}/{kode}"


def printed_title(item: dict[str, Any], ident: str) -> dict[str, str]:
    name = item.get("beskrivelse")
    if isinstance(name, str) and name.strip():
        return {"no": name.strip()}
    return {"no": ident}


def is_brrepresent_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    if parsed.netloc.lower() != HOST:
        return False
    path = parsed.path.rstrip("/")
    prefix = PATH_PREFIX + "/"
    if not path.startswith(prefix):
        return False
    rest = path[len(prefix) :]
    return bool(rest) and "/" not in rest


def brrepresent_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "brrepresent"


def cells_from_brrepresent(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Legacy observation projection. Prefer entity_from_brrepresent."""

    if not isinstance(payload, dict):
        raise ValueError("brrepresent payload is not a JSON object")
    cells = _cells_from_record(
        {key: value for key, value in payload.items() if key != "_links"}
    )
    if not cells:
        raise ValueError("brrepresent payload printed no representant members")
    return cells


def entity_from_brrepresent(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("brrepresent payload is not a JSON object")
    code = payload.get("kode")
    if not isinstance(code, str) or not code.strip():
        raise ValueError("brrepresent payload printed no kode")
    description = payload.get("beskrivelse")
    label = description.strip() if isinstance(description, str) and description.strip() else None
    return {
        "subject_scheme": REPRESENTANT_SCHEME,
        "subject_code": code.strip(),
        "subject_label": label,
        "attributes": {
            str(key): value
            for key, value in payload.items()
            if key not in {"kode", "beskrivelse", "_links"}
        },
    }


def shape_from_brrepresent(
    payload: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    entity = entity_from_brrepresent(payload)
    code, label = entity["subject_code"], entity["subject_label"]
    fields: list[dict[str, Any]] = [
        {
            "field_code": "kode", "field_label": "kode", "field_role": "key",
            "value_count": 1, "values": [{"value_code": code, "value_label": label}],
        }
    ]
    if label is not None:
        fields.append(
            {
                "field_code": "beskrivelse", "field_label": "beskrivelse",
                "field_role": "attribute", "value_count": 1,
                "values": [{"value_code": label, "value_label": label}],
            }
        )
    return fields, [
        {
            "scheme": REPRESENTANT_SCHEME,
            "field_code": "kode",
            "coverage_count": 1,
        }
    ]


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
