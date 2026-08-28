from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlencode, urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "ldirwms"
SOURCE_NAME = "Landbruksdirektoratet leftover WMS"
SEARCH_URL = "https://kartkatalog.geonorge.no/api/search"
SEARCH_TEXT = "Landbruksdirektoratet"
DEFAULT_MAX_ITEMS = 10
PAGE_SIZE = 50
INGEST_REASON = (
    "listed as a printed OGC:WMS service on the official Geonorge "
    f"Kartkatalog search text={SEARCH_TEXT}, capped at {DEFAULT_MAX_ITEMS}"
)
LDIRWMS_RPS = 2.0
LDIRWMS_BURST = 4
LDIR_ORG = "Landbruksdirektoratet"
WMS_PROTOCOL = "OGC:WMS"
SERVICE_TYPE = "service"
REINDRIFT_HOST = "reindrift.nibio.no"
WMS_HOST = "wms.nibio.no"
PATH_MARK = "/cgi-bin/"
NIBIOWMS_CGI = frozenset(
    (
        "ok_raster",
        "verdiklasserjordbrukogdyrkbar",
        "produksjonspotensial",
        "artsdata",
        "naturbase2",
        "gjodselsfelt_i_skog",
        "hovedplan",
        "riparian_zones",
        "urban_atlas",
        "urban_atlas_stl",
        "riparian_zones_GLE",
    )
)


class LdirwmsSource(SourceBase):
    """Replaceable ingest adapter for leftover Landbruksdirektoratet WMS.

    Listing copies printed OGC:WMS Type=service rows the official Geonorge
    Kartkatalog search for Landbruksdirektoratet prints. It skips other
    organizations, WFS, downloads, servicelayers, empty DistributionUrl,
    cgi-bin names already ingested by leftover NIBIO WMS, and
    GetCapabilities bodies that are not WMS XML. Native ids are the
    printed last cgi-bin path segment so `vernskog2` stays distinct from
    `reindrift`. Access URLs keep the printed DistributionUrl. This first
    slice stays inside that printed search and caps the walk. This is not
    Geonorge Kartkatalog REST (`--source geonorge`) and not NIBIO IPM
    weather (`--source nibio`) and not leftover NIBIO WMS
    (`--source nibiowms`).
    """

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = (SEARCH_URL,)
    ingest_reason = INGEST_REASON

    def __init__(
        self,
        *,
        search_url: str = SEARCH_URL,
        max_items: int = DEFAULT_MAX_ITEMS,
        http: HttpClient | None = None,
    ) -> None:
        self.search_url = search_url
        self.max_items = max_items
        self.http = http or HttpClient(
            limiter=RateLimiter(LDIRWMS_RPS, LDIRWMS_BURST),
            timeout=60.0,
        )
        self._listed: list[tuple[str, str, str]] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        listed = self._listed_services()
        sliced = listed[offset : offset + cap]
        refs: list[DatasetRef] = []
        for ident, href, _title in sliced:
            refs.append(
                DatasetRef(
                    source_native_uri=href,
                    source_native_id=ident,
                )
            )
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        ident, href, title = _href_for_ref(self._listed_services(), ref)
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
            "landingPage": [self.search_url],
            "ldirwms_service_id": ident,
            "ldirwms_service_href": href,
            "ldirwms_service_title": title,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ident,
            source_native_uri=href,
            fetched_from=self.search_url,
            payload=payload,
        )

    def _listed_services(self) -> list[tuple[str, str, str]]:
        if self._listed is not None:
            return self._listed
        results = _search_ldir_rows(self.http, self.search_url)
        collected = printed_wms_services(results)
        kept: list[tuple[str, str, str]] = []
        for ident, href, title in collected:
            try:
                body = self.http.get_text(href)
            except Exception:
                continue
            if not is_wms_capabilities_body(body):
                continue
            kept.append((ident, href, title))
        if not kept:
            raise SourceError(
                f"Geonorge Landbruksdirektoratet search printed no live WMS services: {self.search_url}"
            )
        self._listed = kept
        return kept


def printed_wms_services(results: Any) -> list[tuple[str, str, str]]:
    """Copy printed leftover LDIR OGC:WMS Type=service rows."""

    if not isinstance(results, list):
        raise SourceError("Geonorge Landbruksdirektoratet search has no printed Results array")
    listed: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for item in results:
        if not isinstance(item, dict):
            continue
        if not is_ldir_wms_service(item):
            continue
        href = printed_distribution_url(item)
        if href is None:
            continue
        ident = printed_service_id(href)
        if ident is None or ident in seen or ident in NIBIOWMS_CGI:
            continue
        seen.add(ident)
        title = _printed_str(item.get("Title") or item.get("NorwegianTitle")) or ident
        listed.append((ident, href, title))
    return listed


def is_ldir_wms_service(item: dict[str, Any]) -> bool:
    return (
        item.get("Organization") == LDIR_ORG
        and item.get("DistributionProtocol") == WMS_PROTOCOL
        and item.get("Type") == SERVICE_TYPE
    )


def printed_distribution_url(item: dict[str, Any]) -> str | None:
    for key in ("DistributionUrl", "DownloadUrl", "GetCapabilitiesUrl"):
        value = _printed_str(item.get(key))
        if value:
            return value
    details = item.get("DistributionDetails")
    if isinstance(details, dict):
        return _printed_str(details.get("URL"))
    return None


def printed_service_id(name: str) -> str | None:
    path = urlsplit(name).path if name else ""
    if not path:
        path = name
    segment = path.rstrip("/").split("/")[-1] if path else ""
    if not segment:
        return None
    return segment


def is_wms_capabilities_body(body: str) -> bool:
    if not isinstance(body, str) or not body.strip():
        return False
    if _is_html(body):
        return False
    return "WMS_Capabilities" in body or "WMT_MS_Capabilities" in body


def is_ldirwms_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    host = parsed.netloc.lower()
    if PATH_MARK not in parsed.path:
        return False
    if host == REINDRIFT_HOST:
        return True
    if host != WMS_HOST:
        return False
    ident = printed_service_id(parsed.path)
    return ident is not None and ident not in NIBIOWMS_CGI


def ldirwms_table_id(access_path: str) -> str:
    path = urlsplit(access_path).path.rstrip("/")
    parts = [part for part in path.split("/") if part]
    if PATH_MARK.strip("/") in parts:
        idx = parts.index(PATH_MARK.strip("/"))
        if idx + 1 < len(parts):
            return parts[idx + 1]
    ident = printed_service_id(path)
    return ident or "ldirwms"


def cells_from_ldirwms(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed WMS Layer/Name text into cells.

    Each Layer keeps printed Name text. A Title sibling, when present,
    stays as a dimension. Nested objects and other XML are not copied.
    Nothing is invented.
    """

    if not isinstance(payload, str) or not payload.strip():
        raise ValueError("ldirwms payload is empty or not WMS XML")
    if _is_html(payload):
        raise ValueError("ldirwms payload is HTML, not WMS XML")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError("ldirwms payload is not WMS XML") from exc
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for layer in root.iter():
        if _localname(layer.tag) != "Layer":
            continue
        name = None
        title = None
        for child in list(layer):
            local = _localname(child.tag)
            if local == "Name" and name is None:
                text = (child.text or "").strip()
                if text:
                    name = text
            elif local == "Title" and title is None:
                text = (child.text or "").strip()
                if text:
                    title = text
        if name is None:
            continue
        dims = {"Title": title} if title is not None else {}
        cells.append(("Name", name, dims))
    if not cells:
        raise ValueError("ldirwms payload printed no Layer Name members")
    return cells


def _search_ldir_rows(http: HttpClient, search_url: str) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    page_offset = 1
    while True:
        query = urlencode({"text": SEARCH_TEXT, "limit": PAGE_SIZE, "offset": page_offset})
        url = f"{search_url}?{query}"
        try:
            body = http.get_json(url)
        except Exception as exc:
            raise SourceError(f"Geonorge Landbruksdirektoratet search failed for {url}: {exc}") from exc
        if not isinstance(body, dict):
            raise SourceError(f"Geonorge Landbruksdirektoratet search is not a JSON object: {url}")
        results = body.get("Results")
        if not isinstance(results, list) or not results:
            break
        for item in results:
            if isinstance(item, dict):
                collected.append(item)
        page_offset += len(results)
        if len(results) < PAGE_SIZE:
            break
    if not collected:
        raise SourceError(
            f"Geonorge Landbruksdirektoratet search printed no Results: {search_url}"
        )
    return collected


def _href_for_ref(
    listed: list[tuple[str, str, str]],
    ref: DatasetRef,
) -> tuple[str, str, str]:
    for ident, href, title in listed:
        if href == ref.source_native_uri:
            return ident, href, title
        if ident == ref.source_native_id:
            return ident, href, title
    raise SourceError(
        f"Geonorge Landbruksdirektoratet search has no printed WMS matching {ref.source_native_uri}"
    )


def _printed_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _localname(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _is_html(body: str) -> bool:
    lowered = body.lstrip().lower()
    return lowered.startswith("<!doctype html") or "<html" in body.lower()
