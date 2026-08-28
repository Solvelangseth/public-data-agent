from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "kvwms"
SOURCE_NAME = "Kartverket WMS/WMTS"
WMS_URL = "https://wms.geonorge.no/skwms1/wms.topo?service=WMS&request=GetCapabilities"
WMTS_URL = "https://cache.kartverket.no/v1/wmts/1.0.0/WMTSCapabilities.xml"
LIST_URLS = (WMS_URL, WMTS_URL)
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as printed leftover Kartverket WMS/WMTS GetCapabilities documents, "
    f"capped at {DEFAULT_MAX_ITEMS}. This is not --source geonorge, "
    "--source hoydedata, --source hoydegis, --source ogccoverages, "
    "--source transformering"
)
KVWMS_RPS = 2.0
KVWMS_BURST = 4
ACCEPT_XML = "application/xml, text/xml, */*"
WMS_HOST = "wms.geonorge.no"
WMS_PATH_MARK = "/skwms1/"
WMTS_HOST = "cache.kartverket.no"
WMTS_PATH_MARK = "/wmts"
CAPABILITIES_ROOTS = {"WMS_Capabilities", "Capabilities"}


class KvwmsSource(SourceBase):
    """Replaceable ingest adapter for leftover Kartverket WMS/WMTS GetCapabilities.

    Listing copies the two official leftover GetCapabilities documents.
    Each document is one dataset. It skips a document that is not XML
    capabilities. Native ids are the printed last path segment of the
    service href so `wms.topo` stays distinct from `wmts`. Access URLs
    keep the GetCapabilities URL. This first slice stays inside those
    two documents and caps the walk. This is not Geonorge Kartkatalog
    (`--source geonorge`), not Kartverket Høydedata
    (`--source hoydedata`), not Kartverket Høydedata GIS
    (`--source hoydegis`), not Kartverket OGC API Coverages
    (`--source ogccoverages`), and not Kartverket Transformering
    (`--source transformering`).
    """

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = LIST_URLS
    ingest_reason = INGEST_REASON

    def __init__(
        self,
        *,
        list_urls: tuple[str, ...] = LIST_URLS,
        max_items: int = DEFAULT_MAX_ITEMS,
        http: HttpClient | None = None,
    ) -> None:
        self.list_urls = list_urls
        self.max_items = max_items
        self.http = http or HttpClient(
            limiter=RateLimiter(KVWMS_RPS, KVWMS_BURST),
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
            "title": {"en": title},
            "description": None,
            "publisher": None,
            "license": None,
            "distribution": [
                {
                    "accessURL": [href],
                    "downloadURL": [href],
                }
            ],
            "landingPage": [href],
            "kvwms_service_id": ident,
            "kvwms_service_href": href,
            "kvwms_service_title": title,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ident,
            source_native_uri=href,
            fetched_from=href,
            payload=payload,
        )

    def _listed_services(self) -> list[tuple[str, str, str]]:
        if self._listed is not None:
            return self._listed
        listed: list[tuple[str, str, str]] = []
        for url in self.list_urls:
            try:
                body = self.http.get_text(url, headers={"Accept": ACCEPT_XML})
            except Exception as exc:
                raise SourceError(
                    f"Kartverket WMS/WMTS GetCapabilities failed for {url}: {exc}"
                ) from exc
            printed = printed_services(body, url)
            if not printed:
                raise SourceError(
                    f"Kartverket WMS/WMTS GetCapabilities printed no id: {url}"
                )
            listed.extend(printed)
        self._listed = listed
        return listed


def printed_services(xml_text: str, request_url: str) -> list[tuple[str, str, str]]:
    """Copy the printed native id and title from one GetCapabilities document."""

    root = _parse_capabilities(xml_text)
    if root is None:
        return []
    ident, title = _printed_id_and_title(root, request_url)
    if not ident:
        return []
    if not title:
        title = ident
    return [(ident, request_url, title)]


def is_kvwms_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    host = parsed.netloc.lower()
    path = parsed.path
    if host == WMS_HOST and WMS_PATH_MARK in path:
        return kvwms_table_id(access_path) == "wms.topo"
    if host == WMTS_HOST and WMTS_PATH_MARK in path:
        return True
    return False


def kvwms_table_id(access_path: str) -> str:
    path = urlsplit(access_path).path.rstrip("/")
    parts = [part for part in path.split("/") if part]
    if not parts:
        return "kvwms"
    last = parts[-1]
    if last == "WMTSCapabilities.xml":
        return "wmts"
    return last


def cells_from_kvwms(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed GetCapabilities layer names into cells.

    WMS keeps every Layer with a non-empty Name. WMTS keeps every Layer
    with a non-empty Identifier. Title stays a dimension when printed.
    Empty names are skipped. Nothing is invented.
    """

    if not isinstance(payload, str):
        raise ValueError("kvwms payload is not XML")
    root = _parse_capabilities(payload)
    if root is None:
        raise ValueError("kvwms payload is not XML")
    kind = _local(root.tag)
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for layer in _iter_local(root, "Layer"):
        if kind == "WMS_Capabilities":
            value = _direct_text(layer, "Name")
            measure = "Name"
        else:
            value = _direct_text(layer, "Identifier")
            measure = "Identifier"
        if not value:
            continue
        dims: dict[str, str] = {}
        title = _direct_text(layer, "Title")
        if title:
            dims["Title"] = title
        cells.append((measure, value, dims))
    if not cells:
        raise ValueError("kvwms payload printed no named layers")
    return cells


def _parse_capabilities(xml_text: str) -> ET.Element | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    if _local(root.tag) not in CAPABILITIES_ROOTS:
        return None
    return root


def _printed_id_and_title(root: ET.Element, request_url: str) -> tuple[str, str]:
    if _local(root.tag) == "WMS_Capabilities":
        href = _wms_online_href(root)
        title = _first_child_text(_first_local(root, "Service"), "Title")
    else:
        href = _wmts_getcapabilities_href(root)
        title = _first_child_text(_first_local(root, "ServiceIdentification"), "Title")
    ident = _last_path_segment(href) or _last_path_segment(request_url)
    return ident, title


def _wms_online_href(root: ET.Element) -> str:
    service = _first_local(root, "Service")
    if service is None:
        return ""
    online = _first_local(service, "OnlineResource")
    if online is None:
        return ""
    return _attr_local(online, "href")


def _wmts_getcapabilities_href(root: ET.Element) -> str:
    for operation in _iter_local(root, "Operation"):
        if _attr_local(operation, "name") != "GetCapabilities":
            continue
        for getter in _iter_local(operation, "Get"):
            href = _attr_local(getter, "href")
            if href:
                return href
    return ""


def _last_path_segment(url: str) -> str:
    if not url:
        return ""
    parts = [part for part in urlsplit(url).path.split("/") if part]
    return parts[-1] if parts else ""


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _attr_local(elem: ET.Element, name: str) -> str:
    for key, value in elem.attrib.items():
        if _local(key) == name and isinstance(value, str):
            return value.strip()
    return ""


def _direct_text(elem: ET.Element, name: str) -> str:
    for child in elem:
        if _local(child.tag) == name:
            text = (child.text or "").strip()
            if text:
                return text
    return ""


def _first_child_text(elem: ET.Element | None, name: str) -> str:
    if elem is None:
        return ""
    return _direct_text(elem, name)


def _first_local(elem: ET.Element, name: str) -> ET.Element | None:
    for child in elem:
        if _local(child.tag) == name:
            return child
    return None


def _iter_local(elem: ET.Element, name: str):
    for child in elem.iter():
        if _local(child.tag) == name:
            yield child


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
        f"Kartverket WMS/WMTS has no printed document matching {ref.source_native_uri}"
    )
