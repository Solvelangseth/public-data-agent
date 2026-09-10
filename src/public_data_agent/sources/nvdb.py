"""Nasjonal vegdatabank: every road object type Statens vegvesen publishes.

The registry is heavy on statistics and thin on things. NVDB is the other kind
of source -- bridges, tunnels, guardrails, kerbs, traffic signs, 424 object types
in all -- and each object carries geometry, typed attributes, and the fylke and
kommune it sits in, so it joins to the same Klass vocabulary the statistics do.

This catalogues object *types*, not objects. A type is a register addressed by
subject the same way Enhetsregisteret is: one resource, not one dataset per
bridge. Nothing here fetches road objects in bulk, which is deliberate while
storage is short -- what is worth recording now is that the source exists, what
it holds, and how to reach one record.

The whole catalogue is one request. The type listing already carries each type's
`egenskapstyper`, so the attribute schema arrives with the listing rather than
costing 424 more requests.

Licence stays null. NVDB's API prints no licence field on a type, and the NLOD
that Statens vegvesen's CKAN portal states for *its* datasets is a claim about
those datasets, not about this API.
"""

from __future__ import annotations

from typing import Any, Iterable

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord
from public_data_agent.sources.base import SourceBase

CATALOGUE_URL = "https://nvdbapiles.atlas.vegvesen.no/vegobjekttyper"
OBJECT_API = "https://nvdbapiles.atlas.vegvesen.no/vegobjekter"
PUBLISHER = "Statens vegvesen"
INGEST_REASON = "listed as a road object type in the NVDB object type catalogue"
# NVDB asks callers to identify themselves; an anonymous client is throttled
# harder and the header costs nothing.
HEADERS = {"Accept": "application/json", "X-Client": "public-data-agent"}
REQUESTS_PER_SECOND = 2.0


class NvdbSource(SourceBase):
    """Catalogue adapter over the NVDB road object type list."""

    source_id = "nvdb"
    source_name = "NVDB object type catalogue"
    endpoints = (CATALOGUE_URL,)
    ingest_reason = INGEST_REASON

    def __init__(self, *, http: Any | None = None, catalogue_url: str = CATALOGUE_URL) -> None:
        self._http = http or HttpClient(
            limiter=RateLimiter(REQUESTS_PER_SECOND, 1), timeout=60.0, max_retries=3
        )
        self._catalogue_url = catalogue_url
        self._by_id: dict[str, dict[str, Any]] = {}

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        body = self._http.get_json(self._catalogue_url, headers=HEADERS)
        rows = [item for item in body if isinstance(item, dict)] if isinstance(body, list) else []
        refs: list[DatasetRef] = []
        for row in rows:
            type_id = row.get("id")
            if type_id is None:
                continue
            # An abstract type holds no objects of its own, so cataloguing it as
            # a retrievable resource would promise records that do not exist.
            if row.get("abstrakt_type"):
                continue
            key = str(type_id)
            self._by_id[key] = row
            refs.append(
                DatasetRef(
                    source_native_uri=f"{OBJECT_API}/{key}",
                    source_native_id=key,
                    catalog_modified=_string(row.get("objektliste_dato")),
                )
            )
        end = None if limit is None else offset + limit
        return refs[offset:end]

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        row = self._by_id.get(ref.source_native_id or "")
        if row is None:
            raise KeyError(f"object type {ref.source_native_id} was not listed by the catalogue")
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ref.source_native_id,
            source_native_uri=ref.source_native_uri,
            fetched_from=self._catalogue_url,
            payload=_payload(row),
            catalog_modified=ref.catalog_modified,
        )

    def fetch_many(self, refs: Iterable[DatasetRef]) -> list[HarvestedRecord]:
        # The listing already carries the full record, schema included.
        return [self.fetch_dataset(ref) for ref in refs]


def _payload(row: dict[str, Any]) -> dict[str, Any]:
    """One object type as the payload the mapper expects. Copied, never filled in."""

    type_id = str(row.get("id"))
    name = _string(row.get("navn"))
    access_url = f"{OBJECT_API}/{type_id}"
    payload: dict[str, Any] = {
        "id": type_id,
        "uri": access_url,
        "title": {"no": name} if name else {},
        "publisher": {"title": {"no": PUBLISHER}, "id": None, "uri": None},
        "distribution": [
            {
                "uri": access_url,
                "title": {"no": name} if name else {},
                "accessURL": [access_url],
                "fdkFormat": [{"code": "JSON", "type": "MEDIA_TYPE", "name": "application/json"}],
            }
        ],
        # NVDB prints no licence on an object type. Statens vegvesen's separate
        # CKAN portal states NLOD for its own datasets; that is not this.
        "license": None,
    }
    description = _string(row.get("beskrivelse"))
    if description:
        payload["description"] = {"no": description}

    # A type's attribute names are how someone describes what they want from it
    # -- "byggverkstype", "lengde", "eier" -- and none of them are in the title.
    attributes = [
        _string(item.get("navn"))
        for item in row.get("egenskapstyper") or []
        if isinstance(item, dict) and _string(item.get("navn"))
    ]
    if attributes:
        payload["variables"] = attributes
        payload["keyword"] = [{"no": attribute} for attribute in attributes]

    # NVDB files each type under its own categories. Like SSB's subject paths,
    # these carry words the one-word title does not: "Bru" is filed under
    # "Bruer og kaier".
    themes = [
        _string(item.get("navn"))
        for item in row.get("kategorier") or []
        if isinstance(item, dict) and _string(item.get("navn"))
    ]
    short = _string(row.get("kortnavn"))
    if short and short.casefold() != name.casefold():
        themes.append(short)
    if themes:
        payload["subjects"] = themes
        payload["theme"] = [{"code": None, "title": {"no": theme}} for theme in themes]
    return payload


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
