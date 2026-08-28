from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "ssbsec"
SOURCE_NAME = "SSB Klass SSB-seksjoner"
LIST_URL = "https://data.ssb.no/api/klass/v1/ssbsections"
OPENAPI_URL = "https://data.ssb.no/api/klass/v3/api-docs"
PATH_PREFIX = "/api/klass/v1/ssbsections"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as the leftover collection GET /api/klass/v1/ssbsections in "
    f"the official Klass OpenAPI, capped at {DEFAULT_MAX_ITEMS} paths"
)
SSBSEC_RPS = 2.0
SSBSEC_BURST = 4
HOST = "data.ssb.no"
NAME_FIELDS = ("name",)


class SsbsecSource(SourceBase):
    """Replaceable ingest adapter for leftover SSB Klass SSB-seksjoner.

    Listing copies the leftover collection GET `/api/klass/v1/ssbsections`
    the official Klass OpenAPI names. The live catalog prints that path
    on `_links.self.href`. Native id is the printed last path segment
    `ssbsections`. Printed member `id` values are null and are not
    copied. This first slice stays inside that document and caps the
    walk. This is not the Klass version fetch and not PxWebApi 2
    (`--source ssbv2`).
    """

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = (LIST_URL, OPENAPI_URL)
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
            limiter=RateLimiter(SSBSEC_RPS, SSBSEC_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None
        self._self_href: str | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._catalog()
        if not listed:
            raise SourceError("SSB Klass ssbsections catalog printed no section names")
        href = self._catalog_href()
        ident = printed_collection_id(href)
        refs = [
            DatasetRef(
                source_native_uri=href,
                source_native_id=ident,
            )
        ]
        return refs[offset : offset + cap]

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        href = self._catalog_href()
        ident = ref.source_native_id or printed_collection_id(href)
        if ident != printed_collection_id(href):
            raise SourceError(
                f"SSB Klass ssbsections catalog has no printed collection {ident}"
            )
        payload = {
            "id": ident,
            "uri": href,
            "title": {"no": ident},
            "description": None,
            "publisher": None,
            "license": None,
            "distribution": [
                {
                    "accessURL": [href],
                    "downloadURL": [href],
                }
            ],
            "landingPage": [self.list_url, OPENAPI_URL],
            "ssbsec_collection": ident,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ident,
            source_native_uri=href,
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
                f"SSB Klass ssbsections catalog failed for {self.list_url}: {exc}"
            ) from exc
        listed, href = printed_sections(body, self.list_url)
        if not listed:
            raise SourceError("SSB Klass ssbsections catalog printed no section names")
        self._listed = listed
        self._self_href = href
        return listed

    def _catalog_href(self) -> str:
        self._catalog()
        if not self._self_href:
            raise SourceError("SSB Klass ssbsections catalog printed no self href")
        return self._self_href


def printed_collection_id(href: str) -> str:
    ident = urlsplit(href).path.rstrip("/").split("/")[-1]
    if not ident:
        raise SourceError("SSB Klass ssbsections URL has no printed collection id")
    return ident


def printed_sections(body: Any, list_url: str) -> tuple[list[dict[str, Any]], str]:
    if not isinstance(body, dict):
        raise SourceError("SSB Klass ssbsections catalog is not a JSON object")
    embedded = body.get("_embedded")
    if not isinstance(embedded, dict):
        raise SourceError("SSB Klass ssbsections catalog has no printed _embedded object")
    sections = embedded.get("ssbSections")
    if not isinstance(sections, list):
        raise SourceError("SSB Klass ssbsections catalog has no printed ssbSections array")
    listed: list[dict[str, Any]] = []
    for item in sections:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        listed.append(item)
    href = printed_self_href(body, list_url)
    return listed, href


def printed_self_href(body: dict[str, Any], list_url: str) -> str:
    links = body.get("_links")
    if isinstance(links, dict):
        self_link = links.get("self")
        if isinstance(self_link, dict):
            href = self_link.get("href")
            if isinstance(href, str) and href.strip():
                return href.strip()
    if list_url.strip():
        return list_url
    raise SourceError("SSB Klass ssbsections catalog printed no self href")


def is_ssbsec_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    path = parsed.path.rstrip("/")
    return parsed.netloc.lower() == HOST and path == PATH_PREFIX


def ssbsec_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "ssbsec"


def cells_from_ssbsec(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed Klass ssbSections names into observation cells.

    Each printed member keeps `name`. Printed `id` is null and is not
    copied. When `name` is the only printed scalar it is also copied as
    the dimension so rows stay distinct. Nested objects are not copied.
    Nothing is invented.
    """

    if not isinstance(payload, dict):
        raise ValueError("ssbsec payload is not a JSON object")
    embedded = payload.get("_embedded")
    if not isinstance(embedded, dict):
        raise ValueError("ssbsec payload has no printed _embedded object")
    sections = embedded.get("ssbSections")
    if not isinstance(sections, list):
        raise ValueError("ssbsec payload has no printed ssbSections array")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in sections:
        if isinstance(item, dict):
            cells.extend(_cells_from_record(item))
    if not cells:
        raise ValueError("ssbsec payload printed no section names")
    return cells


def _cells_from_record(item: dict[str, Any]) -> list[tuple[str, Any, dict[str, str]]]:
    scalars = {
        key: value
        for key, value in item.items()
        if _is_scalar(value) and value is not None
    }
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
    if not dims:
        dims = {measure: _as_dim(value)}
    return [(measure, value, dims)]


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _as_dim(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
