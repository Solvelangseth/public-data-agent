from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.fiskerigis import (
    FiskerigisSource,
    cells_from_fiskerigis,
    fiskerigis_table_id,
    is_fiskerigis_url,
    printed_service_id,
    printed_services,
)

LIST_URL = "https://gis.fiskeridir.no/arcgis/rest/services?f=json"
AIS_URL = "https://gis.fiskeridir.no/arcgis/rest/services/AIS_density_Norge_2016/MapServer?f=json"
ROUTE_URL = "https://gis.fiskeridir.no/arcgis/rest/services/AIS_Route_Density_2020/MapServer?f=json"
OECM_URL = "https://gis.fiskeridir.no/arcgis/rest/services/Beregning_OECM_Norge/MapServer?f=json"
VESSEL_URL = "https://api.fiskeridir.no/vessel-api/api/vessel"
NVEGIS_URL = "https://gis3.nve.no/map/rest/services/Fjellskred1/MapServer?f=json"
NVEMAP_URL = "https://gis3.nve.no/map/rest/services/Mapservices/Administrasjon2/MapServer?f=json"
HOYDEGIS_URL = "https://hoydedata.no/arcgis/rest/services/DTM/ImageServer?f=json"
ARCTICSDI_URL = "https://geodata.npolar.no/arcgis/rest/services/ArcticSDI/ArcticSDI_NO_JAN/MapServer?f=json"
DATASET_ID = "fiskerigis:AIS_density_Norge_2016"

CATALOG = {
    "currentVersion": 10.91,
    "folders": ["Utilities", "Yggdrasil"],
    "services": [
        {"name": "AIS_density_Norge_2016", "type": "MapServer"},
        {"name": "AIS_Route_Density_2020", "type": "MapServer"},
        {"name": "Beregning_OECM_Norge", "type": "MapServer"},
        {"name": "", "type": "MapServer"},
        {"name": "SkipEmptyType", "type": ""},
        {"nested": True},
    ],
}
AIS_BODY = {
    "mapName": "Layers",
    "layers": [
        {
            "id": 0,
            "name": "AIS density Norge 2016",
            "type": "Raster Layer",
            "nested": {"skip": True},
        },
        {"id": 1, "name": "AIS density overlay", "type": "Feature Layer"},
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
        if url == AIS_URL:
            return JsonResponse(status=200, url=url, body=AIS_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"fiskerigis fetch must GET, not POST {url}")


def test_printed_refs_skip_folders_and_empty_name() -> None:
    source = FiskerigisSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "AIS_density_Norge_2016",
        "AIS_Route_Density_2020",
        "Beregning_OECM_Norge",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        AIS_URL,
        ROUTE_URL,
        OECM_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all("Utilities" not in (ref.source_native_uri or "") for ref in refs)
    assert all("Yggdrasil" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "SkipEmptyType" for ref in refs)


def test_printed_services_keep_document_order_and_type() -> None:
    listed = printed_services(CATALOG, LIST_URL)
    assert [ident for ident, _href, _title in listed] == [
        "AIS_density_Norge_2016",
        "AIS_Route_Density_2020",
        "Beregning_OECM_Norge",
    ]
    assert [href for _ident, href, _title in listed] == [
        AIS_URL,
        ROUTE_URL,
        OECM_URL,
    ]


def test_printed_service_id_uses_last_path_segment() -> None:
    assert printed_service_id("AIS_density_Norge_2016") == "AIS_density_Norge_2016"
    assert printed_service_id("Yggdrasil/AIS_density_Norge_2016") == "AIS_density_Norge_2016"
    assert printed_service_id("/") is None


def test_fiskerigis_is_a_registered_source() -> None:
    assert "fiskerigis" in SOURCE_IDS
    assert "fiskeridir" in SOURCE_IDS
    assert "nvemap" in SOURCE_IDS
    assert "arcticsdi" in SOURCE_IDS
    assert "hoydegis" in SOURCE_IDS
    source = build_source("fiskerigis")
    assert isinstance(source, FiskerigisSource)
    assert source.source_id == "fiskerigis"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = FiskerigisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "fiskerigis"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == AIS_URL
    assert row["title"] == "AIS_density_Norge_2016"
    route = registry.get_dataset("fiskerigis:AIS_Route_Density_2020")
    assert route is not None
    assert route["access_path"] == ROUTE_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("fiskeridir:")
    assert not str(row["id"]).startswith("nvemap:")
    assert not str(row["id"]).startswith("hoydegis:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["fiskerigis_service_id"] == "AIS_density_Norge_2016"
    assert payload["fiskerigis_service_href"] == AIS_URL
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_layer_names(tmp_path: Path) -> None:
    source = FiskerigisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == AIS_URL
    assert result.table_id == "AIS_density_Norge_2016"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    assert len(rows) == 2
    values = {json.loads(row["value_json"]) for row in rows}
    assert values == {"AIS density Norge 2016", "AIS density overlay"}
    assert all(row["measure"] == "name" for row in rows)
    dims_by_value = {
        json.loads(row["value_json"]): json.loads(row["dimensions_json"]) for row in rows
    }
    assert dims_by_value["AIS density Norge 2016"]["id"] == "0"
    assert dims_by_value["AIS density Norge 2016"]["type"] == "Raster Layer"
    assert "nested" not in dims_by_value["AIS density Norge 2016"]
    assert "extent" not in dims_by_value["AIS density Norge 2016"]
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == AIS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_name_or_scalar() -> None:
    cells = cells_from_fiskerigis(AIS_BODY)
    assert cells == [
        ("name", "AIS density Norge 2016", {"id": "0", "type": "Raster Layer"}),
        ("name", "AIS density overlay", {"id": "1", "type": "Feature Layer"}),
    ]
    assert cells_from_fiskerigis({"folders": ["Utilities"]}) == [
        ("value", "Utilities", {})
    ]
    assert cells_from_fiskerigis({"name": "AIS_density_Norge_2016", "id": 9}) == [
        ("name", "AIS_density_Norge_2016", {"id": "9"})
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_fiskerigis(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_fiskerigis([])


def test_is_fiskerigis_url_accepts_only_gis_host_path() -> None:
    assert is_fiskerigis_url(AIS_URL)
    assert is_fiskerigis_url(LIST_URL)
    assert fiskerigis_table_id(AIS_URL) == "AIS_density_Norge_2016"
    assert fiskerigis_table_id(ROUTE_URL) == "AIS_Route_Density_2020"
    assert not is_fiskerigis_url(VESSEL_URL)
    assert not is_fiskerigis_url(NVEGIS_URL)
    assert not is_fiskerigis_url(NVEMAP_URL)
    assert not is_fiskerigis_url(HOYDEGIS_URL)
    assert not is_fiskerigis_url(ARCTICSDI_URL)
    assert not is_fiskerigis_url("https://data.norge.no/datasets/x")
    assert not is_fiskerigis_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = FiskerigisSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "AIS_density_Norge_2016"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["AIS_Route_Density_2020"]
    assert source.list_dataset_refs(limit=1, offset=3) == []
