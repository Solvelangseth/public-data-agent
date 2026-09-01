from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "ssbsubj"
SOURCE_NAME = "SSB PxWeb leftover subjects"
LIST_URL = "https://data.ssb.no/api/v0/no/table"
PATH_PREFIX = "/api/v0/no/table"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed leftover subject folder on the official SSB PxWeb "
    f"v0 table catalog, capped at {DEFAULT_MAX_ITEMS} subjects"
)
SSBSUBJ_RPS = 2.0
SSBSUBJ_BURST = 4
HOST = "data.ssb.no"
NAME_FIELDS = ("text", "id")


class SsbsubjSource(SourceBase):
    """Replaceable ingest adapter for leftover SSB PxWeb v0 subjects.

    Listing copies printed `id` values from the official
    `/api/v0/no/table` subject catalog. It does not invent ids.
    `access_path` joins each printed `id` onto that same `/table` path.
    Live GET of those joined subject folders is HTTP 200. This first
    slice stays inside that catalog and caps the walk. This is not the
    SSB PxWeb v0 Statbank table walk under subject `be`
    (`--source ssb`), not PxWebApi 2 (`--source ssbv2`), and not Klass
    leftovers (`--source ssclass`, `--source ssbfam`, `--source ssbsec`,
    `--source ssbver`, `--source ssbcorr`, `--source ssbvar`).
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
            limiter=RateLimiter(SSBSUBJ_RPS, SSBSUBJ_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._catalog()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            ident = printed_subject_id(item)
            refs.append(
                DatasetRef(
                    source_native_uri=printed_item_url(item, self.list_url),
                    source_native_id=ident,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident = ref.source_native_id or ssbsubj_table_id(ref.source_native_uri or "")
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
            "ssbsubj_subject": {
                key: item[key]
                for key in item
                if _is_scalar(item[key])
            },
            "ssbsubj_self_href": endpoint,
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
                f"SSB PxWeb leftover subject catalog failed for {self.list_url}: {exc}"
            ) from exc
        listed = printed_subjects(body)
        if not listed:
            raise SourceError("SSB PxWeb leftover subject catalog printed no subjects")
        self._listed = listed
        return listed

    def _catalog_item(self, ident: str) -> dict[str, Any]:
        for item in self._catalog():
            if printed_subject_id(item) == ident:
                return item
        raise SourceError(
            f"SSB PxWeb leftover subject catalog has no printed subject {ident}"
        )


def printed_subjects(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, list):
        raise SourceError("SSB PxWeb leftover subject catalog is not a JSON array")
    listed: list[dict[str, Any]] = []
    for item in body:
        if not isinstance(item, dict):
            continue
        try:
            printed_subject_id(item)
        except SourceError:
            continue
        listed.append(item)
    return listed


def printed_subject_id(item: dict[str, Any]) -> str:
    ident = item.get("id")
    if isinstance(ident, str) and ident.strip() and ident.strip().isalpha():
        return ident.strip()
    raise SourceError("SSB PxWeb leftover subject has no printed alphabetic id")


def printed_item_url(item: dict[str, Any], list_url: str) -> str:
    """Join printed subject id onto the printed /api/v0/no/table path.

    The catalog is `/api/v0/no/table`. Each printed leftover subject has
    `id` and `type=l`. That printed `id` is copied onto that same path.
    Live GET of `/api/v0/no/table/{id}` is HTTP 200. No subject id is
    invented. Five-digit table numbers used by `--source ssb` are not
    copied from this catalog.
    """

    parts = urlsplit(list_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("SSB PxWeb leftover subject catalog URL has no printed origin")
    ident = printed_subject_id(item)
    return f"{parts.scheme}://{parts.netloc}{PATH_PREFIX}/{ident}"


def printed_title(item: dict[str, Any], ident: str) -> dict[str, str]:
    name = item.get("text")
    if isinstance(name, str) and name.strip():
        return {"no": name.strip()}
    return {"no": ident}


def is_ssbsubj_url(access_path: str | None) -> bool:
    """Match leftover `/table/{subject}` folders, not five-digit table ids."""

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
    return bool(rest) and "/" not in rest and rest.isalpha()


def ssbsubj_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "ssbsubj"


def cells_from_ssbsubj(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed leftover-subject folder members into observation cells.

    A live subject GET prints a JSON array of child folders. Each printed
    member keeps `text` when present, otherwise `id`. Other scalars stay
    as dimensions. Nested objects are not copied. A single printed
    subject object is also accepted. Nothing is invented.
    """

    if isinstance(payload, list):
        cells: list[tuple[str, Any, dict[str, str]]] = []
        for item in payload:
            if isinstance(item, dict):
                cells.extend(_cells_from_record(item))
        if not cells:
            raise ValueError("ssbsubj payload printed no subject members")
        return cells
    if not isinstance(payload, dict):
        raise ValueError("ssbsubj payload is not a JSON object")
    cells = _cells_from_record(payload)
    if not cells:
        raise ValueError("ssbsubj payload printed no subject members")
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
