from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "kvkrets"
SOURCE_NAME = "Kartverket leftover Grunnkretser WFS"
WFS_URL = (
    "https://wfs.geonorge.no/skwms1/wfs.grunnkretser?service=WFS&request=GetCapabilities"
)
LIST_URLS = (WFS_URL,)
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed leftover Kartverket Grunnkretser WFS "
    f"GetCapabilities document, capped at {DEFAULT_MAX_ITEMS}. This is not "
    "--source kvgrunn, --source kvfkb, --source kvtopo, --source kvwms, "
    "or --source geonorge"
)
KVKRETS_RPS = 2.0
KVKRETS_BURST = 4
HOST = "wfs.geonorge.no"
KEPT_ID = "wfs.grunnkretser"
ACCEPT_XML = "application/xml, text/xml, */*"


class KvkretsSource(SourceBase):
    """Replaceable ingest adapter for leftover Kartverket Grunnkretser WFS.

    Listing copies the official leftover Kartverket Grunnkretser OGC:WFS
    GetCapabilities document that Geonorge prints as Type=service.
    It skips GetCapabilities bodies that are not WFS XML. Native ids
    are the printed last path segment so `wfs.grunnkretser` stays the
    leftover Grunnkretser WFS path. Access URLs keep the printed
    GetCapabilities URL. This first slice stays inside that leftover
    document and caps the walk. This is not leftover grunnkart WMS
    (`--source kvgrunn`), not leftover FKB WMS (`--source kvfkb`),
    not leftover topo WMS (`--source kvtopo`), not leftover WMS/WMTS
    (`--source kvwms`), and not Geonorge Kartkatalog
    (`--source geonorge`).
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
            limiter=RateLimiter(KVKRETS_RPS, KVKRETS_BURST),
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
            "kvkrets_service_id": ident,
            "kvkrets_service_href": href,
            "kvkrets_service_title": title,
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
            if not is_wfs_capabilities_body(body):
                continue
            for ident, href, title in printed_services(body, url):
                if ident != KEPT_ID or ident in seen:
                    continue
                seen.add(ident)
                listed.append((ident, href, title))
        if not listed:
            raise SourceError(
                "Kartverket leftover Grunnkretser WFS printed no GetCapabilities XML: "
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
    title = printed_service_title(xml_text, ident)
    return [(ident, request_url, title)]


def printed_service_id(name: str) -> str | None:
    path = urlsplit(name).path if name else ""
    if not path:
        path = name
    segment = path.rstrip("/").split("/")[-1] if path else ""
    if not segment:
        return None
    return segment


def printed_service_title(body: str, fallback: str) -> str:
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return fallback
    for elem in root.iter():
        if _localname(elem.tag) != "ServiceIdentification":
            continue
        for child in elem:
            if _localname(child.tag) != "Title":
                continue
            text = (child.text or "").strip()
            if text:
                return text
    return fallback


def is_wfs_capabilities_body(body: str) -> bool:
    if not isinstance(body, str) or not body.strip():
        return False
    if _is_html(body):
        return False
    return "WFS_Capabilities" in body


def is_kvkrets_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    if parsed.netloc.lower() != HOST:
        return False
    return printed_service_id(parsed.path) == KEPT_ID


def kvkrets_table_id(access_path: str) -> str:
    ident = printed_service_id(access_path)
    return ident or "kvkrets"


def cells_from_kvkrets(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed WFS FeatureType/Name text into cells.

    WFS_Capabilities keeps printed FeatureType Name text. A Title
    sibling, when present, stays as a dimension. Nested objects and
    other XML are not copied. Nothing is invented.
    """

    if not isinstance(payload, str) or not payload.strip():
        raise ValueError("kvkrets payload is empty or not WFS XML")
    if _is_html(payload):
        raise ValueError("kvkrets payload is HTML, not WFS XML")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError("kvkrets payload is not WFS XML") from exc
    if _localname(root.tag) != "WFS_Capabilities":
        raise ValueError("kvkrets payload is not WFS XML")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for elem in root.iter():
        if _localname(elem.tag) != "FeatureType":
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
    if not cells:
        raise ValueError("kvkrets payload printed no FeatureType Name members")
    return cells


def _parse_capabilities(xml_text: str) -> ET.Element | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    if _localname(root.tag) != "WFS_Capabilities":
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
        "Kartverket leftover Grunnkretser WFS has no printed document "
        f"matching {ref.source_native_uri}"
    )


def _localname(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _is_html(body: str) -> bool:
    lowered = body.lstrip().lower()
    return lowered.startswith("<!doctype html") or "<html" in body.lower()
