from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "rawms"
SOURCE_NAME = "Riksantikvaren leftover WMS"
KULTURMINNER2_URL = (
    "https://kart.ra.no/wms/kulturminner2?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
)
KULTURMILJOER_URL = (
    "https://kart.ra.no/wms/kulturmiljoer?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
)
LIST_URLS = (KULTURMINNER2_URL, KULTURMILJOER_URL)
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed leftover Riksantikvaren WMS GetCapabilities "
    f"document, capped at {DEFAULT_MAX_ITEMS}. This is not "
    "--source riksantikvaren and not --source ragis"
)
RAWMS_RPS = 2.0
RAWMS_BURST = 4
HOST = "kart.ra.no"
PATH_MARK = "/wms/"


class RawmsSource(SourceBase):
    """Replaceable ingest adapter for leftover Riksantikvaren WMS.

    Listing copies the two official leftover GetCapabilities documents
    printed on kart.ra.no/wms. Each document is one dataset. It skips a
    document that is not WMS XML. Native ids are the printed last path
    segment so `kulturminner2` stays distinct from `kulturmiljoer`.
    Access URLs keep the printed GetCapabilities URL. This first slice
    stays inside those two documents and caps the walk. This is not
    Riksantikvaren MABYGIS FeatureServer layers
    (`--source riksantikvaren`) and not leftover MABYGIS REST
    (`--source ragis`).
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
            limiter=RateLimiter(RAWMS_RPS, RAWMS_BURST),
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
            "rawms_service_id": ident,
            "rawms_service_href": href,
            "rawms_service_title": title,
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
            if not is_wms_capabilities_body(body):
                continue
            seen.add(ident)
            listed.append((ident, url, ident))
        if not listed:
            raise SourceError(
                "Riksantikvaren leftover WMS printed no GetCapabilities XML: "
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


def is_wms_capabilities_body(body: str) -> bool:
    if not isinstance(body, str) or not body.strip():
        return False
    if _is_html(body):
        return False
    return "WMS_Capabilities" in body or "WMT_MS_Capabilities" in body


def is_rawms_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    if parsed.netloc.lower() != HOST:
        return False
    path = parsed.path
    if PATH_MARK not in path:
        return False
    if "/arcgis/" in path:
        return False
    return True


def rawms_table_id(access_path: str) -> str:
    path = urlsplit(access_path).path.rstrip("/")
    parts = [part for part in path.split("/") if part]
    if PATH_MARK.strip("/") in parts:
        idx = parts.index(PATH_MARK.strip("/"))
        if idx + 1 < len(parts):
            return parts[idx + 1]
    ident = printed_service_id(path)
    return ident or "rawms"


def cells_from_rawms(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed WMS Layer/Name text into cells.

    Each Layer keeps printed Name text. A Title sibling, when present,
    stays as a dimension. Nested objects and other XML are not copied.
    Nothing is invented.
    """

    if not isinstance(payload, str) or not payload.strip():
        raise ValueError("rawms payload is empty or not WMS XML")
    if _is_html(payload):
        raise ValueError("rawms payload is HTML, not WMS XML")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError("rawms payload is not WMS XML") from exc
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
        raise ValueError("rawms payload printed no Layer Name members")
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
        f"Riksantikvaren leftover WMS has no printed service matching {ref.source_native_uri}"
    )


def _localname(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _is_html(body: str) -> bool:
    lowered = body.lstrip().lower()
    return lowered.startswith("<!doctype html") or "<html" in body.lower()
