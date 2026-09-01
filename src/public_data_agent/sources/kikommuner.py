from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "kikommuner"
SOURCE_NAME = "Kartverket Kommuneinfo kommuner"
LIST_URL = "https://api.kartverket.no/kommuneinfo/v1/kommuner"
PATH_PREFIX = "/kommuneinfo/v1/kommuner"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed kommune on the official Kartverket Kommuneinfo "
    f"kommuner catalog, capped at {DEFAULT_MAX_ITEMS} kommuner"
)
KIKOMMUNER_RPS = 2.0
KIKOMMUNER_BURST = 4
HOST = "api.kartverket.no"
NAME_FIELDS = ("kommunenavnNorsk", "kommunenavn", "kommunenummer")
SKIP_NESTED = ("avgrensningsboks", "gyldigeNavn", "punktIOmrade")


class KikommunerSource(SourceBase):
    """Replaceable ingest adapter for leftover Kartverket Kommuneinfo kommuner.

    Listing copies printed `kommunenummer` values from the official
    `/kommuneinfo/v1/kommuner` catalog. It does not invent ids.
    `access_path` joins each printed `kommunenummer` onto that same
    `/kommuner` path. The official Kommuneinfo OpenAPI names GET
    `/kommuner/{kommunenummer}`. Live GET of those joined paths is
    HTTP 200. This first slice stays inside that catalog and caps the
    walk. This is not Kartverket Kommuneinfo OpenAPI collection paths
    (`--source kommuneinfo`), not leftover fylker (`--source kifylker`),
    and not Enhetsregisteret kommuner (`--source brkommuner`).
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
            limiter=RateLimiter(KIKOMMUNER_RPS, KIKOMMUNER_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._catalog()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            ident = printed_kommunenummer(item)
            refs.append(
                DatasetRef(
                    source_native_uri=printed_item_url(item, self.list_url),
                    source_native_id=ident,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident = ref.source_native_id or kikommuner_table_id(ref.source_native_uri or "")
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
            "kikommuner_kommune": {
                key: item[key]
                for key in item
                if key not in SKIP_NESTED
            },
            "kikommuner_self_href": endpoint,
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
                f"Kartverket Kommuneinfo kommuner catalog failed for {self.list_url}: {exc}"
            ) from exc
        listed = printed_kommuner(body)
        if not listed:
            raise SourceError("Kartverket Kommuneinfo kommuner catalog printed no kommuner")
        self._listed = listed
        return listed

    def _catalog_item(self, ident: str) -> dict[str, Any]:
        for item in self._catalog():
            if printed_kommunenummer(item) == ident:
                return item
        raise SourceError(
            f"Kartverket Kommuneinfo kommuner catalog has no printed kommune {ident}"
        )


def printed_kommuner(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, list):
        raise SourceError("Kartverket Kommuneinfo kommuner catalog is not a JSON array")
    listed: list[dict[str, Any]] = []
    for item in body:
        if not isinstance(item, dict):
            continue
        try:
            printed_kommunenummer(item)
        except SourceError:
            continue
        listed.append(item)
    return listed


def printed_kommunenummer(item: dict[str, Any]) -> str:
    ident = item.get("kommunenummer")
    if isinstance(ident, str) and ident.strip():
        return ident.strip()
    raise SourceError("Kartverket Kommuneinfo kommune has no printed kommunenummer")


def printed_item_url(item: dict[str, Any], list_url: str) -> str:
    """Join printed kommunenummer onto the printed /kommuneinfo/v1/kommuner path.

    The catalog is `/kommuneinfo/v1/kommuner`. Each printed member has
    `kommunenummer`. That printed field is copied onto that same path.
    The official OpenAPI names GET `/kommuner/{kommunenummer}`. Live GET
    of `/kommuneinfo/v1/kommuner/{kommunenummer}` is HTTP 200. No
    kommunenummer is invented.
    """

    parts = urlsplit(list_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Kartverket Kommuneinfo kommuner catalog URL has no printed origin")
    ident = printed_kommunenummer(item)
    return f"{parts.scheme}://{parts.netloc}{PATH_PREFIX}/{ident}"


def printed_title(item: dict[str, Any], ident: str) -> dict[str, str]:
    for field in ("kommunenavnNorsk", "kommunenavn"):
        name = item.get(field)
        if isinstance(name, str) and name.strip():
            return {"no": name.strip()}
    return {"no": ident}


def is_kikommuner_url(access_path: str | None) -> bool:
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
    return bool(rest) and "/" not in rest and rest.isdigit()


def kikommuner_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "kikommuner"


def cells_from_kikommuner(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    if not isinstance(payload, dict):
        raise ValueError("kikommuner payload is not a JSON object")
    cells = _cells_from_record(
        {key: value for key, value in payload.items() if key not in SKIP_NESTED}
    )
    if not cells:
        raise ValueError("kikommuner payload printed no kommune members")
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
