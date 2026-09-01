from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlencode, urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "ssbgis"
SOURCE_NAME = "SSB leftover WMS"
SEARCH_URL = "https://kartkatalog.geonorge.no/api/search"
SEARCH_TEXT = "Statistisk sentralbyrå"
DEFAULT_MAX_ITEMS = 10
PAGE_SIZE = 50
INGEST_REASON = (
    "listed as a printed leftover OGC:WMS Type=service row on "
    f"the official Geonorge Kartkatalog search text={SEARCH_TEXT}, "
    f"capped at {DEFAULT_MAX_ITEMS}. This is not --source ssbv2, "
    "--source kvwms, --source kvtopo, --source kvgrunn, or "
    "--source geonorge"
)
SSBGIS_RPS = 2.0
SSBGIS_BURST = 4
SSB_ORG = "Statistisk sentralbyrå"
OGC_PROTOCOLS = frozenset({"OGC:WMS", "OGC:WFS"})
SERVICE_TYPE = "service"
SSB_HOST = "kart.ssb.no"
MAPSERVER_MARK = "/api/mapserver/"
WMS_PATH_MARK = "/wms/"
WMS_GEONORGE_HOST = "wms.geonorge.no"
SKWMS1_MARK = "/skwms1/"
GEONORGE_LEFTOVER_IDS = frozenset({"wms.arealbruk"})
SKIP_HOSTS = frozenset(
    (
        "data.ssb.no",
        "cache.kartverket.no",
        "wfs.geonorge.no",
    )
)
SKIP_GEONORGE_IDS = frozenset(
    {
        "wms.topo",
        "wmts",
        "wms.kartdata",
        "wms.fkb",
        "wms.friluftsruter2",
        "wms.fjellskygge",
        "wms.n5raster2",
        "wms.markagrensen",
        "wms.topograatone",
        "wms.norges_grunnkart",
        "wms.matrikkelkart",
    }
)
ACCEPT_XML = "application/xml, text/xml, */*"


class SsbgisSource(SourceBase):
    """Replaceable ingest adapter for leftover SSB WMS.

    Listing copies printed leftover OGC:WMS Type=service rows the official
    Geonorge Kartkatalog search for Statistisk sentralbyrå prints. It skips
    other organizations, downloads, servicelayers, leftover WFS on the same
    host, PxWebApi 2 already in ssbv2, leftover Kartverket WMS already in
    kvwms/kvtopo/kvgrunn, and GetCapabilities bodies that are not WMS XML.
    Native ids are the printed last path segment so `sentrumssoner` stays
    distinct from `wms.arealbruk`. Access URLs keep the printed
    DistributionUrl. This first slice stays inside that printed search and
    caps the walk. This is not SSB PxWebApi 2 (`--source ssbv2`).
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
            limiter=RateLimiter(SSBGIS_RPS, SSBGIS_BURST),
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
            "ssbgis_service_id": ident,
            "ssbgis_service_href": href,
            "ssbgis_service_title": title,
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
        results = _search_ssb_rows(self.http, self.search_url)
        collected = printed_leftover_services(results)
        kept: list[tuple[str, str, str]] = []
        for ident, href, title in collected:
            try:
                body = self.http.get_text(href, headers={"Accept": ACCEPT_XML})
            except Exception:
                continue
            if not is_wms_capabilities_body(body):
                continue
            kept.append((ident, href, title))
        if not kept:
            raise SourceError(
                "Geonorge Statistisk sentralbyrå search printed no leftover live "
                f"WMS services: {self.search_url}"
            )
        self._listed = kept
        return kept


def printed_leftover_services(results: Any) -> list[tuple[str, str, str]]:
    if not isinstance(results, list):
        raise SourceError(
            "Geonorge Statistisk sentralbyrå search has no printed Results array"
        )
    listed: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for item in results:
        if not isinstance(item, dict):
            continue
        if not is_ssb_ogc_service(item):
            continue
        href = printed_distribution_url(item)
        if href is None or not is_leftover_href(href):
            continue
        ident = printed_service_id(href)
        if ident is None or ident in seen:
            continue
        seen.add(ident)
        title = _printed_str(item.get("Title") or item.get("NorwegianTitle")) or ident
        listed.append((ident, href, title))
    return listed


def is_ssb_ogc_service(item: dict[str, Any]) -> bool:
    return (
        item.get("Organization") == SSB_ORG
        and item.get("DistributionProtocol") in OGC_PROTOCOLS
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
    parts = [part for part in path.strip("/").split("/") if part]
    if not parts:
        return None
    last = parts[-1]
    last_l = last.lower()
    if last_l in {"wmsserver", "wfsserver"}:
        if len(parts) >= 2 and parts[-2].lower() == "mapserver":
            if len(parts) >= 3:
                return parts[-3]
        return parts[-2] if len(parts) >= 2 else last
    if last_l in {"wms", "wfs", "ows"}:
        if len(parts) >= 2:
            return f"{parts[-2]}_{last}"
        return last
    return last


def is_leftover_href(href: str) -> bool:
    parsed = urlsplit(href)
    host = parsed.netloc.lower()
    path = parsed.path
    if host in SKIP_HOSTS:
        return False
    if host == SSB_HOST:
        return MAPSERVER_MARK in path and WMS_PATH_MARK in path
    if host == WMS_GEONORGE_HOST and SKWMS1_MARK in path:
        ident = printed_service_id(href)
        if ident in SKIP_GEONORGE_IDS:
            return False
        return ident in GEONORGE_LEFTOVER_IDS
    return False


def is_wms_capabilities_body(body: str) -> bool:
    if not isinstance(body, str) or not body.strip():
        return False
    if _is_html(body):
        return False
    return "WMS_Capabilities" in body or "WMT_MS_Capabilities" in body


def is_ssbgis_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    return is_leftover_href(access_path)


def ssbgis_table_id(access_path: str) -> str:
    ident = printed_service_id(access_path)
    return ident or "ssbgis"


def cells_from_ssbgis(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed WMS Layer/Name text into cells.

    WMS_Capabilities and WMT_MS_Capabilities keep printed Layer Name
    text. A Title sibling, when present, stays as a dimension. Nested
    objects and other XML are not copied. Nothing is invented.
    """

    if not isinstance(payload, str) or not payload.strip():
        raise ValueError("ssbgis payload is empty or not WMS XML")
    if _is_html(payload):
        raise ValueError("ssbgis payload is HTML, not WMS XML")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError("ssbgis payload is not WMS XML") from exc
    local = _localname(root.tag)
    if local not in ("WMS_Capabilities", "WMT_MS_Capabilities"):
        raise ValueError("ssbgis payload is not WMS XML")
    cells = _name_cells(root, "Layer")
    if not cells:
        raise ValueError("ssbgis payload printed no Layer Name members")
    return cells


def _search_ssb_rows(http: HttpClient, search_url: str) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    page_offset = 1
    while True:
        query = urlencode({"text": SEARCH_TEXT, "limit": PAGE_SIZE, "offset": page_offset})
        url = f"{search_url}?{query}"
        try:
            body = http.get_json(url)
        except Exception as exc:
            raise SourceError(
                f"Geonorge Statistisk sentralbyrå search failed for {url}: {exc}"
            ) from exc
        if not isinstance(body, dict):
            raise SourceError(
                f"Geonorge Statistisk sentralbyrå search is not a JSON object: {url}"
            )
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
            f"Geonorge Statistisk sentralbyrå search printed no Results: {search_url}"
        )
    return collected


def _name_cells(
    root: ET.Element,
    container: str,
) -> list[tuple[str, Any, dict[str, str]]]:
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for elem in root.iter():
        if _localname(elem.tag) != container:
            continue
        name = None
        title = None
        for child in list(elem):
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
    return cells


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
        "Geonorge Statistisk sentralbyrå search has no leftover WMS matching "
        f"{ref.source_native_uri}"
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
