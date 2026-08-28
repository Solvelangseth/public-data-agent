from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "kystwms"
SOURCE_NAME = "Kystverket leftover WMS"
WMS_URL = (
    "https://services.kystverket.no/wms.ashx?service=WMS&request=GetCapabilities"
)
WFS_URL = (
    "https://services.kystverket.no/wfs.ashx?service=WFS&request=GetCapabilities"
)
LIST_URLS = (WMS_URL, WFS_URL)
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed leftover Kystverket WMS or WFS GetCapabilities "
    f"document, capped at {DEFAULT_MAX_ITEMS}. This is not "
    "--source kystverket, not --source havnedata, and not --source navwarnings"
)
KYSTWMS_RPS = 2.0
KYSTWMS_BURST = 4
HOST = "services.kystverket.no"
PATH_WMS = "wms.ashx"
PATH_WFS = "wfs.ashx"


class KystwmsSource(SourceBase):
    """Replaceable ingest adapter for leftover Kystverket WMS.

    Listing copies the two official leftover GetCapabilities documents
    printed on services.kystverket.no. Each document is one dataset. It
    skips a document that is not WMS or WFS XML. Native ids are the
    printed last path segment so `wms.ashx` stays distinct from
    `wfs.ashx`. Access URLs keep the printed GetCapabilities URL. This
    first slice stays inside those two documents and caps the walk.
    This is not Kystdatahuset (`--source kystverket`), not havnedata
    collections (`--source havnedata`), and not navigational warnings
    (`--source navwarnings`).
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
            limiter=RateLimiter(KYSTWMS_RPS, KYSTWMS_BURST),
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
            "kystwms_service_id": ident,
            "kystwms_service_href": href,
            "kystwms_service_title": title,
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
            ident = printed_service_id(url)
            if ident is None or ident in seen:
                continue
            try:
                body = self.http.get_text(url)
            except Exception:
                continue
            if not is_ogc_capabilities_body(body):
                continue
            seen.add(ident)
            listed.append((ident, url, ident))
        if not listed:
            raise SourceError(
                "Kystverket leftover WMS printed no GetCapabilities XML: "
                + ", ".join(self.list_urls)
            )
        self._listed = listed
        return listed


def printed_service_id(name: str) -> str | None:
    path = urlsplit(name).path if name else ""
    if not path:
        path = name
    segment = path.rstrip("/").split("/")[-1] if path else ""
    if not segment:
        return None
    return segment


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


def is_kystwms_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    if parsed.netloc.lower() != HOST:
        return False
    path = parsed.path
    return PATH_WMS in path or PATH_WFS in path


def kystwms_table_id(access_path: str) -> str:
    ident = printed_service_id(access_path)
    return ident or "kystwms"


def cells_from_kystwms(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed WMS Layer/Name or WFS FeatureType/Name text into cells.

    WMS_Capabilities and WMT_MS_Capabilities keep printed Layer Name
    text. WFS_Capabilities keeps printed FeatureType Name text. A Title
    sibling, when present, stays as a dimension. Nested objects and
    other XML are not copied. Nothing is invented.
    """

    if not isinstance(payload, str) or not payload.strip():
        raise ValueError("kystwms payload is empty or not WMS/WFS XML")
    if _is_html(payload):
        raise ValueError("kystwms payload is HTML, not WMS/WFS XML")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError("kystwms payload is not WMS/WFS XML") from exc
    local = _localname(root.tag)
    if local in ("WMS_Capabilities", "WMT_MS_Capabilities"):
        cells = _name_cells(root, "Layer")
        if not cells:
            raise ValueError("kystwms payload printed no Layer Name members")
        return cells
    if local == "WFS_Capabilities":
        cells = _name_cells(root, "FeatureType")
        if not cells:
            raise ValueError("kystwms payload printed no FeatureType Name members")
        return cells
    raise ValueError("kystwms payload is not WMS/WFS XML")


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
        f"Kystverket leftover WMS has no printed service matching {ref.source_native_uri}"
    )


def _localname(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _is_html(body: str) -> bool:
    lowered = body.lstrip().lower()
    return lowered.startswith("<!doctype html") or "<html" in body.lower()
