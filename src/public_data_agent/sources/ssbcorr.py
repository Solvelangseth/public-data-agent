from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "ssbcorr"
SOURCE_NAME = "SSB Klass Correspondence Tables"
LIST_URL = "https://data.ssb.no/api/klass/v1/classifications"
OPENAPI_URL = "https://data.ssb.no/api/klass/v3/api-docs"
TABLE_PATH_PREFIX = "/api/klass/v1/correspondencetables"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed correspondence table on official Klass versions, "
    f"capped at {DEFAULT_MAX_ITEMS} tables"
)
SSBCORR_RPS = 2.0
SSBCORR_BURST = 4
HOST = "data.ssb.no"
NAME_FIELDS = ("sourceName", "targetName", "name", "id")


class SsbcorrSource(SourceBase):
    """Leftover Klass correspondence tables.

    The Klass OpenAPI names GET `/api/klass/v1/correspondencetables/{id}`
    and does not print a correspondence-tables collection. Listing copies
    printed `correspondenceTables[].id` and `_links.self.href` from official
    version payloads reached through the classifications catalog.
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
            limiter=RateLimiter(SSBCORR_RPS, SSBCORR_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._catalog()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            ident = printed_table_id(item)
            refs.append(
                DatasetRef(
                    source_native_uri=printed_item_url(item, self.list_url),
                    source_native_id=ident,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident = ref.source_native_id or ssbcorr_table_id(ref.source_native_uri or "")
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
            "ssbcorr_correspondencetable": {
                key: item[key]
                for key in item
                if key not in ("_links", "correspondenceMaps", "changelogs")
            },
            "ssbcorr_self_href": endpoint,
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
        seen: set[str] = set()
        for classification in classifications:
            href = printed_classification_url(classification, self.list_url)
            try:
                detail = self.http.get_json(href)
            except Exception as exc:
                raise SourceError(
                    f"Klass classification GET failed for {href}: {exc}"
                ) from exc
            for version in printed_versions(detail):
                version_href = printed_version_url(version)
                try:
                    version_body = self.http.get_json(version_href)
                except Exception as exc:
                    raise SourceError(
                        f"Klass version GET failed for {version_href}: {exc}"
                    ) from exc
                for table in printed_correspondence_tables(version_body):
                    ident = printed_table_id(table)
                    if ident in seen:
                        continue
                    seen.add(ident)
                    listed.append(table)
                    if len(listed) >= self.max_items:
                        break
                if len(listed) >= self.max_items:
                    break
            if len(listed) >= self.max_items:
                break
        if not listed:
            raise SourceError("Klass versions printed no correspondence tables")
        self._listed = listed
        return listed

    def _catalog_item(self, ident: str) -> dict[str, Any]:
        for item in self._catalog():
            if printed_table_id(item) == ident:
                return item
        raise SourceError(
            f"Klass versions have no printed correspondence table {ident}"
        )


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
            printed_classification_url(item, LIST_URL)
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
            printed_version_url(item)
        except SourceError:
            continue
        listed.append(item)
    return listed


def printed_correspondence_tables(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise SourceError("Klass version is not a JSON object")
    tables = body.get("correspondenceTables")
    if not isinstance(tables, list):
        return []
    listed: list[dict[str, Any]] = []
    for item in tables:
        if not isinstance(item, dict):
            continue
        try:
            printed_table_id(item)
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


def printed_table_id(item: dict[str, Any]) -> str:
    ident = item.get("id")
    if isinstance(ident, bool):
        raise SourceError("Klass correspondence table has no printed id")
    if isinstance(ident, int):
        return str(ident)
    if isinstance(ident, str) and ident.strip():
        return ident.strip()
    raise SourceError("Klass correspondence table has no printed id")


def printed_classification_url(item: dict[str, Any], list_url: str) -> str:
    href = _printed_self_href(item)
    if href is None:
        raise SourceError("Klass classification has no printed self href")
    return href


def printed_version_url(item: dict[str, Any]) -> str:
    href = _printed_self_href(item)
    if href is None:
        raise SourceError("Klass version has no printed self href")
    return href


def printed_item_url(item: dict[str, Any], list_url: str) -> str:
    href = _printed_self_href(item)
    if href is None:
        raise SourceError("Klass correspondence table has no printed self href")
    return href


def _printed_self_href(item: dict[str, Any]) -> str | None:
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


def printed_title(item: dict[str, Any], ident: str) -> dict[str, str]:
    name = item.get("name")
    if isinstance(name, str) and name.strip():
        return {"no": name.strip()}
    return {"no": ident}


def is_ssbcorr_url(access_path: str | None) -> bool:
    """Match `/correspondencetables/{id}` where the Klass OpenAPI prints `{id}` as an integer."""

    if not access_path:
        return False
    parsed = urlsplit(access_path)
    if parsed.netloc.lower() != HOST:
        return False
    path = parsed.path.rstrip("/")
    prefix = TABLE_PATH_PREFIX + "/"
    if not path.startswith(prefix):
        return False
    rest = path[len(prefix) :]
    return bool(rest) and "/" not in rest and rest.isdigit()


def ssbcorr_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "ssbcorr"


def cells_from_ssbcorr(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    if not isinstance(payload, dict):
        raise ValueError("ssbcorr payload is not a JSON object")
    maps = payload.get("correspondenceMaps")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    if isinstance(maps, list):
        for item in maps:
            if isinstance(item, dict):
                cells.extend(_cells_from_record(item))
    if not cells:
        cells.extend(_cells_from_record(payload))
    if not cells:
        raise ValueError("ssbcorr payload printed no correspondence-table members")
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
