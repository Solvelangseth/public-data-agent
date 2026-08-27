from __future__ import annotations

from typing import Any

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "brreg"
SOURCE_NAME = "Brønnøysundregistrene Enhetsregisteret"
LIST_URL = "https://data.brreg.no/enhetsregisteret/api"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "listed as a printed HAL _links relation on the official "
    "Enhetsregisteret API root, capped at 10"
)
BRREG_RPS = 2.0
BRREG_BURST = 4


class BrregEnhetsregisterSource(SourceBase):
    """Replaceable ingest adapter for the official Enhetsregisteret HAL catalog.

    Listing copies printed `_links` on the API root except `self`. Ids and
    hrefs are copied from the printed JSON.
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
            limiter=RateLimiter(BRREG_RPS, BRREG_BURST),
            timeout=60.0,
        )

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        cap = self.max_items if limit is None else limit
        try:
            body = self.http.get_json(self.list_url)
        except Exception as exc:
            raise SourceError(f"Enhetsregisteret API root failed for {self.list_url}: {exc}") from exc
        if not isinstance(body, dict):
            raise SourceError(f"Enhetsregisteret API root is not a JSON object: {self.list_url}")
        links = body.get("_links")
        if not isinstance(links, dict):
            raise SourceError(f"Enhetsregisteret API root has no _links object: {self.list_url}")
        refs: list[DatasetRef] = []
        for rel, link in links.items():
            if rel == "self":
                continue
            href = _printed_href(link)
            if href is None:
                continue
            refs.append(
                DatasetRef(
                    source_native_uri=href,
                    source_native_id=str(rel),
                )
            )
            if len(refs) >= cap + offset:
                break
        return refs[offset : offset + cap]

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        href = ref.source_native_uri
        try:
            meta = self.http.get_json(href)
        except Exception as exc:
            raise SourceError(f"Enhetsregisteret GET failed for {href}: {exc}") from exc
        if not isinstance(meta, dict):
            raise SourceError(f"Enhetsregisteret response is not a JSON object: {href}")
        payload = {
            "id": ref.source_native_id,
            "uri": href,
            "title": {"no": ref.source_native_id},
            "description": _top_level_description(meta),
            "publisher": None,
            "license": None,
            "distribution": [
                {
                    "accessURL": [href],
                    "downloadURL": [href],
                }
            ],
            "landingPage": [href],
            "brreg_metadata": meta,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ref.source_native_id,
            source_native_uri=href,
            fetched_from=href,
            payload=payload,
            catalog_modified=ref.catalog_modified,
        )


def _printed_href(link: Any) -> str | None:
    if not isinstance(link, dict):
        return None
    href = link.get("href")
    if isinstance(href, str) and href.strip():
        return href.strip()
    return None


def _top_level_description(meta: dict[str, Any]) -> dict[str, str] | None:
    for key in ("title", "beskrivelse"):
        value = meta.get(key)
        if isinstance(value, str) and value.strip():
            return {"no": value}
    return None
