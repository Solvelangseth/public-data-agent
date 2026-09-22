from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "trondheim"
SOURCE_NAME = "Trondheim kommune Åpne Data"
LIST_URL = "https://data.trondheim.kommune.no/api/v3/datasets/export.json"
DATASET_PATH_PREFIX = "/api/v3/dataset/"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a dataset on the official Trondheim Åpne Data export list, "
    f"capped at {DEFAULT_MAX_ITEMS} datasets"
)
TRONDHEIM_RPS = 2.0
TRONDHEIM_BURST = 4
HOST = "data.trondheim.kommune.no"
NAME_FIELDS = ("title", "name", "filename", "id")


class TrondheimOpenDataSource(SourceBase):
    """Replaceable ingest adapter for Trondheim kommune Åpne Data.

    Listing copies dataset ids the official export.json list prints. It does
    not invent ids. Native ids are the printed catalog `id` values. access_path
    is the printed `/api/v3/dataset/:id` URL the catalog documents. This first
    slice stays inside that list and caps the walk.

    Retired upstream, checked 2026-09-21: `data.trondheim.kommune.no` is a
    CNAME to `trondheim.datapress.io` whose custom hostname is gone. HTTPS
    fails the TLS handshake (alert 40) for curl and OpenSSL alike, plain HTTP
    answers 409, and the DataPress host itself answers 404 "There's no site at
    this address". Nothing here is broken, so the adapter is kept as written
    against the documented API in case the portal returns. Three Trondheim
    kommune datasets reach the registry through data.norge meanwhile.
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
            limiter=RateLimiter(TRONDHEIM_RPS, TRONDHEIM_BURST),
            timeout=60.0,
        )
        self._listed: list[dict[str, Any]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._catalog()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            ident = printed_dataset_id(item)
            refs.append(
                DatasetRef(
                    source_native_uri=printed_dataset_url(ident, self.list_url),
                    source_native_id=ident,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident = ref.source_native_id or trondheim_table_id(ref.source_native_uri or "")
        item = self._catalog_item(ident)
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            title = ident
        description = item.get("description")
        webpage = item.get("webpage")
        endpoint = printed_dataset_url(ident, self.list_url)
        payload = {
            "id": ident,
            "uri": endpoint,
            "title": {"no": title},
            "description": (
                {"no": description} if isinstance(description, str) and description.strip() else None
            ),
            "publisher": None,
            "license": printed_license_url(item),
            "distribution": [
                {
                    "accessURL": [endpoint],
                    "downloadURL": [endpoint],
                }
            ],
            "landingPage": (
                [webpage] if isinstance(webpage, str) and webpage.strip() else [self.list_url]
            ),
            "trondheim_catalog_item": item,
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
                f"Trondheim Åpne Data list failed for {self.list_url}: {exc}"
            ) from exc
        listed = printed_datasets(body)
        if not listed:
            raise SourceError("Trondheim Åpne Data export printed no datasets")
        self._listed = listed
        return listed

    def _catalog_item(self, ident: str) -> dict[str, Any]:
        for item in self._catalog():
            if printed_dataset_id(item) == ident:
                return item
        raise SourceError(f"Trondheim Åpne Data export has no printed dataset {ident}")


def printed_datasets(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, list):
        raise SourceError("Trondheim Åpne Data export is not a JSON array")
    listed: list[dict[str, Any]] = []
    for item in body:
        if not isinstance(item, dict):
            continue
        ident = item.get("id")
        if not isinstance(ident, str) or not ident.strip():
            continue
        listed.append(item)
    return listed


def printed_dataset_id(item: dict[str, Any]) -> str:
    ident = item.get("id")
    if not isinstance(ident, str) or not ident.strip():
        raise SourceError("Trondheim Åpne Data catalog item has no printed id")
    return ident.strip()


def printed_dataset_url(ident: str, list_url: str) -> str:
    """Join a printed catalog id to the documented /api/v3/dataset/:id path.

    The live catalog's deprecated CKAN help route prints
    `/api/v3/datasets/export.json` and `/api/v3/dataset/:id`. The origin is
    copied from the list URL. No dataset id is invented.
    """

    parts = urlsplit(list_url)
    if not parts.scheme or not parts.netloc:
        raise SourceError("Trondheim Åpne Data list URL has no printed origin")
    suffix = ident if ident.startswith("/") else ident
    return f"{parts.scheme}://{parts.netloc}{DATASET_PATH_PREFIX}{suffix}"


def printed_license_url(item: dict[str, Any]) -> str | None:
    licence = item.get("licence")
    if not isinstance(licence, dict):
        return None
    url = licence.get("url")
    if isinstance(url, str) and url.strip():
        return url.strip()
    return None


def is_trondheim_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.lower() == HOST and parsed.path.startswith(DATASET_PATH_PREFIX)


def trondheim_table_id(access_path: str) -> str:
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or "trondheim"


def cells_from_trondheim(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed Trondheim dataset resources and links into observation cells.

    The dataset API prints `resources` and `links` as objects or arrays.
    Nested QA blobs are not copied. Geometry and file bytes are not fetched.
    """

    if not isinstance(payload, dict):
        raise ValueError("trondheim payload is not a JSON object")
    records = _records(payload)
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for item in records:
        cells.extend(_cells_from_record(item))
    if not cells:
        raise ValueError("trondheim payload printed no resources or links")
    return cells


def _records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    records.extend(_named_entries(payload.get("resources")))
    records.extend(_named_entries(payload.get("links")))
    return records


def _named_entries(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        records: list[dict[str, Any]] = []
        for key, item in value.items():
            if not isinstance(item, dict):
                continue
            record = dict(item)
            if "id" not in record and isinstance(key, str):
                record["id"] = key
            records.append(record)
        return records
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _cells_from_record(item: dict[str, Any]) -> list[tuple[str, Any, dict[str, str]]]:
    scalars = {key: value for key, value in item.items() if _is_scalar(value)}
    if not scalars:
        return []
    measure = None
    value: Any = None
    for field in NAME_FIELDS:
        if field in scalars:
            measure = field
            value = scalars[field]
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
