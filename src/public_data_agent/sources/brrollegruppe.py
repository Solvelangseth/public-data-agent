from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "brrollegruppe"
SOURCE_NAME = "Brønnøysundregistrene Enhetsregisteret rollegruppetyper"
LIST_URL = "https://data.brreg.no/enhetsregisteret/api/roller/rollegruppetyper"
PATH_PREFIX = "/enhetsregisteret/api/roller/rollegruppetyper"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed rollegruppetype on the official Enhetsregisteret "
    f"rollegruppetyper catalog, capped at {DEFAULT_MAX_ITEMS} codes"
)
BRROLLEGRUPPE_RPS = 2.0
BRROLLEGRUPPE_BURST = 4
HOST = "data.brreg.no"
NAME_FIELDS = ("beskrivelse", "kode")


class BrrollegruppeSource(SourceBase):
    """Replaceable ingest adapter for leftover Enhetsregisteret rollegruppetyper.

    Listing copies printed `_embedded.rollegruppetyper[].kode` values from
    the official `/enhetsregisteret/api/roller/rollegruppetyper`
    collection. It does not invent kodes. Printed `_links.self.href`
    values point at `/enhetsregisteret/autorisert-api/` (HTTP 401) and
    are not copied. `access_path` joins each printed `kode` onto the
    printed public collection path. This first slice stays inside that
    catalog and caps the walk. This is not the Enhetsregisteret HAL
    root (`--source brreg`), not leftover roller OpenAPI collection
    GETs (`--source brroller`), not leftover organisasjonsformer
    (`--source brorgform`), and not leftover rolletyper.
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
            limiter=RateLimiter(BRROLLEGRUPPE_RPS, BRROLLEGRUPPE_BURST),
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
        ident = ref.source_native_id or brrollegruppe_table_id(ref.source_native_uri or "")
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
            "brrollegruppe_rollegruppetype": {
                key: item[key]
                for key in item
                if key != "_links"
            },
            "brrollegruppe_self_href": endpoint,
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
                f"Enhetsregisteret rollegruppetyper catalog failed for {self.list_url}: {exc}"
            ) from exc
        listed = printed_rollegruppetyper(body)
        if not listed:
            raise SourceError(
                "Enhetsregisteret rollegruppetyper catalog printed no rollegruppetyper"
            )
        self._listed = listed
        return listed

    def _catalog_item(self, ident: str) -> dict[str, Any]:
        for item in self._catalog():
            if printed_kode(item) == ident:
                return item
        raise SourceError(
            f"Enhetsregisteret rollegruppetyper catalog has no printed kode {ident}"
        )


def printed_rollegruppetyper(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise SourceError("Enhetsregisteret rollegruppetyper catalog is not a JSON object")
    embedded = body.get("_embedded")
    if not isinstance(embedded, dict):
        raise SourceError(
            "Enhetsregisteret rollegruppetyper catalog has no printed _embedded object"
        )
    items = embedded.get("rollegruppetyper")
    if not isinstance(items, list):
        raise SourceError(
            "Enhetsregisteret rollegruppetyper catalog has no printed rollegruppetyper array"
        )
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
    raise SourceError("Enhetsregisteret rollegruppetype has no printed kode")


def printed_item_url(item: dict[str, Any], list_url: str) -> str:
    """Join printed kode onto the printed public rollegruppetyper path.

    The catalog is `/enhetsregisteret/api/roller/rollegruppetyper`. Each
    printed member has `kode`. Printed `_links.self.href` values point at
    `/enhetsregisteret/autorisert-api/` and those GETs are HTTP 401. Those
    hrefs are not copied. The printed kode is joined onto the printed
    public collection path. No kode is invented.
    """

    parts = urlsplit(list_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError(
            "Enhetsregisteret rollegruppetyper catalog URL has no printed origin"
        )
    kode = printed_kode(item)
    return f"{parts.scheme}://{parts.netloc}{PATH_PREFIX}/{kode}"


def printed_title(item: dict[str, Any], ident: str) -> dict[str, str]:
    name = item.get("beskrivelse")
    if isinstance(name, str) and name.strip():
        return {"no": name.strip()}
    return {"no": ident}


def is_brrollegruppe_url(access_path: str | None) -> bool:
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


def brrollegruppe_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "brrollegruppe"


def cells_from_brrollegruppe(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    if not isinstance(payload, dict):
        raise ValueError("brrollegruppe payload is not a JSON object")
    cells = _cells_from_record(
        {key: value for key, value in payload.items() if key != "_links"}
    )
    if not cells:
        raise ValueError("brrollegruppe payload printed no rollegruppetype members")
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
