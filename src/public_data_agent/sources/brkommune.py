from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "brkommune"
SOURCE_NAME = "Brønnøysundregistrene Enhetsregisteret kommuner"
LIST_URL = "https://data.brreg.no/enhetsregisteret/api/kommuner"
PATH_PREFIX = "/enhetsregisteret/api/kommuner"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed kommune on the official Enhetsregisteret "
    f"kommuner catalog, capped at {DEFAULT_MAX_ITEMS} codes"
)
BRKOMMUNE_RPS = 2.0
BRKOMMUNE_BURST = 4
HOST = "data.brreg.no"
NAME_FIELDS = ("navn", "nummer")


class BrkommuneSource(SourceBase):
    """Replaceable ingest adapter for leftover Enhetsregisteret kommuner.

    Listing copies printed `_embedded.kommuner[].nummer` values and the
    printed `_links.self.href` from the official
    `/enhetsregisteret/api/kommuner` collection. Native ids are the
    printed `nummer` strings so `0301` stays distinct from `1101`. This
    first slice stays inside that catalog and caps the walk. This is not
    the Enhetsregisteret HAL root (`--source brreg`), not
    organisasjonsformer (`--source brorgform`), not leftover roller
    lists (`--source brroller`), and not Kartverket Kommuneinfo
    (`--source kommuneinfo`).
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
            limiter=RateLimiter(BRKOMMUNE_RPS, BRKOMMUNE_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._catalog()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            ident = printed_nummer(item)
            refs.append(
                DatasetRef(
                    source_native_uri=printed_item_url(item, self.list_url),
                    source_native_id=ident,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident = ref.source_native_id or brkommune_table_id(ref.source_native_uri or "")
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
            "brkommune_kommune": {
                key: item[key]
                for key in item
                if key != "_links"
            },
            "brkommune_self_href": endpoint,
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
                f"Enhetsregisteret kommuner catalog failed for {self.list_url}: {exc}"
            ) from exc
        listed = printed_kommuner(body)
        if not listed:
            raise SourceError("Enhetsregisteret kommuner catalog printed no kommuner")
        self._listed = listed
        return listed

    def _catalog_item(self, ident: str) -> dict[str, Any]:
        for item in self._catalog():
            if printed_nummer(item) == ident:
                return item
        raise SourceError(f"Enhetsregisteret kommuner catalog has no printed nummer {ident}")


def printed_kommuner(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise SourceError("Enhetsregisteret kommuner catalog is not a JSON object")
    embedded = body.get("_embedded")
    if not isinstance(embedded, dict):
        raise SourceError("Enhetsregisteret kommuner catalog has no printed _embedded object")
    items = embedded.get("kommuner")
    if not isinstance(items, list):
        raise SourceError("Enhetsregisteret kommuner catalog has no printed kommuner array")
    listed: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            printed_nummer(item)
        except SourceError:
            continue
        listed.append(item)
    return listed


def printed_nummer(item: dict[str, Any]) -> str:
    nummer = item.get("nummer")
    if isinstance(nummer, str) and nummer.strip():
        return nummer.strip()
    raise SourceError("Enhetsregisteret kommune has no printed nummer")


def printed_item_url(item: dict[str, Any], list_url: str) -> str:
    links = item.get("_links")
    if isinstance(links, dict):
        self_link = links.get("self")
        if isinstance(self_link, dict):
            href = self_link.get("href")
            if isinstance(href, str) and href.strip():
                return href.strip()
    parts = urlsplit(list_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Enhetsregisteret kommuner catalog URL has no printed origin")
    nummer = printed_nummer(item)
    return f"{parts.scheme}://{parts.netloc}{PATH_PREFIX}/{nummer}"


def printed_title(item: dict[str, Any], ident: str) -> dict[str, str]:
    name = item.get("navn")
    if isinstance(name, str) and name.strip():
        return {"no": name.strip()}
    return {"no": ident}


def is_brkommune_url(access_path: str | None) -> bool:
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


def brkommune_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "brkommune"


def cells_from_brkommune(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    if not isinstance(payload, dict):
        raise ValueError("brkommune payload is not a JSON object")
    cells = _cells_from_record(
        {key: value for key, value in payload.items() if key != "_links"}
    )
    if not cells:
        raise ValueError("brkommune payload printed no kommune members")
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
