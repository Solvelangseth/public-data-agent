from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "ssbfritid"
SOURCE_NAME = "SSB leftover Fritidsbyggområder WMS"
FRITID_URL = (
    "https://kart.ssb.no/api/mapserver/v1/wms/fritidsbyggomraader"
    "?service=WMS&version=1.3.0&request=GetCapabilities"
)
LIST_URLS = (FRITID_URL,)
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed leftover SSB Fritidsbyggområder WMS "
    "GetCapabilities document, capped at "
    f"{DEFAULT_MAX_ITEMS}. This is not --source ssbgis, "
    "--source ssbv2, or --source geonorge"
)
SSBFRITID_RPS = 2.0
SSBFRITID_BURST = 4
HOST = "kart.ssb.no"
KEPT_ID = "fritidsbyggomraader"
ACCEPT_XML = "application/xml, text/xml, */*"


class SsbfritidSource(SourceBase):
    """Replaceable ingest adapter for leftover SSB Fritidsbyggområder WMS.

    Listing copies the official leftover SSB Fritidsbyggområder OGC:WMS
    GetCapabilities document that Geonorge prints as Type=service.
    It skips GetCapabilities bodies that are not WMS XML. Native ids
    are the printed last path segment so `fritidsbyggomraader` stays
    the leftover Fritidsbyggområder WMS path. Access URLs keep the
    printed GetCapabilities URL. This first slice stays inside that
    leftover document and caps the walk. This is not leftover SSB WMS
    (`--source ssbgis`), not SSB PxWebApi 2 (`--source ssbv2`), and
    not Geonorge Kartkatalog (`--source geonorge`).
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
            limiter=RateLimiter(SSBFRITID_RPS, SSBFRITID_BURST),
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
            "landingPage": [href],
            "ssbfritid_service_id": ident,
            "ssbfritid_service_href": href,
            "ssbfritid_service_title": title,
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
        seen: set[str] = set()
        for url in self.list_urls:
            try:
                body = self.http.get_text(url, headers={"Accept": ACCEPT_XML})
            except Exception:
                continue
            if not is_wms_capabilities_body(body):
                continue
            for ident, href, title in printed_services(body, url):
                if ident != KEPT_ID or ident in seen:
                    continue
                seen.add(ident)
                listed.append((ident, href, title))
        if not listed:
            raise SourceError(
                "SSB leftover Fritidsbyggområder WMS printed no GetCapabilities XML: "
                + ", ".join(self.list_urls)
            )
        self._listed = listed
        return listed


def printed_services(xml_text: str, request_url: str) -> list[tuple[str, str, str]]:
    root = _parse_capabilities(xml_text)
    if root is None:
        return []
    ident = printed_service_id(request_url)
    if ident is None:
        return []
    title = _first_child_text(_first_local(root, "Service"), "Title") or ident
    return [(ident, request_url, title)]


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


def is_ssbfritid_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    if parsed.netloc.lower() != HOST:
        return False
    return printed_service_id(parsed.path) == KEPT_ID


def ssbfritid_table_id(access_path: str) -> str:
    ident = printed_service_id(access_path)
    return ident or "ssbfritid"


def cells_from_ssbfritid(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed WMS Layer/Name text into cells.

    WMS_Capabilities and WMT_MS_Capabilities keep printed Layer Name
    text. A Title sibling, when present, stays as a dimension. Nested
    objects and other XML are not copied. Nothing is invented.
    """

    if not isinstance(payload, str) or not payload.strip():
        raise ValueError("ssbfritid payload is empty or not WMS XML")
    if _is_html(payload):
        raise ValueError("ssbfritid payload is HTML, not WMS XML")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError("ssbfritid payload is not WMS XML") from exc
    if _localname(root.tag) not in {"WMS_Capabilities", "WMT_MS_Capabilities"}:
        raise ValueError("ssbfritid payload is not WMS XML")
    cells = _name_cells(root, "Layer")
    if not cells:
        raise ValueError("ssbfritid payload printed no Layer Name members")
    return cells


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


def _parse_capabilities(xml_text: str) -> ET.Element | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    if _localname(root.tag) not in {"WMS_Capabilities", "WMT_MS_Capabilities"}:
        return None
    return root


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
        "SSB leftover Fritidsbyggområder WMS has no printed document matching "
        f"{ref.source_native_uri}"
    )


def _first_child_text(elem: ET.Element | None, name: str) -> str:
    if elem is None:
        return ""
    for child in elem:
        if _localname(child.tag) == name:
            text = (child.text or "").strip()
            if text:
                return text
    return ""


def _first_local(elem: ET.Element, name: str) -> ET.Element | None:
    for child in elem:
        if _localname(child.tag) == name:
            return child
    return None


def _localname(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _is_html(body: str) -> bool:
    lowered = body.lstrip().lower()
    return lowered.startswith("<!doctype html") or "<html" in body.lower()
