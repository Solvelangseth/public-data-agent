from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.npiintern import (
    NpiinternSource,
    cells_from_npiintern,
    is_npiintern_url,
    npiintern_table_id,
    printed_service_id,
    printed_services,
)

LIST_URL = "https://geodata.npolar.no/arcgis/rest/services/Basisdata_Intern?f=json"
ANTARKTIS_URL = (
    "https://geodata.npolar.no/arcgis/rest/services/Basisdata_Intern/"
    "NP_Antarktis_WMTS_3031/MapServer?f=json"
)
LOKALSTYRET_URL = (
    "https://geodata.npolar.no/arcgis/rest/services/Basisdata_Intern/"
    "NP_Lokalstyret_WMS_25833/MapServer?f=json"
)
ARCTICSDI_URL = (
    "https://geodata.npolar.no/arcgis/rest/services/ArcticSDI/"
    "ArcticSDI_NO_JAN/MapServer?f=json"
)
NPITEMA_URL = (
    "https://geodata.npolar.no/arcgis/rest/services/Temadata/"
    "F_Biogeographic_Zones_Svalbard/MapServer?f=json"
)
NPIGIS_URL = (
    "https://geodata.npolar.no/arcgis/rest/services/Basisdata/"
    "NP_Basiskart_Svalbard_WMS/MapServer?f=json"
)
NPOLAR_URL = "https://api.npolar.no/service/?q=*&format=json"
NVEGIS_URL = "https://gis3.nve.no/map/rest/services/Fjellskred1/MapServer?f=json"
NVEMAP_URL = (
    "https://gis3.nve.no/map/rest/services/Mapservices/"
    "Administrasjon2/MapServer?f=json"
)
DATASET_ID = "npiintern:NP_Antarktis_WMTS_3031"

CATALOG = {
    "currentVersion": 10.81,
    "folders": [],
    "services": [
        {"name": "Basisdata_Intern/NP_Antarktis_WMTS_3031", "type": "MapServer"},
        {"name": "Basisdata_Intern/NP_Lokalstyret_WMS_25833", "type": "MapServer"},
        {"name": "", "type": "MapServer"},
        {"name": "SkipMe", "type": ""},
        {"nested": True},
    ],
}
ANTARKTIS_BODY = {
    "mapName": "NP_Antarktis_WMTS_3031",
    "copyrightText": "Norwegian Polar Institute.",
    "layers": [
        {"id": 0, "name": "Stedsnavn_DML", "type": "Feature Layer"},
        {
            "id": 1,
            "name": "Sørpolen_p",
            "type": "Feature Layer",
            "nested": {"skip": True},
        },
        {"id": 2, "name": "GradnettBreddeIs_l", "type": "Feature Layer"},
    ],
    "spatialReference": {"wkid": 3031},
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
        if url == ANTARKTIS_URL:
            return JsonResponse(status=200, url=url, body=ANTARKTIS_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"npiintern fetch must GET, not POST {url}")


def test_printed_refs_skip_empty_name_or_type() -> None:
    source = NpiinternSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "NP_Antarktis_WMTS_3031",
        "NP_Lokalstyret_WMS_25833",
    ]
    assert [ref.source_native_uri for ref in refs] == [ANTARKTIS_URL, LOKALSTYRET_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "SkipMe" for ref in refs)


def test_printed_services_keep_document_order() -> None:
    listed = printed_services(CATALOG, LIST_URL)
    assert [ident for ident, _href, _title in listed] == [
        "NP_Antarktis_WMTS_3031",
        "NP_Lokalstyret_WMS_25833",
    ]
    assert [href for _ident, href, _title in listed] == [ANTARKTIS_URL, LOKALSTYRET_URL]


def test_printed_service_id_uses_last_path_segment() -> None:
    assert printed_service_id("NP_Lokalstyret_WMS_25833") == "NP_Lokalstyret_WMS_25833"
    assert printed_service_id("Basisdata_Intern/NP_Antarktis_WMTS_3031") == "NP_Antarktis_WMTS_3031"
    assert printed_service_id("/") is None


def test_npiintern_is_a_registered_source() -> None:
    assert "npiintern" in SOURCE_IDS
    assert "arcticsdi" in SOURCE_IDS
    assert "npitema" in SOURCE_IDS
    assert "npigis" in SOURCE_IDS
    assert "npolar" in SOURCE_IDS
    assert "nvegis" in SOURCE_IDS
    source = build_source("npiintern")
    assert isinstance(source, NpiinternSource)
    assert source.source_id == "npiintern"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = NpiinternSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "npiintern"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == ANTARKTIS_URL
    assert row["title"] == "NP_Antarktis_WMTS_3031"
    lokal = registry.get_dataset("npiintern:NP_Lokalstyret_WMS_25833")
    assert lokal is not None
    assert lokal["access_path"] == LOKALSTYRET_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("arcticsdi:")
    assert not str(row["id"]).startswith("npitema:")
    assert not str(row["id"]).startswith("npigis:")
    assert not str(row["id"]).startswith("npolar:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["npiintern_service_id"] == "NP_Antarktis_WMTS_3031"
    assert payload["npiintern_service_href"] == ANTARKTIS_URL
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_layer_names(tmp_path: Path) -> None:
    source = NpiinternSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == ANTARKTIS_URL
    assert result.table_id == "NP_Antarktis_WMTS_3031"
    assert result.http_status == 200
    assert result.counts.listed == 3
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"Stedsnavn_DML", "Sørpolen_p", "GradnettBreddeIs_l"}
    assert by_value["Sørpolen_p"]["measure"] == "name"
    dims = json.loads(by_value["Sørpolen_p"]["dimensions_json"])
    assert dims["id"] == "1"
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == ANTARKTIS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_name_or_scalar() -> None:
    cells = cells_from_npiintern(ANTARKTIS_BODY)
    assert len(cells) == 3
    measure, value, dims = cells[1]
    assert measure == "name"
    assert value == "Sørpolen_p"
    assert dims["id"] == "1"
    assert "nested" not in dims
    assert cells_from_npiintern({"folders": ["Basisdata_Intern"]}) == [
        ("value", "Basisdata_Intern", {})
    ]
    assert cells_from_npiintern({"name": "NP_Antarktis_WMTS_3031", "id": 9}) == [
        ("name", "NP_Antarktis_WMTS_3031", {"id": "9"})
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_npiintern(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_npiintern([])


def test_is_npiintern_url_accepts_only_basisdata_intern_path() -> None:
    assert is_npiintern_url(ANTARKTIS_URL)
    assert is_npiintern_url(LIST_URL)
    assert npiintern_table_id(ANTARKTIS_URL) == "NP_Antarktis_WMTS_3031"
    assert npiintern_table_id(LOKALSTYRET_URL) == "NP_Lokalstyret_WMS_25833"
    assert not is_npiintern_url(ARCTICSDI_URL)
    assert not is_npiintern_url(NPITEMA_URL)
    assert not is_npiintern_url(NPIGIS_URL)
    assert not is_npiintern_url(NPOLAR_URL)
    assert not is_npiintern_url(NVEGIS_URL)
    assert not is_npiintern_url(NVEMAP_URL)
    assert not is_npiintern_url("https://data.norge.no/datasets/x")
    assert not is_npiintern_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = NpiinternSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "NP_Antarktis_WMTS_3031"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["NP_Lokalstyret_WMS_25833"]
