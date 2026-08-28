from __future__ import annotations

import html as html_lib
import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urljoin, urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "nguwms"
SOURCE_NAME = "NGU leftover WMS"
LIST_URL = "https://www.ngu.no/taxonomy/term/36"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed GetCapabilities URL on the official leftover "
    f"NGU WMS pages, capped at {DEFAULT_MAX_ITEMS}. This is not --source ngu"
)
NGUWMS_RPS = 2.0
NGUWMS_BURST = 4
HOST = "geo.ngu.no"
PATH_MARK = "/mapserver/"
# HttpClient.get_text defaults Accept to application/json.
ACCEPT_XML = "application/xml, text/xml, */*"
HREF_RE = re.compile(r'href="([^"]+)"', re.IGNORECASE)
GETCAP_RE = re.compile(
    r"https://geo\.ngu\.no/mapserver/[^\s\"'<>]+",
    re.IGNORECASE,
)


class NguwmsSource(SourceBase):
    """Replaceable ingest adapter for leftover NGU WMS.

    Listing copies printed GetCapabilities URLs the official leftover
    NGU WMS pages print. It skips URLs without request=GetCapabilities,
    hosts other than geo.ngu.no, paths outside /mapserver/, /api/features,
    /kart/ viewers, and GetCapabilities bodies that are HTML or not WMS
    XML. Native ids are the printed last /mapserver/ path segment so
    LosmasserWMS3 stays distinct from BerggrunnWMS3. Access URLs keep
    the printed href. This first slice stays inside those leftover pages
    and caps the walk. This is not NGU OGC Features (`--source ngu`).
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
            limiter=RateLimiter(NGUWMS_RPS, NGUWMS_BURST),
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
            "nguwms_service_id": ident,
            "nguwms_service_href": href,
            "nguwms_service_title": title,
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
                f"NGU leftover WMS catalog failed for {self.list_url}: {exc}"
            ) from exc
        if not isinstance(page, str) or not page.strip():
            raise SourceError(f"NGU leftover WMS catalog is empty: {self.list_url}")
        collected: list[tuple[str, str, str]] = []
        seen: set[str] = set()
        for ident, href, title in printed_getcapabilities(page):
            if ident in seen:
                continue
            seen.add(ident)
            collected.append((ident, href, title))
        for pager_url in printed_pager_urls(page, self.list_url):
            try:
                child_page = self.http.get_text(pager_url)
            except Exception:
                continue
            if not isinstance(child_page, str) or not child_page.strip():
                continue
            for ident, href, title in printed_getcapabilities(child_page):
                if ident in seen:
                    continue
                seen.add(ident)
                collected.append((ident, href, title))
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
                f"NGU leftover WMS pages printed no GetCapabilities URLs: {self.list_url}"
            )
        self._listed = kept
        return kept


def printed_pager_urls(page: str, list_url: str) -> list[str]:
    """Copy printed leftover pager hrefs on taxonomy/term/36."""

    parent_path = urlsplit(list_url).path.rstrip("/")
    listed: list[str] = []
    seen: set[str] = set()
    for raw in HREF_RE.findall(page):
        href = html_lib.unescape(raw).strip()
        if not href:
            continue
        joined = _join_href(list_url, href)
        parsed = urlsplit(joined)
        if parsed.path.rstrip("/") != parent_path:
            continue
        if "page=" not in parsed.query.lower():
            continue
        if joined in seen:
            continue
        seen.add(joined)
        listed.append(joined)
    return listed


def printed_getcapabilities(page: str) -> list[tuple[str, str, str]]:
    """Copy printed geo.ngu.no/mapserver GetCapabilities URLs."""

    listed: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for raw in GETCAP_RE.findall(page):
        href = raw.replace("&amp;", "&").strip()
        if not href:
            continue
        parsed = urlsplit(href)
        if parsed.netloc.lower() != HOST:
            continue
        if PATH_MARK not in parsed.path:
            continue
        if "/api/features" in parsed.path:
            continue
        if "/kart/" in parsed.path:
            continue
        if "request=getcapabilities" not in parsed.query.lower():
            continue
        ident = printed_service_id(href)
        if ident is None or ident in seen:
            continue
        seen.add(ident)
        listed.append((ident, href, ident))
    return listed


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


def is_nguwms_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    if parsed.netloc.lower() != HOST:
        return False
    if PATH_MARK not in parsed.path:
        return False
    if "/api/features" in parsed.path:
        return False
    return True


def nguwms_table_id(access_path: str) -> str:
    path = urlsplit(access_path).path.rstrip("/")
    parts = [part for part in path.split("/") if part]
    if PATH_MARK.strip("/") in parts:
        idx = parts.index(PATH_MARK.strip("/"))
        if idx + 1 < len(parts):
            return parts[idx + 1]
    ident = printed_service_id(path)
    return ident or "nguwms"


def cells_from_nguwms(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed WMS Layer/Name text into cells.

    Each Layer keeps printed Name text. A Title sibling, when present,
    stays as a dimension. Nested objects and other XML are not copied.
    Nothing is invented.
    """

    if not isinstance(payload, str) or not payload.strip():
        raise ValueError("nguwms payload is empty or not WMS XML")
    if _is_html(payload):
        raise ValueError("nguwms payload is HTML, not WMS XML")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError("nguwms payload is not WMS XML") from exc
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
        raise ValueError("nguwms payload printed no Layer Name members")
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
        raise SourceError("NGU leftover WMS catalog URL has no printed origin")
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
        f"NGU leftover WMS pages have no printed service matching {ref.source_native_uri}"
    )


def _localname(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _is_html(body: str) -> bool:
    lowered = body.lstrip().lower()
    return lowered.startswith("<!doctype html") or "<html" in body.lower()
