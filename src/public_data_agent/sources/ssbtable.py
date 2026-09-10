"""SSB PxWeb table catalogue.

Every row here is a numeric statistics table that the existing PxWeb connector
in ``fetch.py`` can already retrieve observations from. The Data.norge harvest
catalogues descriptions; this catalogues things that actually return cells.

The v2 API also publishes ``variableNames`` and first/last period per table.
Those are the dimension and coverage fields GAPS.md records as absent from
every Data.norge row, so they are stored as harvested, never inferred.
"""

from __future__ import annotations

from typing import Any, Iterable

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord
from public_data_agent.sources.base import SourceBase

CATALOGUE_URL = "https://data.ssb.no/api/pxwebapi/v2/tables"
# The beta listing publishes tables the stable one omits -- 245 of them when
# this was measured, mostly older series like the 1996 population projections.
# Neither listing is complete on its own: 154 tables the registry holds from the
# stable list are absent from the beta one, and spot checks (01301 from beta
# only, 06265 from stable only) show both still answer through the table API. So
# both are paged and the results unioned, rather than trusting either as the
# catalogue.
CATALOGUE_URL_BETA = "https://data.ssb.no/api/pxwebapi/v2-beta/tables"
CATALOGUE_URLS = (CATALOGUE_URL, CATALOGUE_URL_BETA)
TABLE_API = "https://data.ssb.no/api/v0/no/table"
SSB_PUBLISHER = "Statistisk sentralbyrå"
INGEST_REASON = "listed as a public table in the SSB PxWeb v2 table catalogue"
PAGE_SIZE = 500
# SSB publishes no rps for this endpoint. Stay well below anything punitive.
REQUESTS_PER_MINUTE = 60


class SsbTableSource(SourceBase):
    """Catalogue adapter over the SSB PxWeb v2 table list."""

    source_id = "ssbtable"
    source_name = "SSB PxWeb table catalogue"
    endpoints = CATALOGUE_URLS
    ingest_reason = INGEST_REASON

    def __init__(
        self,
        *,
        http: Any | None = None,
        catalogue_url: str | tuple[str, ...] = CATALOGUE_URLS,
        page_size: int = PAGE_SIZE,
        language: str = "no",
    ) -> None:
        self._http = http or HttpClient(
            limiter=RateLimiter(REQUESTS_PER_MINUTE, 1), timeout=60.0, max_retries=3
        )
        self._catalogue_urls = (
            (catalogue_url,) if isinstance(catalogue_url, str) else tuple(catalogue_url)
        )
        self._page_size = page_size
        self._language = language
        self._by_id: dict[str, dict[str, Any]] = {}

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        """Page the catalogue until the requested slice is covered."""

        wanted = None if limit is None else offset + limit
        refs: list[DatasetRef] = []
        seen: set[str] = set()
        for catalogue_url in self._catalogue_urls:
            page = 1
            total_pages: int | None = None
            while total_pages is None or page <= total_pages:
                tables, total_pages = self._page(catalogue_url, page)
                if not tables:
                    break
                for table in tables:
                    table_id = table.get("id")
                    if not isinstance(table_id, str) or not table_id:
                        continue
                    # A table in both listings is one table. The first listing
                    # wins, so the stable catalogue's record is the one kept.
                    if table_id in seen:
                        continue
                    seen.add(table_id)
                    self._by_id[table_id] = table
                    refs.append(
                        DatasetRef(
                            source_native_uri=f"{TABLE_API}/{table_id}",
                            source_native_id=table_id,
                            catalog_modified=_string(table.get("updated")),
                        )
                    )
                if wanted is not None and len(refs) >= wanted:
                    break
                page += 1
            if wanted is not None and len(refs) >= wanted:
                break
        end = None if limit is None else offset + limit
        return refs[offset:end]

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        table = self._by_id.get(ref.source_native_id or "")
        if table is None:
            raise KeyError(f"table {ref.source_native_id} was not listed by the catalogue")
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ref.source_native_id,
            source_native_uri=ref.source_native_uri,
            fetched_from=self._catalogue_urls[0],
            payload=_payload(table),
            catalog_modified=ref.catalog_modified,
        )

    def fetch_many(self, refs: Iterable[DatasetRef]) -> list[HarvestedRecord]:
        # The listing already carries the full record; no extra request needed.
        return [self.fetch_dataset(ref) for ref in refs]

    def _page(self, catalogue_url: str, page: int) -> tuple[list[dict[str, Any]], int | None]:
        """Return one page of tables plus the catalogue's own page count.

        Requesting a page past the end is a 404, not an empty list, so the
        loop must be bounded by totalPages rather than by an empty response.
        """

        url = (
            f"{catalogue_url}?lang={self._language}"
            f"&pagesize={self._page_size}&pageNumber={page}"
        )
        body = self._http.get_json(url)
        if not isinstance(body, dict):
            return [], None
        tables = body.get("tables")
        rows = [item for item in tables if isinstance(item, dict)] if isinstance(tables, list) else []
        meta = body.get("page")
        total = meta.get("totalPages") if isinstance(meta, dict) else None
        return rows, total if isinstance(total, int) else None


def _payload(table: dict[str, Any]) -> dict[str, Any]:
    """Shape one catalogue row as the DCAT-ish payload the mapper expects.

    Only stored fields are copied. Absent values stay absent rather than being
    filled with a plausible default.
    """

    table_id = str(table.get("id"))
    label = _string(table.get("label"))
    access_url = f"{TABLE_API}/{table_id}"
    payload: dict[str, Any] = {
        "id": table_id,
        "uri": access_url,
        "title": {"no": label} if label else {},
        "publisher": {"title": {"no": SSB_PUBLISHER}, "id": None, "uri": None},
        "distribution": [
            {
                "uri": access_url,
                "title": {"no": label} if label else {},
                "accessURL": [access_url],
                "fdkFormat": [{"code": "JSON", "type": "MEDIA_TYPE", "name": "application/json"}],
            }
        ],
        # SSB PxWeb open tables carry no per-table licence document in this
        # catalogue. Leaving it null is the documented behaviour for unknown.
        "license": None,
    }
    description = _string(table.get("description"))
    if description:
        payload["description"] = {"no": description}

    first, last = _string(table.get("firstPeriod")), _string(table.get("lastPeriod"))
    if first or last:
        payload["temporal"] = [{"startDate": first, "endDate": last}]

    # variableNames is the dimension list GAPS.md records as absent from every
    # Data.norge row. It is stored and also offered to the ranker as keywords:
    # a table's dimensions are how people describe what they want from it.
    variables = [name for name in table.get("variableNames") or [] if isinstance(name, str)]
    if variables:
        payload["variables"] = variables
        payload["keyword"] = [{"no": name} for name in variables]

    # SSB's own subject hierarchy carries words the title often lacks: table
    # 03777 is titled "Personer i arbeidsstyrken" but is filed under
    # "Arbeidsledighet". Dropping it makes the table unfindable by the word a
    # person would actually search, so it is kept as real harvested metadata.
    subjects = _subject_labels(table.get("paths"))
    if subjects:
        payload["subjects"] = subjects
        payload["theme"] = [{"code": None, "title": {"no": subject}} for subject in subjects]
    return payload


def _subject_labels(paths: Any) -> list[str]:
    """Flatten the subject hierarchy SSB attaches to each table."""

    labels: list[str] = []
    if not isinstance(paths, list):
        return labels
    for path in paths:
        if not isinstance(path, list):
            continue
        for node in path:
            if isinstance(node, dict):
                label = _string(node.get("label"))
                if label and label not in labels:
                    labels.append(label)
    return labels


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
