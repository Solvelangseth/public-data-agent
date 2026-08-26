from __future__ import annotations

from typing import Any, Iterable

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SPARQL_URL = "https://sparql.fellesdatakatalog.digdir.no"
RESOURCE_URL = "https://resource.api.fellesdatakatalog.digdir.no"

SOURCE_ID = "datanorge"
SOURCE_NAME = "Data.norge / Felles datakatalog"
INGEST_REASON = "listed as dcat:Dataset in Felles datakatalog SPARQL"

# Resource Service published limit: 5 rps, burst 10. Stay under it.
RESOURCE_RPS = 5.0
RESOURCE_BURST = 10
DEFAULT_PAGE_SIZE = 500
DEFAULT_BATCH_SIZE = 25

LIST_QUERY = """
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
SELECT ?dataset (SAMPLE(?fdkId) AS ?fdkId) (MAX(?modified) AS ?catalogModified)
WHERE {
  ?dataset a dcat:Dataset .
  OPTIONAL {
    ?record a dcat:CatalogRecord ;
            foaf:primaryTopic ?dataset ;
            dct:identifier ?fdkId .
    OPTIONAL { ?record dct:modified ?modified }
  }
}
GROUP BY ?dataset
ORDER BY ?dataset
LIMIT {limit} OFFSET {offset}
"""


class DataNorgeSource(SourceBase):
    """Harvest adapter for Data.norge / Felles datakatalog.

    Listing uses SPARQL (system of record for membership). Full metadata
    comes from the Resource Service JSON, not the Search API.
    """

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = (SPARQL_URL, RESOURCE_URL)
    ingest_reason = INGEST_REASON

    def __init__(
        self,
        *,
        sparql_url: str = SPARQL_URL,
        resource_url: str = RESOURCE_URL,
        page_size: int = DEFAULT_PAGE_SIZE,
        batch_size: int = DEFAULT_BATCH_SIZE,
        http: HttpClient | None = None,
        sparql_http: HttpClient | None = None,
    ) -> None:
        self.sparql_url = sparql_url
        self.resource_url = resource_url.rstrip("/")
        self.page_size = page_size
        self.batch_size = batch_size
        self.http = http or HttpClient(limiter=RateLimiter(RESOURCE_RPS, RESOURCE_BURST))
        # SPARQL has no published rps. Keep it well below the Resource Service.
        self.sparql_http = sparql_http or HttpClient(limiter=RateLimiter(2.0, 4))

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        refs: list[DatasetRef] = []
        remaining = limit
        page_offset = offset
        while remaining is None or remaining > 0:
            page = self.page_size if remaining is None else min(self.page_size, remaining)
            rows = self._sparql(LIST_QUERY.format(limit=page, offset=page_offset))
            for row in rows:
                dataset = _binding(row, "dataset")
                if not dataset:
                    continue
                refs.append(
                    DatasetRef(
                        source_native_uri=dataset,
                        source_native_id=_binding(row, "fdkId"),
                        catalog_modified=_binding(row, "catalogModified"),
                    )
                )
            if remaining is not None:
                remaining -= len(rows)
            page_offset += len(rows)
            if len(rows) < page:
                break
        return refs

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        if ref.source_native_id:
            url = f"{self.resource_url}/v1/datasets/{ref.source_native_id}"
            payload = self.http.get_json(url)
        else:
            url = f"{self.resource_url}/v1/datasets/by-uri?uri={_q(ref.source_native_uri)}"
            payload = self.http.get_json(url)
        if not isinstance(payload, dict):
            raise SourceError(f"Resource Service did not return a dataset object from {url}")
        return self._record(payload, ref, url)

    def fetch_many(self, refs: Iterable[DatasetRef]) -> list[HarvestedRecord]:
        pending = list(refs)
        records: list[HarvestedRecord] = []
        with_id = [ref for ref in pending if ref.source_native_id]
        without_id = [ref for ref in pending if not ref.source_native_id]
        by_id = {ref.source_native_id: ref for ref in with_id}

        for chunk in _chunks(with_id, self.batch_size):
            ids = [ref.source_native_id for ref in chunk if ref.source_native_id]
            url = f"{self.resource_url}/v1/datasets"
            try:
                payload = self.http.post_json(url, {"ids": ids})
            except Exception:
                records.extend(self.fetch_dataset(ref) for ref in chunk)
                continue
            found: set[str] = set()
            if isinstance(payload, list):
                for item in payload:
                    if not isinstance(item, dict) or not item.get("id"):
                        continue
                    native_id = str(item["id"])
                    ref = by_id.get(native_id)
                    if ref is None:
                        continue
                    found.add(native_id)
                    records.append(self._record(item, ref, url))
            for ref in chunk:
                if ref.source_native_id not in found:
                    records.append(self.fetch_dataset(ref))

        records.extend(self.fetch_dataset(ref) for ref in without_id)
        return records

    def _sparql(self, query: str) -> list[dict[str, Any]]:
        result = self.sparql_http.post_form(
            self.sparql_url,
            {"query": query},
            headers={"Accept": "application/sparql-results+json"},
        )
        try:
            return result["results"]["bindings"]
        except (TypeError, KeyError) as exc:
            raise SourceError("SPARQL response was not a SELECT result set") from exc

    def _record(self, payload: dict[str, Any], ref: DatasetRef, fetched_from: str) -> HarvestedRecord:
        native_id = payload.get("id") if isinstance(payload.get("id"), str) else ref.source_native_id
        native_uri = payload.get("uri") if isinstance(payload.get("uri"), str) else ref.source_native_uri
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=native_id,
            source_native_uri=native_uri,
            fetched_from=fetched_from,
            payload=payload,
            catalog_modified=ref.catalog_modified,
        )


def _binding(row: dict[str, Any], name: str) -> str | None:
    cell = row.get(name)
    if not isinstance(cell, dict):
        return None
    value = cell.get("value")
    return value if isinstance(value, str) and value else None


def _q(uri: str) -> str:
    from urllib.parse import quote

    return quote(uri, safe="")


def _chunks(items: list[DatasetRef], size: int) -> Iterable[list[DatasetRef]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]
