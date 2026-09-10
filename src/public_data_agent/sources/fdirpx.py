"""Fiskeridirektoratet PxWeb aquaculture sales table.

This first bounded slice exists to answer questions about Norwegian farmed
salmon production with returned statistics, not merely an aquaculture-register
or spreadsheet landing page.  The publisher's own table catalogue is the list
source and the listed table URL is both the metadata and observation endpoint.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "fdirpx"
SOURCE_NAME = "Fiskeridirektoratet PxWeb akvakulturstatistikk"
PUBLISHER = "Fiskeridirektoratet"
ROOT_URL = (
    "https://statistikkbanken.fiskeridir.no/PxWeb/api/v1/no/Fiskeridirektoratet"
)
CATALOGUE_URL = f"{ROOT_URL}/A_Akvakultur/A_06_Salg"
TABLE_ID = "A06002a.px"
TABLE_URL = f"{CATALOGUE_URL}/{TABLE_ID}"
LANDING_PAGE = (
    "https://www.fiskeridir.no/statistikk-tall-og-analyse/data-og-statistikk-om-"
    "akvakultur/akvakulturstatistikk-laks-regnbueorret-og-orret-offisiell-statistikk"
)
INGEST_REASON = (
    "listed as A.06.002a in Fiskeridirektoratet's public PxWeb A.06 Salg catalogue"
)
REQUESTS_PER_SECOND = 2.0
BURST = 4


class FdirPxwebSource(SourceBase):
    """One data-bearing official table for farmed salmon sales by species.

    The surrounding sales catalogue currently contains thirteen tables.  V1
    deliberately promotes only the table needed for the known coverage gap;
    listing every neighbour without fetching and shaping it would recreate a
    metadata-only catalogue.
    """

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = (CATALOGUE_URL,)
    ingest_reason = INGEST_REASON

    def __init__(
        self,
        *,
        catalogue_url: str = CATALOGUE_URL,
        table_id: str = TABLE_ID,
        http: Any | None = None,
    ) -> None:
        self.catalogue_url = catalogue_url.rstrip("/")
        self.table_id = table_id
        self.http = http or HttpClient(
            limiter=RateLimiter(REQUESTS_PER_SECOND, BURST),
            timeout=60.0,
            max_retries=3,
        )
        self._listed: dict[str, Any] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        listed = self.http.get_json(self.catalogue_url)
        if not isinstance(listed, list):
            raise SourceError(
                f"Fiskeridirektoratet PxWeb catalogue is not a list: {self.catalogue_url}"
            )
        item = next(
            (
                row
                for row in listed
                if isinstance(row, dict)
                and row.get("type") == "t"
                and row.get("id") == self.table_id
            ),
            None,
        )
        if item is None:
            raise SourceError(
                f"Fiskeridirektoratet PxWeb catalogue did not print {self.table_id}"
            )
        self._listed = item
        refs = [
            DatasetRef(
                source_native_uri=f"{self.catalogue_url}/{self.table_id}",
                source_native_id=self.table_id.removesuffix(".px"),
                catalog_modified=_string(item.get("updated")),
            )
        ]
        end = None if limit is None else offset + limit
        return refs[offset:end]

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        if self._listed is None:
            raise SourceError("table must be listed before it is fetched")
        metadata = self.http.get_json(ref.source_native_uri)
        if not isinstance(metadata, dict) or not isinstance(metadata.get("variables"), list):
            raise SourceError(
                f"Fiskeridirektoratet PxWeb table has no variables: {ref.source_native_uri}"
            )
        title = _string(metadata.get("title")) or _string(self._listed.get("text"))
        variables = [
            str(item.get("text"))
            for item in metadata["variables"]
            if isinstance(item, dict) and _string(item.get("text"))
        ]
        first, last = _period_span(metadata["variables"])
        payload: dict[str, Any] = {
            "id": ref.source_native_id,
            "uri": ref.source_native_uri,
            "title": {"no": title} if title else {},
            "publisher": {"title": {"no": PUBLISHER}, "id": None, "uri": None},
            "distribution": [
                {
                    "uri": ref.source_native_uri,
                    "title": {"no": title} if title else {},
                    "accessURL": [ref.source_native_uri],
                    "fdkFormat": [
                        {"code": "JSON", "type": "MEDIA_TYPE", "name": "application/json"}
                    ],
                }
            ],
            "landingPage": [LANDING_PAGE],
            "variables": variables,
            "keyword": [{"no": "Akvakultur"}, {"no": "Salg"}, *({"no": v} for v in variables)],
            # The table metadata does not print a licence URI.  The publisher's
            # general licence page is not silently promoted to a per-table claim.
            "license": None,
        }
        if first or last:
            payload["temporal"] = [{"startDate": first, "endDate": last}]
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ref.source_native_id,
            source_native_uri=ref.source_native_uri,
            fetched_from=ref.source_native_uri,
            payload=payload,
            catalog_modified=ref.catalog_modified,
        )


def is_fdirpx_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlparse(access_path)
    return (
        parsed.netloc.casefold() == "statistikkbanken.fiskeridir.no"
        and parsed.path.casefold().startswith("/pxweb/api/v1/no/fiskeridirektoratet/")
        and parsed.path.casefold().endswith(".px")
    )


def fdirpx_table_id(access_path: str) -> str:
    return urlparse(access_path).path.rstrip("/").rsplit("/", 1)[-1]


def _period_span(variables: list[Any]) -> tuple[str | None, str | None]:
    for variable in variables:
        if not isinstance(variable, dict) or not variable.get("time"):
            continue
        values = [str(value) for value in variable.get("values") or []]
        return (values[0], values[-1]) if values else (None, None)
    return None, None


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
