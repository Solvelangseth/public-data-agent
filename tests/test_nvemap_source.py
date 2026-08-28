from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.nvemap import (
    NvemapSource,
    cells_from_nvemap,
    is_nvemap_url,
    nvemap_table_id,
    printed_service_id,
    printed_services,
)

LIST_URL = "https://gis3.nve.no/map/rest/services/Mapservices?f=json"
ADM2_URL = "https://gis3.nve.no/map/rest/services/Mapservices/Administrasjon2/MapServer?f=json"
ADM_URL = "https://gis3.nve.no/map/rest/services/Mapservices/Administrasjon/MapServer?f=json"
FKB_URL = "https://gis3.nve.no/map/rest/services/Mapservices/FKB/MapServer?f=json"
NVE_URL = "https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk/HentManedlig"
NVEGIS_URL = "https://gis3.nve.no/map/rest/services/Fjellskred1/MapServer?f=json"
NVE2GIS_URL = "https://gis2.nve.no/arcgis/rest/services/mapservice/AlphaBeta/MapServer?f=json"
NPITEMA_URL = "https://geodata.npolar.no/arcgis/rest/services/Temadata/F_Reinsdyrhabitat/MapServer?f=json"
DATASET_ID = "nvemap:Administrasjon2"

CATALOG = {
    "currentVersion": 10.91,
    "folders": ["Utilities"],
    "services": [
        {"name": "Mapservices/Administrasjon2", "type": "MapServer"},
        {"name": "Mapservices/Administrasjon", "type": "MapServer"},
        {"name": "Mapservices/FKB", "type": "MapServer"},
        {"name": "", "type": "MapServer"},
        {"name": "Mapservices/SkipEmptyType", "type": ""},
        {"nested": True},
    ],
}
ADM2_BODY = {
    "mapName": "Layers",
    "layers": [
        {"id": 0, "name": "NVE Region", "type": "Feature Layer", "nested": {"skip": True}},
        {"id": 1, "name": "NVEs kontorsteder", "type": "Feature Layer"},
    ],
    "extent": {"xmin": 0},
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
        if url == ADM2_URL:
            return JsonResponse(status=200, url=url, body=ADM2_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nvemap fetch must GET, not POST {url}")


def test_printed_refs_skip_folders_and_empty_name() -> None:
    source = NvemapSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "Administrasjon2",
        "Administrasjon",
        "FKB",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        ADM2_URL,
        ADM_URL,
        FKB_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all("Utilities" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "SkipEmptyType" for ref in refs)


def test_printed_services_keep_document_order_and_type() -> None:
    listed = printed_services(CATALOG, LIST_URL)
    assert [ident for ident, _href, _title in listed] == [
        "Administrasjon2",
        "Administrasjon",
        "FKB",
    ]
    assert [href for _ident, href, _title in listed] == [
        ADM2_URL,
        ADM_URL,
        FKB_URL,
    ]


def test_printed_service_id_uses_last_path_segment() -> None:
    assert printed_service_id("Mapservices/Administrasjon2") == "Administrasjon2"
    assert printed_service_id("Administrasjon2") == "Administrasjon2"
    assert printed_service_id("/") is None


def test_nvemap_is_a_registered_source() -> None:
    assert "nvemap" in SOURCE_IDS
    assert "nve" in SOURCE_IDS
    assert "nvegis" in SOURCE_IDS
    assert "nve2gis" in SOURCE_IDS
    source = build_source("nvemap")
    assert isinstance(source, NvemapSource)
    assert source.source_id == "nvemap"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = NvemapSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nvemap"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == ADM2_URL
    assert row["title"] == "Administrasjon2"
    adm = registry.get_dataset("nvemap:Administrasjon")
    assert adm is not None
    assert adm["access_path"] == ADM_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("nvegis:")
    assert not str(row["id"]).startswith("nve:")
    assert not str(row["id"]).startswith("nve2gis:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["nvemap_service_id"] == "Administrasjon2"
    assert payload["nvemap_service_href"] == ADM2_URL
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_layer_names(tmp_path: Path) -> None:
    source = NvemapSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == ADM2_URL
    assert result.table_id == "Administrasjon2"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    assert len(rows) == 2
    values = {json.loads(row["value_json"]) for row in rows}
    assert values == {"NVE Region", "NVEs kontorsteder"}
    assert all(row["measure"] == "name" for row in rows)
    dims_by_value = {
        json.loads(row["value_json"]): json.loads(row["dimensions_json"]) for row in rows
    }
    assert dims_by_value["NVE Region"]["id"] == "0"
    assert dims_by_value["NVE Region"]["type"] == "Feature Layer"
    assert "nested" not in dims_by_value["NVE Region"]
    assert "extent" not in dims_by_value["NVE Region"]
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == ADM2_URL for row in rows)
    registry.close()


def test_cells_copy_printed_name_or_scalar() -> None:
    cells = cells_from_nvemap(ADM2_BODY)
    assert cells == [
        ("name", "NVE Region", {"id": "0", "type": "Feature Layer"}),
        ("name", "NVEs kontorsteder", {"id": "1", "type": "Feature Layer"}),
    ]
    assert cells_from_nvemap({"folders": ["Utilities"]}) == [
        ("value", "Utilities", {})
    ]
    assert cells_from_nvemap({"name": "Administrasjon2", "id": 9}) == [
        ("name", "Administrasjon2", {"id": "9"})
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_nvemap(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_nvemap([])


def test_is_nvemap_url_accepts_only_mapservices_path() -> None:
    assert is_nvemap_url(ADM2_URL)
    assert is_nvemap_url(LIST_URL)
    assert nvemap_table_id(ADM2_URL) == "Administrasjon2"
    assert nvemap_table_id(ADM_URL) == "Administrasjon"
    assert not is_nvemap_url(NVE_URL)
    assert not is_nvemap_url(NVEGIS_URL)
    assert not is_nvemap_url(NVE2GIS_URL)
    assert not is_nvemap_url(NPITEMA_URL)
    assert not is_nvemap_url("https://data.norge.no/datasets/x")
    assert not is_nvemap_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = NvemapSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "Administrasjon2"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["Administrasjon"]
    assert source.list_dataset_refs(limit=1, offset=3) == []
