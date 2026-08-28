from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "nbprov"
SOURCE_NAME = "Norges Bank SDMX provision agreements"
LIST_URL = "https://data.norges-bank.no/api/provisionagreement?format=sdmx-json"
PATH_PREFIX = "/api/provisionagreement"
FORMAT_QUERY = "format=sdmx-json"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed provision agreement on the official Norges Bank "
    f"SDMX provisionagreement catalog, capped at {DEFAULT_MAX_ITEMS} agreements"
)
NBPROV_RPS = 2.0
NBPROV_BURST = 4
HOST = "data.norges-bank.no"
NAME_FIELDS = ("name", "id")


class NbprovSource(SourceBase):
    """Replaceable ingest adapter for leftover Norges Bank SDMX provision agreements.

    Listing copies printed `data.provisionAgreements[].id` and `agencyID`
    from the official `/api/provisionagreement` catalog. It does not invent
    ids. `access_path` joins those printed fields onto
    `/api/provisionagreement/{agencyID}/{id}` and keeps the same
    `format=sdmx-json` query the catalog uses. This first slice stays
    inside that catalog and caps the walk. This is not the dataflow list
    (`--source norgesbank`), not the codelist list (`--source nbcodelist`),
    and not the data-structure list (`--source nbdsd`).
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
            limiter=RateLimiter(NBPROV_RPS, NBPROV_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._catalog()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            ident = printed_agreement_id(item)
            refs.append(
                DatasetRef(
                    source_native_uri=printed_item_url(item, self.list_url),
                    source_native_id=ident,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident = ref.source_native_id or nbprov_table_id(ref.source_native_uri or "")
        item = self._catalog_item(ident)
        description = printed_localized(
            item.get("descriptions"),
            item.get("description"),
            None,
        )
        endpoint = printed_item_url(item, self.list_url)
        payload = {
            "id": ident,
            "uri": endpoint,
            "title": printed_title(item, ident),
            "description": ({"no": description} if description else None),
            "publisher": None,
            "license": None,
            "distribution": [
                {
                    "accessURL": [endpoint],
                    "downloadURL": [endpoint],
                }
            ],
            "landingPage": [self.list_url],
            "nbprov_provisionagreement": {
                key: item[key]
                for key in item
                if key not in ("links",)
            },
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
                f"Norges Bank provisionagreement catalog failed for {self.list_url}: {exc}"
            ) from exc
        listed = printed_agreements(body)
        if not listed:
            raise SourceError(
                "Norges Bank provisionagreement catalog printed no provision agreements"
            )
        self._listed = listed
        return listed

    def _catalog_item(self, ident: str) -> dict[str, Any]:
        for item in self._catalog():
            if printed_agreement_id(item) == ident:
                return item
        raise SourceError(
            f"Norges Bank provisionagreement catalog has no printed agreement {ident}"
        )


def printed_agreements(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise SourceError("Norges Bank provisionagreement catalog is not a JSON object")
    data = body.get("data")
    if not isinstance(data, dict):
        raise SourceError(
            "Norges Bank provisionagreement catalog has no printed data object"
        )
    listed_raw = data.get("provisionAgreements")
    if not isinstance(listed_raw, list):
        raise SourceError(
            "Norges Bank provisionagreement catalog has no printed provisionAgreements array"
        )
    listed: list[dict[str, Any]] = []
    for item in listed_raw:
        if not isinstance(item, dict):
            continue
        ident = item.get("id")
        agency = item.get("agencyID")
        if not isinstance(ident, str) or not ident.strip():
            continue
        if not isinstance(agency, str) or not agency.strip():
            continue
        listed.append(item)
    return listed


def printed_agreement_id(item: dict[str, Any]) -> str:
    ident = item.get("id")
    if not isinstance(ident, str) or not ident.strip():
        raise SourceError("Norges Bank provision agreement has no printed id")
    return ident.strip()


def printed_agency_id(item: dict[str, Any]) -> str:
    agency = item.get("agencyID")
    if not isinstance(agency, str) or not agency.strip():
        raise SourceError("Norges Bank provision agreement has no printed agencyID")
    return agency.strip()


def printed_item_url(item: dict[str, Any], list_url: str) -> str:
    """Join printed agencyID and id onto the printed /api/provisionagreement path.

    The catalog is `/api/provisionagreement?format=sdmx-json`. Each printed
    member has `agencyID` and `id`. Those two printed fields are copied onto
    that same path. The `format=sdmx-json` query is copied from the catalog
    because `/api/provisionagreement/{agency}/{id}` without it returns XML.
    No agency or agreement id is invented.
    """

    parts = urlsplit(list_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Norges Bank provisionagreement catalog URL has no printed origin")
    agency = printed_agency_id(item)
    ident = printed_agreement_id(item)
    return f"{parts.scheme}://{parts.netloc}{PATH_PREFIX}/{agency}/{ident}?{FORMAT_QUERY}"


def printed_title(item: dict[str, Any], ident: str) -> dict[str, str]:
    names = item.get("names") if isinstance(item.get("names"), dict) else {}
    title: dict[str, str] = {}
    for lang in ("no", "nb", "nn", "en"):
        value = names.get(lang)
        if isinstance(value, str) and value.strip():
            title[lang] = value.strip()
    if title:
        return title
    name = item.get("name")
    if isinstance(name, str) and name.strip():
        return {"en": name.strip()}
    return {"en": ident}


def printed_localized(names: Any, fallback: Any, default: str | None) -> str | None:
    if isinstance(names, dict):
        for lang in ("no", "nb", "nn", "en"):
            value = names.get(lang)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(fallback, str) and fallback.strip():
        return fallback.strip()
    return default


def is_nbprov_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    path = parsed.path.rstrip("/")
    if parsed.netloc.lower() != HOST or not path.startswith(PATH_PREFIX + "/"):
        return False
    leftover = path[len(PATH_PREFIX) + 1 :]
    return bool(leftover)


def nbprov_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "nbprov"


def cells_from_nbprov(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed SDMX-JSON provision agreements into observation cells.

    Each printed `provisionAgreements[]` member keeps `name` when present,
    otherwise `id`. Other scalars stay as dimensions. Nested `names`,
    `links`, and `descriptions` objects are not copied. Nothing is invented.
    """

    if not isinstance(payload, dict):
        raise ValueError("nbprov payload is not a JSON object")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("nbprov payload has no printed data object")
    listed = data.get("provisionAgreements")
    if not isinstance(listed, list):
        raise ValueError("nbprov payload has no printed provisionAgreements array")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in listed:
        if isinstance(item, dict):
            cells.extend(_cells_from_record(item))
    if not cells:
        raise ValueError("nbprov payload printed no provision agreements")
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
