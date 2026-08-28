from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "ssbfam"
SOURCE_NAME = "SSB Klass classification families"
LIST_URL = "https://data.ssb.no/api/klass/v1/classificationfamilies"
OPENAPI_URL = "https://data.ssb.no/api/klass/v3/api-docs"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed classification family on the official SSB Klass "
    f"classificationfamilies catalog, capped at {DEFAULT_MAX_ITEMS} families"
)
SSBFAM_RPS = 2.0
SSBFAM_BURST = 4
HOST = "data.ssb.no"
PATH_PREFIX = "/api/klass/v1/classificationfamilies"
NAME_FIELDS = ("name", "id")


class SsbfamSource(SourceBase):
    """Replaceable ingest adapter for leftover SSB Klass classification families.

    Listing copies printed family `id` values and the printed `self` href.
    It does not invent family ids. This first slice stays inside the official
    catalog GET the Klass OpenAPI names and caps the walk. This is not
    Statbank (`--source ssb`), not PxWebApi 2 (`--source ssbv2`), and not
    the Klass version fetch already on main (`/api/klass/v1/versions`).
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
            limiter=RateLimiter(SSBFAM_RPS, SSBFAM_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._listed_families()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            refs.append(
                DatasetRef(
                    source_native_uri=item["href"],
                    source_native_id=item["id"],
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident = ref.source_native_id or ssbfam_table_id(ref.source_native_uri or "")
        item = self._family_item(ident)
        href = item["href"]
        title = item["title"]
        payload = {
            "id": ident,
            "uri": href,
            "title": {"no": title},
            "description": None,
            "publisher": None,
            "license": None,
            "distribution": [
                {
                    "accessURL": [href],
                    "downloadURL": [href],
                }
            ],
            "landingPage": [self.list_url],
            "ssbfam_family": item,
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

    def _listed_families(self) -> list[dict[str, Any]]:
        if self._listed is not None:
            return self._listed
        try:
            body = self.http.get_json(self.list_url)
        except Exception as exc:
            raise SourceError(
                f"SSB Klass classificationfamilies catalog failed for {self.list_url}: {exc}"
            ) from exc
        listed = printed_families(body)
        if not listed:
            raise SourceError(
                f"SSB Klass classificationfamilies catalog printed no families: {self.list_url}"
            )
        self._listed = listed
        return listed

    def _family_item(self, ident: str) -> dict[str, Any]:
        for item in self._listed_families():
            if item["id"] == ident:
                return item
        raise SourceError(
            f"SSB Klass classificationfamilies catalog has no printed family {ident}"
        )


def printed_families(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise SourceError("SSB Klass classificationfamilies catalog is not a JSON object")
    embedded = body.get("_embedded")
    if not isinstance(embedded, dict):
        raise SourceError(
            "SSB Klass classificationfamilies catalog has no printed _embedded object"
        )
    families = embedded.get("classificationFamilies")
    if not isinstance(families, list):
        raise SourceError(
            "SSB Klass classificationfamilies catalog has no printed classificationFamilies array"
        )
    listed: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in families:
        if not isinstance(item, dict):
            continue
        ident = printed_family_id(item)
        href = printed_self_href(item)
        if ident is None or href is None:
            continue
        if ident in seen:
            continue
        seen.add(ident)
        name = item.get("name")
        count = item.get("numberOfClassifications")
        listed.append(
            {
                "id": ident,
                "title": name.strip() if isinstance(name, str) and name.strip() else ident,
                "href": href,
                "numberOfClassifications": count if isinstance(count, int) else None,
            }
        )
    return listed


def printed_family_id(item: dict[str, Any]) -> str | None:
    ident = item.get("id")
    if isinstance(ident, bool):
        return None
    if isinstance(ident, int):
        return str(ident)
    if isinstance(ident, str) and ident.strip():
        return ident.strip()
    return None


def printed_self_href(item: dict[str, Any]) -> str | None:
    links = item.get("_links")
    if not isinstance(links, dict):
        return None
    self_link = links.get("self")
    if not isinstance(self_link, dict):
        return None
    href = self_link.get("href")
    if isinstance(href, str) and href.strip():
        return href.strip()
    return None


def is_ssbfam_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    path = parsed.path.rstrip("/")
    return parsed.netloc.lower() == HOST and (
        path == PATH_PREFIX or path.startswith(f"{PATH_PREFIX}/")
    )


def ssbfam_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    if segment and segment != "classificationfamilies":
        return segment
    return "ssbfam"


def cells_from_ssbfam(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed Klass family members into observation cells.

    A family object keeps printed `classifications`. Each member keeps
    printed `name` when present, otherwise `id`. Other scalars stay as
    dimensions. Nested `_links` objects are not copied. A catalog payload
    falls back to printed `classificationFamilies` members. Nothing is
    invented.
    """

    if not isinstance(payload, dict):
        raise ValueError("ssbfam payload is not a JSON object")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    members = payload.get("classifications")
    if isinstance(members, list):
        for item in members:
            if isinstance(item, dict):
                cells.extend(_cells_from_record(item))
    if not cells:
        embedded = payload.get("_embedded")
        families = embedded.get("classificationFamilies") if isinstance(embedded, dict) else None
        if isinstance(families, list):
            for item in families:
                if isinstance(item, dict):
                    cells.extend(_cells_from_record(item))
    if not cells:
        cells.extend(_cells_from_record(payload))
    if not cells:
        raise ValueError("ssbfam payload printed no family members")
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
        return []
    dims = {key: _as_dim(other) for key, other in scalars.items() if key != measure}
    return [(measure, value, dims)]


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _as_dim(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
