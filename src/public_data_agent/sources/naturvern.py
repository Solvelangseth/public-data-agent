"""Miljødirektoratet protected-area polygons, one register.

Geonorge already catalogues *Naturvernområder* and an Atom feed of national
zips. The zip is tens of megabytes; this connector uses the printed ArcGIS
REST layer instead, which answers one area by ``naturvernId`` or a bounded
page. It does not download the country file.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote, urlparse

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "naturvern"
SOURCE_NAME = "Miljødirektoratet naturvernområder"
PUBLISHER = "Miljødirektoratet"
SERVICE_URL = "https://kart.miljodirektoratet.no/arcgis/rest/services/vern/MapServer"
LAYER_ID = 0
LAYER_URL = f"{SERVICE_URL}/{LAYER_ID}"
GEONORGE_PAGE = (
    "https://kartkatalog.geonorge.no/metadata/naturvernomrader/"
    "5857ec0a-8d2c-4cd8-baa2-0dc54ae213b4"
)
INGEST_REASON = (
    "listed as layer 0 (naturvern_omrade) on Miljødirektoratet's public "
    "ArcGIS REST MapServer vern"
)
HOST = "kart.miljodirektoratet.no"
PATH_RE = re.compile(
    r"/arcgis/rest/services/vern/mapserver/0/?$",
    re.IGNORECASE,
)
SUBJECT_SCHEME = "naturbase:naturvernId"
DEFAULT_LIMIT = 10
MAX_LIMIT = 100
REQUESTS_PER_SECOND = 2.0
BURST = 4
# Geometry is omitted on purpose: a national-park polygon can dwarf the
# attributes, and the question this answers is which areas exist.
QUERY_FIELDS = (
    "naturvernId,cddaId,navn,offisieltNavn,faktaark,verneform,verneforskrift,"
    "kommune,forvaltningsmyndighet,iucn,verneformAggregert,OBJECTID,"
    "SHAPE.STArea(),SHAPE.STLength()"
)


class NaturvernSource(SourceBase):
    """One feature register: protected areas, not the WMS and not the zip."""

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = (LAYER_URL,)
    ingest_reason = INGEST_REASON

    def __init__(
        self,
        *,
        layer_url: str = LAYER_URL,
        http: Any | None = None,
    ) -> None:
        self.layer_url = layer_url.rstrip("/")
        self.http = http or HttpClient(
            limiter=RateLimiter(REQUESTS_PER_SECOND, BURST),
            timeout=60.0,
            max_retries=3,
        )
        self._layer: dict[str, Any] | None = None

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0) -> list[DatasetRef]:
        body = self.http.get_json(f"{self.layer_url}?f=json")
        if not isinstance(body, dict) or body.get("type") != "Feature Layer":
            raise SourceError(f"vern layer is not a Feature Layer: {self.layer_url}")
        self._layer = body
        refs = [
            DatasetRef(
                source_native_uri=self.layer_url,
                source_native_id="naturvern_omrade",
            )
        ]
        end = None if limit is None else offset + limit
        return refs[offset:end]

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        layer = self._layer or {}
        name = _string(layer.get("name")) or "naturvern_omrade"
        payload: dict[str, Any] = {
            "id": name,
            "uri": ref.source_native_uri,
            "title": {"no": "Naturvernområder"},
            "description": {
                "no": _string(layer.get("description"))
                or "Verneområder og vernede enkeltobjekt i Norge."
            },
            "publisher": {"title": {"no": PUBLISHER}, "id": None, "uri": None},
            "distribution": [
                {
                    "uri": ref.source_native_uri,
                    "title": {"no": "Naturvernområder"},
                    "accessURL": [ref.source_native_uri],
                    "fdkFormat": [
                        {"code": "JSON", "type": "MEDIA_TYPE", "name": "application/json"}
                    ],
                }
            ],
            "landingPage": [GEONORGE_PAGE],
            "keyword": [
                {"no": "naturvernområder"},
                {"no": "naturvern"},
                {"no": "verneområder"},
                {"no": name},
            ],
            # ArcGIS JSON prints no licence. Geonorge states NLOD 2.0 for the
            # dataset this layer serves; this harvest does not copy that across.
            "license": None,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=ref.source_native_id,
            source_native_uri=ref.source_native_uri,
            fetched_from=f"{self.layer_url}?f=json",
            payload=payload,
            catalog_modified=None,
        )


def is_naturvern_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlparse(access_path)
    if parsed.netloc.casefold() != HOST:
        return False
    return PATH_RE.search(parsed.path) is not None


def naturvern_table_id(access_path: str) -> str:
    return "naturvern_omrade"


def query_url(
    access_path: str,
    *,
    naturvern_id: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> str:
    base = access_path.split("?", 1)[0].rstrip("/")
    where = "1=1"
    if naturvern_id:
        safe = naturvern_id.replace("'", "''")
        where = f"naturvernId='{safe}'"
    return (
        f"{base}/query?where={quote(where, safe="='")}"
        f"&outFields={quote(QUERY_FIELDS)}"
        f"&returnGeometry=false"
        f"&resultRecordCount={int(limit)}"
        f"&f=json"
    )


def feature_from_arcgis(payload: dict[str, Any]) -> dict[str, Any]:
    attrs = payload.get("attributes") if isinstance(payload.get("attributes"), dict) else payload
    code = _string(attrs.get("naturvernId"))
    if not code:
        raise ValueError("protected-area feature printed no naturvernId")
    label = _string(attrs.get("offisieltNavn")) or _string(attrs.get("navn")) or code
    attributes = {
        key: value
        for key, value in attrs.items()
        if key not in {"SHAPE", "GlobalID", "NaturvernFKID"}
        and value is not None
    }
    return {
        "subject_scheme": SUBJECT_SCHEME,
        "subject_code": code,
        "subject_label": label,
        "attributes": attributes,
    }


def shape_from_layer(layer: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fields = []
    for item in layer.get("fields") or []:
        if not isinstance(item, dict):
            continue
        code = _string(item.get("name"))
        if not code or code in {"SHAPE", "GlobalID", "NaturvernFKID"}:
            continue
        role = "key" if code == "naturvernId" else "attribute"
        if code.startswith("SHAPE."):
            role = "measure"
        fields.append(
            {
                "field_code": code,
                "field_label": _string(item.get("alias")) or code,
                "field_role": role,
                "values": [],
            }
        )
    keys = [
        {
            "scheme": SUBJECT_SCHEME,
            "field_code": "naturvernId",
            "coverage_count": None,
        }
    ]
    return fields, keys


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
