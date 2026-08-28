from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "ssbver"
SOURCE_NAME = "SSB Klass Classification Versions"
LIST_URL = "https://data.ssb.no/api/klass/v1/classifications"
OPENAPI_URL = "https://data.ssb.no/api/klass/v3/api-docs"
CLASS_PATH_PREFIX = "/api/klass/v1/classifications"
VERSION_PATH_PREFIX = "/api/klass/v1/versions"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed classification version on the official Klass "
    f"classifications catalog, capped at {DEFAULT_MAX_ITEMS} versions"
)
SSBVER_RPS = 2.0
SSBVER_BURST = 4
HOST = "data.ssb.no"
NAME_FIELDS = ("name", "id")


class SsbverSource(SourceBase):
    """Replaceable ingest adapter for leftover SSB Klass versions.

    The Klass OpenAPI names GET `/api/klass/v1/versions/{id}` and does not
    print a versions collection. Listing copies printed
    `_embedded.classifications[].id` and `_links.self.href`, GETs each
    printed classification href, and copies printed `versions[].id` plus
    `versions[]._links.self.href`. Native ids are the printed version `id`
    values so `1` stays distinct from `2`. This first slice stays inside
    those printed members and caps the walk. This is not the SSB PxWeb v0
    Statbank (`--source ssb`), not PxWebApi 2 (`--source ssbv2`), not Klass
    classification families (`--source ssbfam`), not Klass sections
    (`--source ssbsec`), and not Klass classifications (`--source ssclass`).
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
            limiter=RateLimiter(SSBVER_RPS, SSBVER_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._catalog()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            ident = printed_version_id(item)
            refs.append(
                DatasetRef(
                    source_native_uri=printed_item_url(item, self.list_url),
                    source_native_id=ident,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident = ref.source_native_id or ssbver_table_id(ref.source_native_uri or "")
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
            "ssbver_version": {
                key: item[key]
                for key in item
                if key not in ("_links", "classificationItems", "correspondenceTables")
            },
            "ssbver_self_href": endpoint,
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
                f"Klass classifications catalog failed for {self.list_url}: {exc}"
            ) from exc
        classifications = printed_classifications(body)
        listed: list[dict[str, Any]] = []
        for classification in classifications:
            href = printed_classification_url(classification, self.list_url)
            try:
                detail = self.http.get_json(href)
            except Exception as exc:
                raise SourceError(
                    f"Klass classification GET failed for {href}: {exc}"
                ) from exc
            listed.extend(printed_versions(detail))
            if len(listed) >= self.max_items:
                break
        if not listed:
            raise SourceError("Klass classifications catalog printed no versions")
        self._listed = listed
        return listed

    def _catalog_item(self, ident: str) -> dict[str, Any]:
        for item in self._catalog():
            if printed_version_id(item) == ident:
                return item
        raise SourceError(f"Klass classifications catalog has no printed version {ident}")


def printed_classifications(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise SourceError("Klass classifications catalog is not a JSON object")
    embedded = body.get("_embedded")
    if not isinstance(embedded, dict):
        raise SourceError("Klass classifications catalog has no printed _embedded object")
    items = embedded.get("classifications")
    if not isinstance(items, list):
        raise SourceError(
            "Klass classifications catalog has no printed classifications array"
        )
    listed: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            printed_classification_id(item)
        except SourceError:
            continue
        listed.append(item)
    return listed


def printed_versions(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise SourceError("Klass classification is not a JSON object")
    versions = body.get("versions")
    if not isinstance(versions, list):
        return []
    listed: list[dict[str, Any]] = []
    for item in versions:
        if not isinstance(item, dict):
            continue
        try:
            printed_version_id(item)
            printed_item_url(item, LIST_URL)
        except SourceError:
            continue
        listed.append(item)
    return listed


def printed_classification_id(item: dict[str, Any]) -> str:
    ident = item.get("id")
    if isinstance(ident, bool):
        raise SourceError("Klass classification has no printed id")
    if isinstance(ident, int):
        return str(ident)
    if isinstance(ident, str) and ident.strip():
        return ident.strip()
    raise SourceError("Klass classification has no printed id")


def printed_version_id(item: dict[str, Any]) -> str:
    ident = item.get("id")
    if isinstance(ident, bool):
        raise SourceError("Klass version has no printed id")
    if isinstance(ident, int):
        return str(ident)
    if isinstance(ident, str) and ident.strip():
        return ident.strip()
    raise SourceError("Klass version has no printed id")


def printed_classification_url(item: dict[str, Any], list_url: str) -> str:
    """Copy the printed classification `_links.self.href`, or join the printed id."""

    links = item.get("_links")
    if isinstance(links, dict):
        self_link = links.get("self")
        if isinstance(self_link, dict):
            href = self_link.get("href")
            if isinstance(href, str) and href.strip():
                return href.strip()
    parts = urlsplit(list_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Klass classifications catalog URL has no printed origin")
    ident = printed_classification_id(item)
    return f"{parts.scheme}://{parts.netloc}{CLASS_PATH_PREFIX}/{ident}"


def printed_item_url(item: dict[str, Any], list_url: str) -> str:
    """Copy the printed version `_links.self.href`.

    The official Klass OpenAPI names GET `/api/klass/v1/versions/{id}` and
    prints no versions collection. Each printed version member carries
    `_links.self.href`. That href is copied. No version id is invented.
    """

    links = item.get("_links")
    if isinstance(links, dict):
        self_link = links.get("self")
        if isinstance(self_link, dict):
            href = self_link.get("href")
            if isinstance(href, str) and href.strip():
                return href.strip()
    raise SourceError("Klass version has no printed self href")


def printed_title(item: dict[str, Any], ident: str) -> dict[str, str]:
    name = item.get("name")
    if isinstance(name, str) and name.strip():
        return {"no": name.strip()}
    return {"no": ident}


def is_ssbver_url(access_path: str | None) -> bool:
    """Match the printed `/versions/{id}` integer path.

    The Klass OpenAPI prints `{id}` as an integer. That rejects leftover
    printed paths under the same host such as `/classifications` and
    `/correspondencetables/{id}`.
    """

    if not access_path:
        return False
    parsed = urlsplit(access_path)
    if parsed.netloc.lower() != HOST:
        return False
    path = parsed.path.rstrip("/")
    prefix = VERSION_PATH_PREFIX + "/"
    if not path.startswith(prefix):
        return False
    rest = path[len(prefix) :]
    return bool(rest) and "/" not in rest and rest.isdigit()


def ssbver_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "ssbver"


def cells_from_ssbver(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed Klass correspondence tables into observation cells.

    A version object keeps each printed `correspondenceTables[]` member.
    Each record keeps printed `name` when present, otherwise `id`. Other
    scalars stay as dimensions. Nested `_links`, `published`, and other
    objects are not copied. If `correspondenceTables` is absent, the
    version scalars themselves are copied. Nothing is invented.
    """

    if not isinstance(payload, dict):
        raise ValueError("ssbver payload is not a JSON object")
    tables = payload.get("correspondenceTables")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    if isinstance(tables, list):
        for item in tables:
            if isinstance(item, dict):
                cells.extend(_cells_from_record(item))
    if not cells:
        cells.extend(_cells_from_record(payload))
    if not cells:
        raise ValueError("ssbver payload printed no version members")
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
