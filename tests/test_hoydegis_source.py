from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.hoydegis import (
    HoydegisSource,
    cells_from_hoydegis,
    hoydegis_table_id,
    is_hoydegis_url,
    printed_service_id,
    printed_services,
)

LIST_URL = "https://hoydedata.no/arcgis/rest/services?f=json"
AREAL_URL = "https://hoydedata.no/arcgis/rest/services/Arealstatistikk/MapServer?f=json"
DTM_URL = "https://hoydedata.no/arcgis/rest/services/DTM/ImageServer?f=json"
CONVERT_URL = "https://hoydedata.no/arcgis/rest/services/ConvertSosi/MapServer?f=json"
HOYDEDATA_URL = "https://ws.geonorge.no/hoydedata/v1/datakilder"
MILJOGIS_URL = "https://kart.miljodirektoratet.no/arcgis/rest/services/anadrome_laksefisk/MapServer?f=json"
NVEGIS_URL = "https://gis3.nve.no/map/rest/services/Fjellskred1/MapServer?f=json"
DATASET_ID = "hoydegis:DTM"

CATALOG = {
    "currentVersion": 11.1,
    "folders": ["Utilities"],
    "services": [
        {"name": "Arealstatistikk", "type": "MapServer"},
        {"name": "ConvertSosi", "type": "MapServer"},
        {"name": "DTM", "type": "ImageServer"},
        {"name": "", "type": "MapServer"},
        {"name": "SkipEmptyType", "type": ""},
        {"nested": True},
    ],
}
DTM_BODY = {
    "name": "DTM",
    "description": "Nasjonal høydemodell",
    "bandCount": 1,
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
        if url == DTM_URL:
            return JsonResponse(status=200, url=url, body=DTM_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"hoydegis fetch must GET, not POST {url}")


def test_printed_refs_skip_folders_and_empty_name() -> None:
    source = HoydegisSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "Arealstatistikk",
        "ConvertSosi",
        "DTM",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        AREAL_URL,
        CONVERT_URL,
        DTM_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all("Utilities" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "SkipEmptyType" for ref in refs)


def test_printed_services_keep_document_order_and_type() -> None:
    listed = printed_services(CATALOG, LIST_URL)
    assert [ident for ident, _href, _title in listed] == [
        "Arealstatistikk",
        "ConvertSosi",
        "DTM",
    ]
    assert [href for _ident, href, _title in listed] == [
        AREAL_URL,
        CONVERT_URL,
        DTM_URL,
    ]


def test_printed_service_id_uses_last_path_segment() -> None:
    assert printed_service_id("Arealstatistikk") == "Arealstatistikk"
    assert printed_service_id("Basisdata/DTM") == "DTM"
    assert printed_service_id("/") is None


def test_hoydegis_is_a_registered_source() -> None:
    assert "hoydegis" in SOURCE_IDS
    assert "hoydedata" in SOURCE_IDS
    assert "miljogis" in SOURCE_IDS
    assert "nvegis" in SOURCE_IDS
    source = build_source("hoydegis")
    assert isinstance(source, HoydegisSource)
    assert source.source_id == "hoydegis"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = HoydegisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "hoydegis"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == DTM_URL
    assert row["title"] == "DTM"
    areal = registry.get_dataset("hoydegis:Arealstatistikk")
    assert areal is not None
    assert areal["access_path"] == AREAL_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("hoydedata:")
    assert not str(row["id"]).startswith("miljogis:")
    assert not str(row["id"]).startswith("nvegis:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["hoydegis_service_id"] == "DTM"
    assert payload["hoydegis_service_href"] == DTM_URL
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_service_name(tmp_path: Path) -> None:
    source = HoydegisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == DTM_URL
    assert result.table_id == "DTM"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    assert len(rows) == 1
    assert json.loads(rows[0]["value_json"]) == "DTM"
    assert rows[0]["measure"] == "name"
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["description"] == "Nasjonal høydemodell"
    assert dims["bandCount"] == "1"
    assert "extent" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == DTM_URL for row in rows)
    registry.close()


def test_cells_copy_printed_name_or_scalar() -> None:
    cells = cells_from_hoydegis(DTM_BODY)
    assert len(cells) == 1
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "DTM"
    assert dims["bandCount"] == "1"
    assert "extent" not in dims
    assert cells_from_hoydegis({"folders": ["Utilities"]}) == [
        ("value", "Utilities", {})
    ]
    assert cells_from_hoydegis({"name": "Arealstatistikk", "id": 9}) == [
        ("name", "Arealstatistikk", {"id": "9"})
    ]
    assert cells_from_hoydegis(
        {
            "mapName": "Layers",
            "layers": [
                {"id": 0, "name": "Flystriper", "nested": {"skip": True}},
            ],
        }
    ) == [("name", "Flystriper", {"id": "0"})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_hoydegis(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_hoydegis([])


def test_is_hoydegis_url_accepts_only_hoydedata_host_path() -> None:
    assert is_hoydegis_url(DTM_URL)
    assert is_hoydegis_url(LIST_URL)
    assert hoydegis_table_id(DTM_URL) == "DTM"
    assert hoydegis_table_id(AREAL_URL) == "Arealstatistikk"
    assert not is_hoydegis_url(HOYDEDATA_URL)
    assert not is_hoydegis_url(MILJOGIS_URL)
    assert not is_hoydegis_url(NVEGIS_URL)
    assert not is_hoydegis_url("https://data.norge.no/datasets/x")
    assert not is_hoydegis_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = HoydegisSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "Arealstatistikk"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["ConvertSosi"]
    assert source.list_dataset_refs(limit=1, offset=3) == []
