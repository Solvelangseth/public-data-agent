from __future__ import annotations

import html as html_lib
import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urljoin, urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "vegogc"
SOURCE_NAME = "Statens vegvesen leftover OGC"
LIST_URL = (
    "https://www.vegvesen.no/fag/teknologi/apne-data/"
    "et-utvalg-apne-data/ogc-karttjenester/kartlag/"
)
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed GetCapabilities href on the official leftover "
    f"Statens vegvesen OGC kartlag page, capped at {DEFAULT_MAX_ITEMS}"
)
VEGOGC_RPS = 2.0
VEGOGC_BURST = 4
HOST = "ogckart-sn1.atlas.vegvesen.no"
HREF_RE = re.compile(r'href="([^"]+)"', re.IGNORECASE)


class VegogcSource(SourceBase):
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
            limiter=RateLimiter(VEGOGC_RPS, VEGOGC_BURST),
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
            "landingPage": [self.list_url],
            "vegogc_service_id": ident,
            "vegogc_service_href": href,
            "vegogc_service_title": title,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ident,
            source_native_uri=href,
            fetched_from=self.list_url,
            payload=payload,
        )

    def _listed_services(self) -> list[tuple[str, str, str]]:
        if self._listed is not None:
            return self._listed
        try:
            page = self.http.get_text(self.list_url)
        except Exception as exc:
            raise SourceError(
                f"Statens vegvesen leftover OGC catalog failed for {self.list_url}: {exc}"
            ) from exc
        if not isinstance(page, str) or not page.strip():
            raise SourceError(
                f"Statens vegvesen leftover OGC catalog is empty: {self.list_url}"
            )
        collected = printed_getcapabilities(page, self.list_url)
        kept: list[tuple[str, str, str]] = []
        for ident, href, title in collected:
            try:
                body = self.http.get_text(href)
            except Exception:
                continue
            if not is_ogc_capabilities_body(body):
                continue
            kept.append((ident, href, title))
        if not kept:
            raise SourceError(
                "Statens vegvesen leftover OGC kartlag page printed no "
                f"GetCapabilities hrefs: {self.list_url}"
            )
        self._listed = kept
        return kept


def printed_getcapabilities(page: str, page_url: str) -> list[tuple[str, str, str]]:
    listed: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for raw in HREF_RE.findall(page):
        href = html_lib.unescape(raw).strip()
        if not href:
            continue
        printed_href = _join_href(page_url, href)
        parsed = urlsplit(printed_href)
        if parsed.netloc.lower() != HOST:
            continue
        if "request=getcapabilities" not in parsed.query.lower():
            continue
        ident = printed_service_id(printed_href)
        if ident is None or ident in seen:
            continue
        seen.add(ident)
        listed.append((ident, printed_href, ident))
    return listed


def printed_service_id(name: str) -> str | None:
    path = urlsplit(name).path if name else ""
    if not path:
        path = name
    parts = [part for part in path.strip("/").split("/") if part]
    if not parts:
        return None
    return "_".join(parts)


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


def is_vegogc_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.lower() == HOST


def vegogc_table_id(access_path: str) -> str:
    ident = printed_service_id(access_path)
    return ident or "vegogc"


def cells_from_vegogc(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    if not isinstance(payload, str) or not payload.strip():
        raise ValueError("vegogc payload is empty or not WMS/WFS XML")
    if _is_html(payload):
        raise ValueError("vegogc payload is HTML, not WMS/WFS XML")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError("vegogc payload is not WMS/WFS XML") from exc
    local = _localname(root.tag)
    if local in ("WMS_Capabilities", "WMT_MS_Capabilities"):
        cells = _name_cells(root, "Layer")
        if not cells:
            raise ValueError("vegogc payload printed no Layer Name members")
        return cells
    if local == "WFS_Capabilities":
        cells = _name_cells(root, "FeatureType")
        if not cells:
            raise ValueError("vegogc payload printed no FeatureType Name members")
        return cells
    raise ValueError("vegogc payload is not WMS/WFS XML")


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


def _join_href(page_url: str, href: str) -> str:
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("//"):
        scheme = urlsplit(page_url).scheme or "https"
        return f"{scheme}:{href}"
    if href.startswith("/"):
        return urljoin(_page_origin(page_url) + "/", href)
    base = page_url if page_url.endswith("/") else f"{page_url}/"
    return urljoin(base, href)


def _page_origin(url: str) -> str:
    parsed = urlsplit(url)
    if not parsed.scheme or not parsed.netloc:
        raise SourceError("Statens vegvesen leftover OGC catalog URL has no printed origin")
    return f"{parsed.scheme}://{parsed.netloc}"


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
        "Statens vegvesen leftover OGC kartlag page has no printed service "
        f"matching {ref.source_native_uri}"
    )


def _localname(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _is_html(body: str) -> bool:
    lowered = body.lstrip().lower()
    return lowered.startswith("<!doctype html") or "<html" in body.lower()
