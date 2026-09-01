from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "fdkorg"
SOURCE_NAME = "Digdir Felles datakatalog organization catalogue"
LIST_URL = "https://organization-catalogue.fellesdatakatalog.digdir.no/organizations"
PATH_PREFIX = "/organizations"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed organization on the official Digdir Felles "
    f"datakatalog organization catalogue, capped at {DEFAULT_MAX_ITEMS} organizations"
)
FDKORG_RPS = 2.0
FDKORG_BURST = 4
HOST = "organization-catalogue.fellesdatakatalog.digdir.no"
NAME_FIELDS = ("name", "organizationId")


class FdkorgSource(SourceBase):
    """Replaceable ingest adapter for leftover Digdir organization catalogue.

    Listing copies printed `organizationId` values from the official
    `/organizations` catalog. It does not invent ids. `access_path` joins
    each printed `organizationId` onto that same `/organizations` path.
    Live GET of those joined paths is HTTP 200. This first slice stays
    inside that catalog and caps the walk. This is not Data.norge
    (`--source datanorge`), not Enhetsregisteret (`--source brreg`), and
    not Kartverket Kommuneinfo (`--source kommuneinfo`).
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
            limiter=RateLimiter(FDKORG_RPS, FDKORG_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._catalog()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            ident = printed_organization_id(item)
            refs.append(
                DatasetRef(
                    source_native_uri=printed_item_url(item, self.list_url),
                    source_native_id=ident,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident = ref.source_native_id or fdkorg_table_id(ref.source_native_uri or "")
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
            "fdkorg_organization": {
                key: item[key]
                for key in item
                if key != "prefLabel"
            },
            "fdkorg_self_href": endpoint,
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
                f"Digdir organization catalogue failed for {self.list_url}: {exc}"
            ) from exc
        listed = printed_organizations(body)
        if not listed:
            raise SourceError("Digdir organization catalogue printed no organizations")
        self._listed = listed
        return listed

    def _catalog_item(self, ident: str) -> dict[str, Any]:
        for item in self._catalog():
            if printed_organization_id(item) == ident:
                return item
        raise SourceError(
            f"Digdir organization catalogue has no printed organization {ident}"
        )


def printed_organizations(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, list):
        raise SourceError("Digdir organization catalogue is not a JSON array")
    listed: list[dict[str, Any]] = []
    for item in body:
        if not isinstance(item, dict):
            continue
        try:
            printed_organization_id(item)
        except SourceError:
            continue
        listed.append(item)
    return listed


def printed_organization_id(item: dict[str, Any]) -> str:
    ident = item.get("organizationId")
    if isinstance(ident, str) and ident.strip():
        return ident.strip()
    raise SourceError("Digdir organization has no printed organizationId")


def printed_item_url(item: dict[str, Any], list_url: str) -> str:
    """Join printed organizationId onto the printed /organizations path.

    The catalog is `/organizations`. Each printed member has
    `organizationId`. That printed field is copied onto that same path.
    Live GET of `/organizations/{organizationId}` is HTTP 200. No
    organization id is invented.
    """

    parts = urlsplit(list_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Digdir organization catalogue URL has no printed origin")
    ident = printed_organization_id(item)
    return f"{parts.scheme}://{parts.netloc}{PATH_PREFIX}/{ident}"


def printed_title(item: dict[str, Any], ident: str) -> dict[str, str]:
    labels = item.get("prefLabel") if isinstance(item.get("prefLabel"), dict) else {}
    title: dict[str, str] = {}
    for lang in ("no", "nb", "nn", "en"):
        value = labels.get(lang)
        if isinstance(value, str) and value.strip():
            title[lang] = value.strip()
    if title:
        return title
    name = item.get("name")
    if isinstance(name, str) and name.strip():
        return {"no": name.strip()}
    return {"no": ident}


def is_fdkorg_url(access_path: str | None) -> bool:
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


def fdkorg_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "fdkorg"


def cells_from_fdkorg(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    if not isinstance(payload, dict):
        raise ValueError("fdkorg payload is not a JSON object")
    cells = _cells_from_record(
        {key: value for key, value in payload.items() if key != "prefLabel"}
    )
    if not cells:
        raise ValueError("fdkorg payload printed no organization members")
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
