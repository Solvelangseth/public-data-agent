from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "kifylker"
SOURCE_NAME = "Kartverket Kommuneinfo fylker"
LIST_URL = "https://api.kartverket.no/kommuneinfo/v1/fylker"
PATH_PREFIX = "/kommuneinfo/v1/fylker"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed fylke on the official Kartverket Kommuneinfo "
    f"fylker catalog, capped at {DEFAULT_MAX_ITEMS} fylker"
)
KIFYLKER_RPS = 2.0
KIFYLKER_BURST = 4
HOST = "api.kartverket.no"
NAME_FIELDS = ("fylkesnavn", "fylkesnummer")


class KifylkerSource(SourceBase):
    """Replaceable ingest adapter for leftover Kartverket Kommuneinfo fylker.

    Listing copies printed `fylkesnummer` values from the official
    `/kommuneinfo/v1/fylker` catalog. It does not invent ids. `access_path`
    joins each printed `fylkesnummer` onto that same `/fylker` path. The
    official Kommuneinfo OpenAPI names GET `/fylker/{fylkesnummer}`. Live
    GET of those joined paths is HTTP 200. This first slice stays inside
    that catalog and caps the walk. This is not Kartverket Kommuneinfo
    OpenAPI collection paths (`--source kommuneinfo`) and not
    Enhetsregisteret kommuner (`--source brkommuner`).
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
            limiter=RateLimiter(KIFYLKER_RPS, KIFYLKER_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._catalog()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            ident = printed_fylkesnummer(item)
            refs.append(
                DatasetRef(
                    source_native_uri=printed_item_url(item, self.list_url),
                    source_native_id=ident,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident = ref.source_native_id or kifylker_table_id(ref.source_native_uri or "")
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
            "kifylker_fylke": {
                key: item[key]
                for key in item
                if key not in {"avgrensningsboks", "kommuner"}
            },
            "kifylker_self_href": endpoint,
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
                f"Kartverket Kommuneinfo fylker catalog failed for {self.list_url}: {exc}"
            ) from exc
        listed = printed_fylker(body)
        if not listed:
            raise SourceError("Kartverket Kommuneinfo fylker catalog printed no fylker")
        self._listed = listed
        return listed

    def _catalog_item(self, ident: str) -> dict[str, Any]:
        for item in self._catalog():
            if printed_fylkesnummer(item) == ident:
                return item
        raise SourceError(
            f"Kartverket Kommuneinfo fylker catalog has no printed fylke {ident}"
        )


def printed_fylker(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, list):
        raise SourceError("Kartverket Kommuneinfo fylker catalog is not a JSON array")
    listed: list[dict[str, Any]] = []
    for item in body:
        if not isinstance(item, dict):
            continue
        try:
            printed_fylkesnummer(item)
        except SourceError:
            continue
        listed.append(item)
    return listed


def printed_fylkesnummer(item: dict[str, Any]) -> str:
    ident = item.get("fylkesnummer")
    if isinstance(ident, str) and ident.strip():
        return ident.strip()
    raise SourceError("Kartverket Kommuneinfo fylke has no printed fylkesnummer")


def printed_item_url(item: dict[str, Any], list_url: str) -> str:
    """Join printed fylkesnummer onto the printed /kommuneinfo/v1/fylker path.

    The catalog is `/kommuneinfo/v1/fylker`. Each printed member has
    `fylkesnummer`. That printed field is copied onto that same path.
    The official OpenAPI names GET `/fylker/{fylkesnummer}`. Live GET of
    `/kommuneinfo/v1/fylker/{fylkesnummer}` is HTTP 200. No fylkesnummer
    is invented.
    """

    parts = urlsplit(list_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Kartverket Kommuneinfo fylker catalog URL has no printed origin")
    ident = printed_fylkesnummer(item)
    return f"{parts.scheme}://{parts.netloc}{PATH_PREFIX}/{ident}"


def printed_title(item: dict[str, Any], ident: str) -> dict[str, str]:
    name = item.get("fylkesnavn")
    if isinstance(name, str) and name.strip():
        return {"no": name.strip()}
    return {"no": ident}


def is_kifylker_url(access_path: str | None) -> bool:
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


def kifylker_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "kifylker"


def cells_from_kifylker(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    if not isinstance(payload, dict):
        raise ValueError("kifylker payload is not a JSON object")
    cells = _cells_from_record(
        {
            key: value
            for key, value in payload.items()
            if key not in {"avgrensningsboks", "kommuner"}
        }
    )
    if not cells:
        raise ValueError("kifylker payload printed no fylke members")
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
