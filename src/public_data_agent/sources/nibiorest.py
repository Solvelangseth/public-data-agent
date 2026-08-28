from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase
from public_data_agent.sources.nibiowms import (
    HOST,
    LIST_URL,
    PATH_MARK,
    is_wms_capabilities_body,
    printed_child_urls,
    printed_getcapabilities,
    printed_service_id,
)

SOURCE_ID = "nibiorest"
SOURCE_NAME = "NIBIO leftover WMS"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed GetCapabilities href on the official leftover "
    f"NIBIO WMS pages after nibiowms and ldirwms cgi-bin names, capped at {DEFAULT_MAX_ITEMS}"
)
NIBIOREST_RPS = 2.0
NIBIOREST_BURST = 4
TAKEN_CGI = frozenset(
    (
        "ok_raster",
        "verdiklasserjordbrukogdyrkbar",
        "produksjonspotensial",
        "artsdata",
        "naturbase2",
        "gjodselsfelt_i_skog",
        "hovedplan",
        "riparian_zones",
        "urban_atlas",
        "urban_atlas_stl",
        "vernskog2",
        "reindrift",
        "skogbruksplan",
        "mis",
    )
)


class NibiorestSource(SourceBase):
    """Replaceable ingest adapter for leftover NIBIO WMS past the nibiowms cap.

    Listing copies printed GetCapabilities hrefs the official leftover
    NIBIO WMS child pages print. It skips cgi-bin names already ingested
    by leftover NIBIO WMS or leftover Landbruksdirektoratet WMS, attachment
    links, pages with no cgi-bin GetCapabilities, and GetCapabilities
    bodies that are HTML MapServer errors. Native ids are the printed
    last cgi-bin path segment so `hrl` stays distinct from `ok_raster`.
    Access URLs keep the printed href. This is not NIBIO IPM weather
    (`--source nibio`) and not leftover NIBIO WMS (`--source nibiowms`)
    and not leftover Landbruksdirektoratet WMS (`--source ldirwms`).
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
            limiter=RateLimiter(NIBIOREST_RPS, NIBIOREST_BURST),
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
            "nibiorest_service_id": ident,
            "nibiorest_service_href": href,
            "nibiorest_service_title": title,
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
                f"NIBIO leftover WMS catalog failed for {self.list_url}: {exc}"
            ) from exc
        if not isinstance(page, str) or not page.strip():
            raise SourceError(f"NIBIO leftover WMS catalog is empty: {self.list_url}")
        collected: list[tuple[str, str, str]] = []
        seen: set[str] = set()
        for child_url in printed_child_urls(page, self.list_url):
            try:
                child_page = self.http.get_text(child_url)
            except Exception:
                continue
            if not isinstance(child_page, str) or not child_page.strip():
                continue
            for ident, href, title in printed_getcapabilities(child_page, child_url):
                if ident in seen or ident in TAKEN_CGI:
                    continue
                seen.add(ident)
                collected.append((ident, href, title))
        kept: list[tuple[str, str, str]] = []
        for ident, href, title in collected:
            try:
                body = self.http.get_text(href)
            except Exception:
                continue
            if not is_wms_capabilities_body(body):
                continue
            kept.append((ident, href, title))
        if not kept:
            raise SourceError(
                f"NIBIO leftover WMS pages printed no leftover GetCapabilities hrefs: {self.list_url}"
            )
        self._listed = kept
        return kept


def is_nibiorest_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    if parsed.netloc.lower() != HOST or PATH_MARK not in parsed.path:
        return False
    ident = printed_service_id(parsed.path)
    return ident is not None and ident not in TAKEN_CGI


def nibiorest_table_id(access_path: str) -> str:
    path = urlsplit(access_path).path.rstrip("/")
    parts = [part for part in path.split("/") if part]
    if PATH_MARK.strip("/") in parts:
        idx = parts.index(PATH_MARK.strip("/"))
        if idx + 1 < len(parts):
            return parts[idx + 1]
    ident = printed_service_id(path)
    return ident or "nibiorest"


def cells_from_nibiorest(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed WMS Layer/Name text into cells.

    Each Layer keeps printed Name text. A Title sibling, when present,
    stays as a dimension. Nested objects and other XML are not copied.
    Nothing is invented.
    """

    if not isinstance(payload, str) or not payload.strip():
        raise ValueError("nibiorest payload is empty or not WMS XML")
    if _is_html(payload):
        raise ValueError("nibiorest payload is HTML, not WMS XML")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError("nibiorest payload is not WMS XML") from exc
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
        raise ValueError("nibiorest payload printed no Layer Name members")
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
        f"NIBIO leftover WMS pages have no printed service matching {ref.source_native_uri}"
    )


def _localname(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _is_html(body: str) -> bool:
    lowered = body.lstrip().lower()
    return lowered.startswith("<!doctype html") or "<html" in body.lower()
