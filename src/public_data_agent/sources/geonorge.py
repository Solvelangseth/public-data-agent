from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "geonorge"
SOURCE_NAME = "Geonorge Kartkatalog"
SEARCH_URL = "https://kartkatalog.geonorge.no/api/search"
GETDATA_ROOT = "https://kartkatalog.geonorge.no/api/getdata"
DEFAULT_TEXT = "REST-API"
DEFAULT_MAX_ITEMS = 8
PAGE_SIZE = 10
INGEST_REASON = (
    "listed as Kartverket W3C:REST under the printed Geonorge Kartkatalog "
    f"search text={DEFAULT_TEXT}, capped at {DEFAULT_MAX_ITEMS} items"
)
GEONORGE_RPS = 2.0
GEONORGE_BURST = 4
KARTVERKET = "Kartverket"
REST_PROTOCOL = "W3C:REST"


class GeonorgeKartkatalogSource(SourceBase):
    """Replaceable ingest adapter for Geonorge Kartkatalog REST-API services.

    Listing uses the official Kartkatalog search API. It keeps items whose
    printed Organization is Kartverket and whose printed DistributionProtocol
    is W3C:REST. Ids and access paths are copied from the printed JSON.
    """

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = (SEARCH_URL, GETDATA_ROOT)
    ingest_reason = INGEST_REASON

    def __init__(
        self,
        *,
        search_url: str = SEARCH_URL,
        getdata_root: str = GETDATA_ROOT,
        text: str = DEFAULT_TEXT,
        max_items: int = DEFAULT_MAX_ITEMS,
        http: HttpClient | None = None,
    ) -> None:
        self.search_url = search_url
        self.getdata_root = getdata_root.rstrip("/")
        self.text = text
        self.max_items = max_items
        self.http = http or HttpClient(
            limiter=RateLimiter(GEONORGE_RPS, GEONORGE_BURST),
            timeout=60.0,
        )

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = _search_kartverket_rest(self.http, self.search_url, self.text, cap + offset)
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for item in sliced:
            native_id = printed_uuid(item)
            details = item.get("ShowDetailsUrl")
            if isinstance(details, str) and details.strip():
                native_uri = details.strip()
            else:
                native_uri = f"{self.getdata_root}/{native_id}"
            refs.append(
                DatasetRef(
                    source_native_uri=native_uri,
                    source_native_id=native_id,
                    catalog_modified=_printed_str(item.get("DateUpdated") or item.get("DateMetadataUpdated")),
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        if not ref.source_native_id:
            raise SourceError(f"Geonorge listing has no printed Uuid: {ref.source_native_uri}")
        url = f"{self.getdata_root}/{ref.source_native_id}"
        try:
            meta = self.http.get_json(url)
        except Exception as exc:
            raise SourceError(f"Kartkatalog getdata failed for {url}: {exc}") from exc
        if not isinstance(meta, dict):
            raise SourceError(f"Kartkatalog getdata is not a JSON object: {url}")
        title = _printed_str(meta.get("Title") or meta.get("NorwegianTitle")) or ref.source_native_id
        abstract = _printed_str(meta.get("Abstract"))
        organization = _printed_str(meta.get("Organization"))
        access_url = printed_distribution_url(meta)
        license_uri = printed_license_uri(meta)
        payload = {
            "id": ref.source_native_id,
            "uri": ref.source_native_uri,
            "title": {"no": title} if title else None,
            "description": {"no": abstract} if abstract else None,
            "publisher": (
                {"name": organization, "title": {"no": organization}} if organization else None
            ),
            "license": license_uri,
            "distribution": (
                [
                    {
                        "accessURL": [access_url],
                        "downloadURL": [access_url],
                    }
                ]
                if access_url
                else []
            ),
            "landingPage": [ref.source_native_uri],
            "geonorge_metadata": meta,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ref.source_native_id,
            source_native_uri=ref.source_native_uri,
            fetched_from=url,
            payload=payload,
            catalog_modified=ref.catalog_modified,
        )


def printed_uuid(item: dict[str, Any]) -> str:
    uuid = item.get("Uuid")
    if not isinstance(uuid, str) or not uuid.strip():
        raise SourceError("Kartkatalog list item has no printed Uuid")
    return uuid.strip()


def is_kartverket_rest(item: dict[str, Any]) -> bool:
    return item.get("Organization") == KARTVERKET and item.get("DistributionProtocol") == REST_PROTOCOL


def printed_distribution_url(meta: dict[str, Any]) -> str | None:
    for key in ("DistributionUrl", "DownloadUrl", "GetCapabilitiesUrl"):
        value = _printed_str(meta.get(key))
        if value:
            return value
    details = meta.get("DistributionDetails")
    if isinstance(details, dict):
        return _printed_str(details.get("URL"))
    return None


def printed_license_uri(meta: dict[str, Any]) -> str | None:
    """Copy a license URI only when the catalog printed one. Do not invent."""

    for key in ("LicenseUrl", "LicenseURI", "LicenceUrl"):
        value = _printed_str(meta.get(key))
        if value:
            return value
    return None


def _printed_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _search_kartverket_rest(
    http: HttpClient,
    search_url: str,
    text: str,
    cap: int,
) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    page_offset = 1
    while len(matched) < cap:
        query = urlencode({"text": text, "limit": PAGE_SIZE, "offset": page_offset})
        url = f"{search_url}?{query}"
        try:
            body = http.get_json(url)
        except Exception as exc:
            raise SourceError(f"Kartkatalog search failed for {url}: {exc}") from exc
        if not isinstance(body, dict):
            raise SourceError(f"Kartkatalog search is not a JSON object: {url}")
        results = body.get("Results")
        if not isinstance(results, list) or not results:
            break
        for item in results:
            if isinstance(item, dict) and is_kartverket_rest(item):
                matched.append(item)
                if len(matched) >= cap:
                    break
        page_offset += len(results)
        if len(results) < PAGE_SIZE:
            break
    return matched
