from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.npitema import (
    NpitemaSource,
    cells_from_npitema,
    is_npitema_url,
    npitema_table_id,
    printed_service_id,
    printed_services,
)

LIST_URL = "https://geodata.npolar.no/arcgis/rest/services/Temadata?f=json"
BIO_URL = (
    "https://geodata.npolar.no/arcgis/rest/services/Temadata/"
    "F_Biogeographic_Zones_Svalbard/MapServer?f=json"
)
REIN_URL = (
    "https://geodata.npolar.no/arcgis/rest/services/Temadata/"
    "F_Reinsdyrhabitat/MapServer?f=json"
)
BIRD_URL = (
    "https://geodata.npolar.no/arcgis/rest/services/Temadata/"
    "F_Seabirds_Svalbard/MapServer?f=json"
)
GEO_URL = (
    "https://geodata.npolar.no/arcgis/rest/services/Temadata/"
    "G_Geologi_DML/MapServer?f=json"
)
GLACIER_URL = (
    "https://geodata.npolar.no/arcgis/rest/services/Temadata/"
    "I_Glacier_Fronts_Svalbard/MapServer?f=json"
)
NPIGIS_URL = (
    "https://geodata.npolar.no/arcgis/rest/services/Basisdata/"
    "NP_Basiskart_Svalbard_WMS/MapServer?f=json"
)
NPOLAR_URL = "https://api.npolar.no/service/?q=*&format=json"
NVEGIS_URL = "https://gis3.nve.no/map/rest/services/Fjellskred1/MapServer?f=json"
NVE2GIS_URL = "https://gis2.nve.no/arcgis/rest/services/mapservice/AlphaBeta/MapServer?f=json"
DATASET_ID = "npitema:F_Biogeographic_Zones_Svalbard"

CATALOG = {
    "currentVersion": 10.81,
    "folders": [],
    "services": [
        {"name": "Temadata/F_Biogeographic_Zones_Svalbard", "type": "MapServer"},
        {"name": "Temadata/F_Reinsdyrhabitat", "type": "MapServer"},
        {"name": "Temadata/F_Seabirds_Svalbard", "type": "MapServer"},
        {"name": "Temadata/G_Geologi_DML", "type": "MapServer"},
        {"name": "Temadata/I_Glacier_Fronts_Svalbard", "type": "MapServer"},
        {"name": "", "type": "MapServer"},
        {"name": "SkipMe", "type": ""},
        {"nested": True},
    ],
}
BIO_BODY = {
    "mapName": "Biogeografiske soner, Fauna og Flora, Svalbard",
    "copyrightText": "Norsk Polarinstitutt",
    "layers": [
        {"id": 0, "name": "Biogeografiske soner", "type": "Feature Layer"},
        {
            "id": 1,
            "name": "Soner",
            "type": "Feature Layer",
            "nested": {"skip": True},
        },
    ],
    "spatialReference": {"wkid": 25833},
}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == LIST_URL:
            return CATALOG
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == BIO_URL:
            return JsonResponse(status=200, url=url, body=BIO_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"npitema fetch must GET, not POST {url}")


def test_printed_refs_skip_empty_name_or_type() -> None:
    source = NpitemaSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "F_Biogeographic_Zones_Svalbard",
        "F_Reinsdyrhabitat",
        "F_Seabirds_Svalbard",
        "G_Geologi_DML",
        "I_Glacier_Fronts_Svalbard",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        BIO_URL,
        REIN_URL,
        BIRD_URL,
        GEO_URL,
        GLACIER_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "SkipMe" for ref in refs)


def test_printed_services_keep_document_order() -> None:
    listed = printed_services(CATALOG, LIST_URL)
    assert [ident for ident, _href, _title in listed] == [
        "F_Biogeographic_Zones_Svalbard",
        "F_Reinsdyrhabitat",
        "F_Seabirds_Svalbard",
        "G_Geologi_DML",
        "I_Glacier_Fronts_Svalbard",
    ]
    assert [href for _ident, href, _title in listed] == [
        BIO_URL,
        REIN_URL,
        BIRD_URL,
        GEO_URL,
        GLACIER_URL,
    ]


def test_printed_service_id_uses_last_path_segment() -> None:
    assert printed_service_id("F_Reinsdyrhabitat") == "F_Reinsdyrhabitat"
    assert printed_service_id("Temadata/F_Biogeographic_Zones_Svalbard") == (
        "F_Biogeographic_Zones_Svalbard"
    )
    assert printed_service_id("/") is None


def test_npitema_is_a_registered_source() -> None:
    assert "npitema" in SOURCE_IDS
    assert "npigis" in SOURCE_IDS
    assert "npolar" in SOURCE_IDS
    assert "nvegis" in SOURCE_IDS
    assert "hoydegis" in SOURCE_IDS
    source = build_source("npitema")
    assert isinstance(source, NpitemaSource)
    assert source.source_id == "npitema"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = NpitemaSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 5
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "npitema"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == BIO_URL
    assert row["title"] == "F_Biogeographic_Zones_Svalbard"
    reinsdyr = registry.get_dataset("npitema:F_Reinsdyrhabitat")
    assert reinsdyr is not None
    assert reinsdyr["access_path"] == REIN_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("npigis:")
    assert not str(row["id"]).startswith("npolar:")
    assert not str(row["id"]).startswith("nvegis:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["npitema_service_id"] == "F_Biogeographic_Zones_Svalbard"
    assert payload["npitema_service_href"] == BIO_URL
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_layer_names(tmp_path: Path) -> None:
    source = NpitemaSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == BIO_URL
    assert result.table_id == "F_Biogeographic_Zones_Svalbard"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"Biogeografiske soner", "Soner"}
    assert by_value["Biogeografiske soner"]["measure"] == "name"
    dims = json.loads(by_value["Biogeografiske soner"]["dimensions_json"])
    assert dims["id"] == "0"
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == BIO_URL for row in rows)
    registry.close()


def test_cells_copy_printed_name_or_scalar() -> None:
    cells = cells_from_npitema(BIO_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "Biogeografiske soner"
    assert dims["id"] == "0"
    assert "nested" not in dims
    assert cells_from_npitema({"folders": ["ArcticSDI"]}) == [
        ("value", "ArcticSDI", {})
    ]
    assert cells_from_npitema({"name": "F_Biogeographic_Zones_Svalbard", "id": 9}) == [
        ("name", "F_Biogeographic_Zones_Svalbard", {"id": "9"})
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_npitema(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_npitema([])


def test_is_npitema_url_accepts_only_temadata_path() -> None:
    assert is_npitema_url(BIO_URL)
    assert is_npitema_url(LIST_URL)
    assert npitema_table_id(BIO_URL) == "F_Biogeographic_Zones_Svalbard"
    assert npitema_table_id(REIN_URL) == "F_Reinsdyrhabitat"
    assert not is_npitema_url(NPIGIS_URL)
    assert not is_npitema_url(NPOLAR_URL)
    assert not is_npitema_url(NVEGIS_URL)
    assert not is_npitema_url(NVE2GIS_URL)
    assert not is_npitema_url("https://data.norge.no/datasets/x")
    assert not is_npitema_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = NpitemaSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "F_Biogeographic_Zones_Svalbard"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["F_Reinsdyrhabitat"]
