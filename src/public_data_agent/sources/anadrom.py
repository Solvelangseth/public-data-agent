"""Miljødirektoratet anadromous river stretches, one register.

The MapServer catalog ``anadrome_laksefisk`` lists layer names. Fetching that
root stored those names as observations. This connector queries layer 4
(``anadrome_strekninger_lin``) instead: one river by printed ``vassdragsNR``,
or a bounded page. Geometry is omitted. Other layers on the same service
(barriers, stocks, outlets) are not this register.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote, urlparse

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "anadrom"
SOURCE_NAME = "Miljødirektoratet anadrome strekninger"
PUBLISHER = "Miljødirektoratet"
SERVICE_URL = (
    "https://kart.miljodirektoratet.no/arcgis/rest/services/anadrome_laksefisk/MapServer"
)
LAYER_ID = 4
LAYER_URL = f"{SERVICE_URL}/{LAYER_ID}"
GEONORGE_PAGE = (
    "https://kartkatalog.geonorge.no/metadata/anadrome-laksefisk-strekninger/"
    "8e01b0fb-476b-4b7f-8c16-60fcfb2df508"
)
INGEST_REASON = (
    "listed as layer 4 (anadrome_strekninger_lin) on Miljødirektoratet's public "
    "ArcGIS REST MapServer anadrome_laksefisk"
)
HOST = "kart.miljodirektoratet.no"
PATH_RE = re.compile(
    r"/arcgis/rest/services/anadrome_laksefisk/mapserver/4/?$",
    re.IGNORECASE,
)
SUBJECT_SCHEME = "nve:vassdragsnummer"
DEFAULT_LIMIT = 10
MAX_LIMIT = 100
REQUESTS_PER_SECOND = 2.0
BURST = 4
QUERY_FIELDS = (
    "objtype,vassdragsNR,nasjonaltLaksevassdrag,lakseregURL,elvenavn,"
    "malemetode,noyaktighet,oppdateringsdato,OBJECTID"
)


class AnadromSource(SourceBase):
    """One feature register: anadromous stretches, not the MapServer catalog."""

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
            raise SourceError(f"anadrom layer is not a Feature Layer: {self.layer_url}")
        self._layer = body
        refs = [
            DatasetRef(
                source_native_uri=self.layer_url,
                source_native_id="anadrome_strekninger_lin",
            )
        ]
        end = None if limit is None else offset + limit
        return refs[offset:end]

    def fetch_dataset(self, ref: DatasetRef) -> HarvestedRecord:
        layer = self._layer or {}
        name = _string(layer.get("name")) or "anadrome_strekninger_lin"
        payload: dict[str, Any] = {
            "id": name,
            "uri": ref.source_native_uri,
            "title": {"no": "Anadrome laksefisk - Strekninger"},
            "description": {
                "no": _string(layer.get("description"))
                or "Strekninger i vassdrag med anadrome laksefiskbestander."
            },
            "publisher": {"title": {"no": PUBLISHER}, "id": None, "uri": None},
            "distribution": [
                {
                    "uri": ref.source_native_uri,
                    "title": {"no": "Anadrome laksefisk - Strekninger"},
                    "accessURL": [ref.source_native_uri],
                    "fdkFormat": [
                        {"code": "JSON", "type": "MEDIA_TYPE", "name": "application/json"}
                    ],
                }
            ],
            "landingPage": [GEONORGE_PAGE],
            "keyword": [
                {"no": "anadrome laksefisk"},
                {"no": "anadrome strekninger"},
                {"no": "laksefisk"},
                {"no": "vassdrag"},
                {"no": "nasjonale laksevassdrag"},
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


def is_anadrom_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlparse(access_path)
    if parsed.netloc.casefold() != HOST:
        return False
    return PATH_RE.search(parsed.path) is not None


def anadrom_table_id(access_path: str) -> str:
    return "anadrome_strekninger_lin"


def query_url(
    access_path: str,
    *,
    vassdrags_nr: str | None = None,
    elvenavn: str | None = None,
    nasjonalt_laksevassdrag: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> str:
    base = access_path.split("?", 1)[0].rstrip("/")
    clauses: list[str] = []
    if vassdrags_nr:
        clauses.append(f"vassdragsNR='{_sql_literal(vassdrags_nr)}'")
    if elvenavn:
        clauses.append(f"elvenavn='{_sql_literal(elvenavn)}'")
    if nasjonalt_laksevassdrag:
        clauses.append(
            f"nasjonaltLaksevassdrag='{_sql_literal(nasjonalt_laksevassdrag)}'"
        )
    where = " AND ".join(clauses) if clauses else "1=1"
    return (
        f"{base}/query?where={quote(where, safe="='")}"
        f"&outFields={quote(QUERY_FIELDS)}"
        f"&returnGeometry=false"
        f"&resultRecordCount={int(limit)}"
        f"&f=json"
    )


def feature_from_arcgis(payload: dict[str, Any]) -> dict[str, Any]:
    attrs = payload.get("attributes") if isinstance(payload.get("attributes"), dict) else payload
    code = _string(attrs.get("vassdragsNR"))
    if not code:
        raise ValueError("anadromous-stretch feature printed no vassdragsNR")
    label = _string(attrs.get("elvenavn")) or code
    attributes = {
        key: value
        for key, value in attrs.items()
        if key not in {"SHAPE"} and value is not None
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
        if not code or code in {"SHAPE"}:
            continue
        role = "key" if code == "vassdragsNR" else "attribute"
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
            "field_code": "vassdragsNR",
            "coverage_count": None,
        }
    ]
    return fields, keys


def _sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
