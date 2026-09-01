from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "barmark"
SOURCE_NAME = "Statsforvalteren leftover Barmarksløyper WFS"
SEARCH_URL = "https://kartkatalog.geonorge.no/api/search"
SEARCH_TEXT = "Barmarksløyper"
DEFAULT_MAX_ITEMS = 10
PAGE_SIZE = 50
INGEST_REASON = (
    "listed as a printed leftover OGC:WFS Type=service GetCapabilities "
    f"row on the official Geonorge Kartkatalog search text={SEARCH_TEXT}, "
    f"capped at {DEFAULT_MAX_ITEMS}. This is not --source nordatlas, "
    "--source fbgis, --source nibiowms, or --source nibiorest"
)
BARMARK_RPS = 2.0
BARMARK_BURST = 4
STATS_ORG = "Statsforvalteren"
OGC_PROTOCOLS = frozenset({"OGC:WFS"})
SERVICE_TYPE = "service"
LEFTOVER_HOST = "wfs.geonorge.no"
LEFTOVER_MARK = "wfs.barmarksloyper"
SKIP_HOSTS = frozenset({"wms.nordatlas.no", "kart.fylkesatlas.no"})
ACCEPT_XML = "application/xml, text/xml, */*"


class BarmarkSource(SourceBase):
    """Replaceable ingest adapter for leftover Statsforvalteren Barmarksløyper WFS.

    Listing copies printed leftover OGC:WFS Type=service GetCapabilities
    rows the official Geonorge Kartkatalog search for Barmarksløyper
    prints. It skips other organizations, downloads, servicelayers,
    software, DescribeFeatureType URLs, Nordatlas WMS hosts, Fylkesatlas
    WMS, the dead Nordatlas wfs.ashx endpoint, leftover NIBIO WMS/REST,
    leftover Forsvarsbygg GIS, and GetCapabilities bodies that are not
    WFS XML. Native ids are the printed last path segment so
    `wfs.barmarksloyper` stays distinct from `kart.fylkesatlas.no`.
    Access URLs keep the printed DistributionUrl. This first slice stays
    inside that printed search and caps the walk. This is not leftover
    Nordatlas WMS/WFS (`--source nordatlas`) and not leftover
    Forsvarsbygg WMS/WFS (`--source fbgis`).
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
            limiter=RateLimiter(BARMARK_RPS, BARMARK_BURST),
            timeout=60.0,
            max_retries=2,
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
            "barmark_service_id": ident,
            "barmark_service_href": href,
            "barmark_service_title": title,
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
        results = _search_barmark_rows(self.http, self.search_url)
        collected = printed_leftover_services(results)
        kept: list[tuple[str, str, str]] = []
        seen_idents: set[str] = set()
        for ident, href, title in collected:
            if len(kept) >= self.max_items:
                break
            try:
                body = self.http.get_text(href, headers={"Accept": ACCEPT_XML})
            except Exception:
                continue
            if not is_wfs_capabilities_body(body):
                continue
            if ident in seen_idents:
                continue
            seen_idents.add(ident)
            kept.append((ident, href, title))
        if not kept:
            raise SourceError(
                "Geonorge Barmarksløyper search printed no leftover live "
                f"WFS GetCapabilities: {self.search_url}"
            )
        self._listed = kept
        return kept


def printed_leftover_services(results: Any) -> list[tuple[str, str, str]]:
    if not isinstance(results, list):
        raise SourceError("Geonorge Barmarksløyper search has no printed Results array")
    listed: list[tuple[str, str, str]] = []
    seen_hrefs: set[str] = set()
    for item in results:
        if not isinstance(item, dict):
            continue
        if not is_stats_wfs_service(item):
            continue
        href = printed_distribution_url(item)
        if href is None or not is_leftover_href(href):
            continue
        if not is_getcapabilities_url(href):
            continue
        if href in seen_hrefs:
            continue
        ident = printed_service_id(href)
        if ident is None:
            continue
        seen_hrefs.add(href)
        title = _printed_str(item.get("Title") or item.get("NorwegianTitle")) or ident
        listed.append((ident, href, title))
    return listed


def is_stats_wfs_service(item: dict[str, Any]) -> bool:
    return (
        item.get("Organization") == STATS_ORG
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
    if last_l in {"wms", "wfs", "ows", "wms.ashx", "wfs.ashx"}:
        if len(parts) >= 2:
            return f"{parts[-2]}_{last}"
        return last
    return last


def is_getcapabilities_url(href: str) -> bool:
    query = parse_qs(urlsplit(href).query, keep_blank_values=True)
    for key, values in query.items():
        if key.lower() != "request":
            continue
        return any(value.lower() == "getcapabilities" for value in values)
    return False


def is_leftover_href(href: str) -> bool:
    parsed = urlsplit(href)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if host in SKIP_HOSTS:
        return False
    if host != LEFTOVER_HOST:
        return False
    return LEFTOVER_MARK in path


def is_wfs_capabilities_body(body: str) -> bool:
    if not isinstance(body, str) or not body.strip():
        return False
    if _is_html(body):
        return False
    return "WFS_Capabilities" in body


def is_barmark_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    return is_leftover_href(access_path)


def barmark_table_id(access_path: str) -> str:
    ident = printed_service_id(access_path)
    return ident or "barmark"


def cells_from_barmark(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed WFS FeatureType/Name text into cells.

    WFS_Capabilities keeps printed FeatureType Name text. A Title
    sibling, when present, stays as a dimension. Nested objects and
    other XML are not copied. Nothing is invented.
    """

    if not isinstance(payload, str) or not payload.strip():
        raise ValueError("barmark payload is empty or not WFS XML")
    if _is_html(payload):
        raise ValueError("barmark payload is HTML, not WFS XML")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError("barmark payload is not WFS XML") from exc
    if _localname(root.tag) != "WFS_Capabilities":
        raise ValueError("barmark payload is not WFS XML")
    cells = _name_cells(root, "FeatureType")
    if not cells:
        raise ValueError("barmark payload printed no FeatureType Name members")
    return cells


def _search_barmark_rows(http: HttpClient, search_url: str) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    page_offset = 1
    while True:
        query = urlencode({"text": SEARCH_TEXT, "limit": PAGE_SIZE, "offset": page_offset})
        url = f"{search_url}?{query}"
        try:
            body = http.get_json(url)
        except Exception as exc:
            raise SourceError(
                f"Geonorge Barmarksløyper search failed for {url}: {exc}"
            ) from exc
        if not isinstance(body, dict):
            raise SourceError(
                f"Geonorge Barmarksløyper search is not a JSON object: {url}"
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
            f"Geonorge Barmarksløyper search printed no Results: {search_url}"
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
        "Geonorge Barmarksløyper search has no leftover WFS "
        f"matching {ref.source_native_uri}"
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
