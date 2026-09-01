from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase
from public_data_agent.sources.ldirwms import is_ldirwms_url
from public_data_agent.sources.mdirgis import is_mdirgis_url
from public_data_agent.sources.mdirwms import is_mdirwms_url
from public_data_agent.sources.miljogis import is_miljogis_url
from public_data_agent.sources.nibiowms import is_nibiowms_url

SOURCE_ID = "nordatlas"
SOURCE_NAME = "Statsforvalteren leftover Nordatlas WMS/WFS"
SEARCH_URL = "https://kartkatalog.geonorge.no/api/search"
SEARCH_TEXTS = ("Nordatlas", "Statsforvalteren")
DEFAULT_MAX_ITEMS = 10
PAGE_SIZE = 50
INGEST_REASON = (
    "listed as a printed leftover OGC:WMS or OGC:WFS Type=service "
    "GetCapabilities row on the official Geonorge Kartkatalog searches "
    "text=Nordatlas and text=Statsforvalteren, "
    f"capped at {DEFAULT_MAX_ITEMS}. This is not --source miljogis, "
    "--source mdirwms, or --source mdirgis"
)
NORDATLAS_RPS = 2.0
NORDATLAS_BURST = 4
STATS_ORG = "Statsforvalteren"
OGC_PROTOCOLS = frozenset({"OGC:WMS", "OGC:WFS"})
SERVICE_TYPE = "service"
LEFTOVER_HOSTS = frozenset({"wms.nordatlas.no", "kart.fylkesatlas.no"})
BARMARKS_HOST = "wfs.geonorge.no"
BARMARKS_MARK = "wfs.barmarksloyper"
GENERIC_LAST = frozenset({"wms", "wfs", "ows", "wms.ashx", "wfs.ashx"})
ACCEPT_XML = "application/xml, text/xml, */*"


class NordatlasSource(SourceBase):
    """Replaceable ingest adapter for leftover Statsforvalteren Nordatlas WMS/WFS.

    Listing copies printed leftover OGC:WMS and OGC:WFS Type=service
    GetCapabilities rows the official Geonorge Kartkatalog searches for
    Nordatlas and Statsforvalteren print. It skips other organizations,
    downloads, servicelayers, software, DescribeFeatureType URLs, URLs
    already owned by leftover Miljødirektoratet WMS/WFS, Miljødirektoratet
    GIS, leftover NIBIO WMS, leftover Landbruksdirektoratet WMS, and
    GetCapabilities bodies that are not WMS or WFS XML. Native ids are
    the printed service path segment, or the printed host when the last
    segment is a generic ashx/wms/wfs name, so `kart.fylkesatlas.no`
    stays distinct from `wfs.barmarksloyper`. Access URLs keep the
    printed DistributionUrl. This first slice stays inside those printed
    searches and caps the walk. This is not leftover Miljødirektoratet
    WMS/WFS (`--source mdirwms`), not leftover Miljødirektoratet ArcGIS
    WMS (`--source mdirgis`), and not Miljødirektoratet ArcGIS REST
    (`--source miljogis`).
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
            limiter=RateLimiter(NORDATLAS_RPS, NORDATLAS_BURST),
            timeout=25.0,
            max_retries=1,
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
            "nordatlas_service_id": ident,
            "nordatlas_service_href": href,
            "nordatlas_service_title": title,
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
        results = _search_stats_rows(self.http, self.search_url)
        collected = printed_leftover_services(results)
        kept: list[tuple[str, str, str]] = []
        seen_idents: set[str] = set()
        for ident, href, title in collected:
            try:
                body = self.http.get_text(href, headers={"Accept": ACCEPT_XML})
            except Exception:
                continue
            if not is_ogc_capabilities_body(body):
                continue
            if ident in seen_idents:
                continue
            seen_idents.add(ident)
            kept.append((ident, href, title))
        if not kept:
            raise SourceError(
                "Geonorge Nordatlas/Statsforvalteren search printed no leftover "
                f"live WMS/WFS GetCapabilities: {self.search_url}"
            )
        self._listed = kept
        return kept


def printed_leftover_services(results: Any) -> list[tuple[str, str, str]]:
    if not isinstance(results, list):
        raise SourceError(
            "Geonorge Nordatlas/Statsforvalteren search has no printed Results array"
        )
    listed: list[tuple[str, str, str]] = []
    seen_hrefs: set[str] = set()
    for item in results:
        if not isinstance(item, dict):
            continue
        if not is_stats_ogc_service(item):
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


def is_stats_ogc_service(item: dict[str, Any]) -> bool:
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
    parsed = urlsplit(name) if name else None
    path = parsed.path if parsed else ""
    if not path:
        path = name or ""
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
    if last_l in GENERIC_LAST:
        if len(parts) >= 2:
            return f"{parts[-2]}_{last}"
        host = (parsed.netloc if parsed else "").lower()
        if host:
            return host
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
    if (
        is_mdirwms_url(href)
        or is_miljogis_url(href)
        or is_mdirgis_url(href)
        or is_nibiowms_url(href)
        or is_ldirwms_url(href)
    ):
        return False
    parsed = urlsplit(href)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if host in LEFTOVER_HOSTS:
        return True
    return host == BARMARKS_HOST and BARMARKS_MARK in path


def is_ogc_capabilities_body(body: str) -> bool:
    if not isinstance(body, str) or not body.strip():
        return False
    if _is_html(body):
        return False
    return (
        "WMS_Capabilities" in body
        or "WMT_MS_Capabilities" in body
        or "WFS_Capabilities" in body
    )


def is_nordatlas_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    return is_leftover_href(access_path)


def nordatlas_table_id(access_path: str) -> str:
    ident = printed_service_id(access_path)
    return ident or "nordatlas"


def cells_from_nordatlas(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed WMS Layer/Name or WFS FeatureType/Name text into cells.

    WMS_Capabilities and WMT_MS_Capabilities keep printed Layer Name
    text. WFS_Capabilities keeps printed FeatureType Name text. A Title
    sibling, when present, stays as a dimension. Nested objects and
    other XML are not copied. Nothing is invented.
    """

    if not isinstance(payload, str) or not payload.strip():
        raise ValueError("nordatlas payload is empty or not WMS/WFS XML")
    if _is_html(payload):
        raise ValueError("nordatlas payload is HTML, not WMS/WFS XML")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError("nordatlas payload is not WMS/WFS XML") from exc
    local = _localname(root.tag)
    if local in ("WMS_Capabilities", "WMT_MS_Capabilities"):
        cells = _name_cells(root, "Layer")
        if not cells:
            raise ValueError("nordatlas payload printed no Layer Name members")
        return cells
    if local == "WFS_Capabilities":
        cells = _name_cells(root, "FeatureType")
        if not cells:
            raise ValueError("nordatlas payload printed no FeatureType Name members")
        return cells
    raise ValueError("nordatlas payload is not WMS/WFS XML")


def _search_stats_rows(http: HttpClient, search_url: str) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for text in SEARCH_TEXTS:
        page_offset = 1
        while True:
            query = urlencode({"text": text, "limit": PAGE_SIZE, "offset": page_offset})
            url = f"{search_url}?{query}"
            try:
                body = http.get_json(url)
            except Exception as exc:
                raise SourceError(
                    f"Geonorge Nordatlas/Statsforvalteren search failed for {url}: {exc}"
                ) from exc
            if not isinstance(body, dict):
                raise SourceError(
                    f"Geonorge Nordatlas/Statsforvalteren search is not a JSON object: {url}"
                )
            results = body.get("Results")
            if not isinstance(results, list) or not results:
                break
            for item in results:
                if not isinstance(item, dict):
                    continue
                key = _printed_str(item.get("Uuid")) or printed_distribution_url(item) or str(len(collected))
                if key in seen:
                    continue
                seen.add(key)
                collected.append(item)
            page_offset += len(results)
            if len(results) < PAGE_SIZE:
                break
    if not collected:
        raise SourceError(
            f"Geonorge Nordatlas/Statsforvalteren search printed no Results: {search_url}"
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
        f"Geonorge Nordatlas/Statsforvalteren search has no leftover WMS/WFS matching {ref.source_native_uri}"
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
