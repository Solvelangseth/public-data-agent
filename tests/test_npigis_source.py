from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.npigis import (
    NpigisSource,
    cells_from_npigis,
    is_npigis_url,
    npigis_table_id,
    printed_service_id,
    printed_services,
)

LIST_URL = "https://geodata.npolar.no/arcgis/rest/services/Basisdata?f=json"
SVALBARD_URL = (
    "https://geodata.npolar.no/arcgis/rest/services/Basisdata/"
    "NP_Basiskart_Svalbard_WMS/MapServer?f=json"
)
JANMAYEN_URL = (
    "https://geodata.npolar.no/arcgis/rest/services/Basisdata/"
    "NP_Basiskart_JanMayen_WMS/MapServer?f=json"
)
FKB_URL = (
    "https://geodata.npolar.no/arcgis/rest/services/Basisdata/"
    "FKB_Svalbard_WMTS_25833/MapServer?f=json"
)
ORTO_URL = (
    "https://geodata.npolar.no/arcgis/rest/services/Basisdata/"
    "NP_Ortofoto_Svalbard_WMTS_25833/MapServer?f=json"
)
SAT_URL = (
    "https://geodata.npolar.no/arcgis/rest/services/Basisdata/"
    "NP_Satellitt_Svalbard_WMTS_25833/MapServer?f=json"
)
NPOLAR_URL = "https://api.npolar.no/service/?q=*&format=json"
NVEGIS_URL = "https://gis3.nve.no/map/rest/services/Fjellskred1/MapServer?f=json"
HAVNEDATA_URL = "https://ogcapitest.kartverket.no/rest/services/havnedata3_0/collections"
DATASET_ID = "npigis:NP_Basiskart_Svalbard_WMS"

CATALOG = {
    "currentVersion": 10.81,
    "folders": [],
    "services": [
        {"name": "Basisdata/NP_Basiskart_Svalbard_WMS", "type": "MapServer"},
        {"name": "Basisdata/NP_Basiskart_JanMayen_WMS", "type": "MapServer"},
        {"name": "Basisdata/FKB_Svalbard_WMTS_25833", "type": "MapServer"},
        {"name": "Basisdata/NP_Ortofoto_Svalbard_WMTS_25833", "type": "MapServer"},
        {"name": "Basisdata/NP_Satellitt_Svalbard_WMTS_25833", "type": "MapServer"},
        {"name": "", "type": "MapServer"},
        {"name": "SkipMe", "type": ""},
        {"nested": True},
    ],
}
SVALBARD_BODY = {
    "mapName": "NP_Basiskart_Svalbard_WMS",
    "copyrightText": "Norsk Polarinstitutt",
    "layers": [
        {"id": 0, "name": "Kystkontur", "type": "Feature Layer"},
        {
            "id": 1,
            "name": "Isbreer",
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
        if url == SVALBARD_URL:
            return JsonResponse(status=200, url=url, body=SVALBARD_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"npigis fetch must GET, not POST {url}")


def test_printed_refs_skip_empty_name_or_type() -> None:
    source = NpigisSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "NP_Basiskart_Svalbard_WMS",
        "NP_Basiskart_JanMayen_WMS",
        "FKB_Svalbard_WMTS_25833",
        "NP_Ortofoto_Svalbard_WMTS_25833",
        "NP_Satellitt_Svalbard_WMTS_25833",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        SVALBARD_URL,
        JANMAYEN_URL,
        FKB_URL,
        ORTO_URL,
        SAT_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "SkipMe" for ref in refs)


def test_printed_services_keep_document_order() -> None:
    listed = printed_services(CATALOG, LIST_URL)
    assert [ident for ident, _href, _title in listed] == [
        "NP_Basiskart_Svalbard_WMS",
        "NP_Basiskart_JanMayen_WMS",
        "FKB_Svalbard_WMTS_25833",
        "NP_Ortofoto_Svalbard_WMTS_25833",
        "NP_Satellitt_Svalbard_WMTS_25833",
    ]
    assert [href for _ident, href, _title in listed] == [
        SVALBARD_URL,
        JANMAYEN_URL,
        FKB_URL,
        ORTO_URL,
        SAT_URL,
    ]


def test_printed_service_id_uses_last_path_segment() -> None:
    assert printed_service_id("NP_Basiskart_Svalbard_WMS") == "NP_Basiskart_Svalbard_WMS"
    assert printed_service_id("Basisdata/NP_Basiskart_JanMayen_WMS") == (
        "NP_Basiskart_JanMayen_WMS"
    )
    assert printed_service_id("/") is None


def test_npigis_is_a_registered_source() -> None:
    assert "npigis" in SOURCE_IDS
    assert "npolar" in SOURCE_IDS
    assert "nvegis" in SOURCE_IDS
    assert "havnedata" in SOURCE_IDS
    assert "miljogis" in SOURCE_IDS
    assert "hoydegis" in SOURCE_IDS
    source = build_source("npigis")
    assert isinstance(source, NpigisSource)
    assert source.source_id == "npigis"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = NpigisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 5
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "npigis"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == SVALBARD_URL
    assert row["title"] == "NP_Basiskart_Svalbard_WMS"
    janmayen = registry.get_dataset("npigis:NP_Basiskart_JanMayen_WMS")
    assert janmayen is not None
    assert janmayen["access_path"] == JANMAYEN_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("npolar:")
    assert not str(row["id"]).startswith("nvegis:")
    assert not str(row["id"]).startswith("havnedata:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["npigis_service_id"] == "NP_Basiskart_Svalbard_WMS"
    assert payload["npigis_service_href"] == SVALBARD_URL
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_layer_names(tmp_path: Path) -> None:
    source = NpigisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == SVALBARD_URL
    assert result.table_id == "NP_Basiskart_Svalbard_WMS"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"Kystkontur", "Isbreer"}
    assert by_value["Kystkontur"]["measure"] == "name"
    dims = json.loads(by_value["Kystkontur"]["dimensions_json"])
    assert dims["id"] == "0"
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == SVALBARD_URL for row in rows)
    registry.close()


def test_cells_copy_printed_name_or_scalar() -> None:
    cells = cells_from_npigis(SVALBARD_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "Kystkontur"
    assert dims["id"] == "0"
    assert "nested" not in dims
    assert cells_from_npigis({"folders": ["ArcticSDI"]}) == [
        ("value", "ArcticSDI", {})
    ]
    assert cells_from_npigis({"name": "NP_Basiskart_Svalbard_WMS", "id": 9}) == [
        ("name", "NP_Basiskart_Svalbard_WMS", {"id": "9"})
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_npigis(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_npigis([])


def test_is_npigis_url_accepts_only_geodata_host_path() -> None:
    assert is_npigis_url(SVALBARD_URL)
    assert is_npigis_url(LIST_URL)
    assert npigis_table_id(SVALBARD_URL) == "NP_Basiskart_Svalbard_WMS"
    assert npigis_table_id(JANMAYEN_URL) == "NP_Basiskart_JanMayen_WMS"
    assert not is_npigis_url(NPOLAR_URL)
    assert not is_npigis_url(NVEGIS_URL)
    assert not is_npigis_url(HAVNEDATA_URL)
    assert not is_npigis_url("https://data.norge.no/datasets/x")
    assert not is_npigis_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = NpigisSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "NP_Basiskart_Svalbard_WMS"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["NP_Basiskart_JanMayen_WMS"]
