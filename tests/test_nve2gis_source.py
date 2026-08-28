from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.nve2gis import (
    Nve2gisSource,
    cells_from_nve2gis,
    is_nve2gis_url,
    nve2gis_table_id,
    printed_service_id,
    printed_services,
)

LIST_URL = "https://gis2.nve.no/arcgis/rest/services/mapservice?f=json"
ALPHA_URL = "https://gis2.nve.no/arcgis/rest/services/mapservice/AlphaBeta/MapServer?f=json"
NGU_URL = "https://gis2.nve.no/arcgis/rest/services/mapservice/NGUFjellskred/MapServer?f=json"
SOLKRAFT_URL = "https://gis2.nve.no/arcgis/rest/services/mapservice/Solkraft/MapServer?f=json"
NVE_URL = "https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk/HentManedlig"
NVEGIS_URL = "https://gis3.nve.no/map/rest/services/Fjellskred1/MapServer?f=json"
HOYDEGIS_URL = "https://hoydedata.no/arcgis/rest/services/DTM/ImageServer?f=json"
DATASET_ID = "nve2gis:AlphaBeta"

CATALOG = {
    "currentVersion": 11.5,
    "folders": ["Utilities"],
    "services": [
        {"name": "mapservice/AlphaBeta", "type": "MapServer"},
        {"name": "mapservice/NGUFjellskred", "type": "MapServer"},
        {"name": "mapservice/Solkraft", "type": "MapServer"},
        {"name": "", "type": "MapServer"},
        {"name": "mapservice/SkipEmptyType", "type": ""},
        {"nested": True},
    ],
}
ALPHA_BODY = {
    "mapName": "Layers",
    "layers": [
        {"id": 0, "name": "Utlopspunkt", "type": "Feature Layer", "nested": {"skip": True}},
        {"id": 1, "name": "Banepunkt", "type": "Feature Layer"},
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
        if url == ALPHA_URL:
            return JsonResponse(status=200, url=url, body=ALPHA_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nve2gis fetch must GET, not POST {url}")


def test_printed_refs_skip_folders_and_empty_name() -> None:
    source = Nve2gisSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "AlphaBeta",
        "NGUFjellskred",
        "Solkraft",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        ALPHA_URL,
        NGU_URL,
        SOLKRAFT_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all("Utilities" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "SkipEmptyType" for ref in refs)


def test_printed_services_keep_document_order_and_type() -> None:
    listed = printed_services(CATALOG, LIST_URL)
    assert [ident for ident, _href, _title in listed] == [
        "AlphaBeta",
        "NGUFjellskred",
        "Solkraft",
    ]
    assert [href for _ident, href, _title in listed] == [
        ALPHA_URL,
        NGU_URL,
        SOLKRAFT_URL,
    ]


def test_printed_service_id_uses_last_path_segment() -> None:
    assert printed_service_id("mapservice/AlphaBeta") == "AlphaBeta"
    assert printed_service_id("AlphaBeta") == "AlphaBeta"
    assert printed_service_id("/") is None


def test_nve2gis_is_a_registered_source() -> None:
    assert "nve2gis" in SOURCE_IDS
    assert "nve" in SOURCE_IDS
    assert "nvegis" in SOURCE_IDS
    assert "hoydegis" in SOURCE_IDS
    source = build_source("nve2gis")
    assert isinstance(source, Nve2gisSource)
    assert source.source_id == "nve2gis"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = Nve2gisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nve2gis"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == ALPHA_URL
    assert row["title"] == "AlphaBeta"
    ngu = registry.get_dataset("nve2gis:NGUFjellskred")
    assert ngu is not None
    assert ngu["access_path"] == NGU_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("nvegis:")
    assert not str(row["id"]).startswith("nve:")
    assert not str(row["id"]).startswith("hoydegis:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["nve2gis_service_id"] == "AlphaBeta"
    assert payload["nve2gis_service_href"] == ALPHA_URL
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_layer_names(tmp_path: Path) -> None:
    source = Nve2gisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == ALPHA_URL
    assert result.table_id == "AlphaBeta"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    assert len(rows) == 2
    values = {json.loads(row["value_json"]) for row in rows}
    assert values == {"Utlopspunkt", "Banepunkt"}
    assert all(row["measure"] == "name" for row in rows)
    dims_by_value = {
        json.loads(row["value_json"]): json.loads(row["dimensions_json"]) for row in rows
    }
    assert dims_by_value["Utlopspunkt"]["id"] == "0"
    assert dims_by_value["Utlopspunkt"]["type"] == "Feature Layer"
    assert "nested" not in dims_by_value["Utlopspunkt"]
    assert "extent" not in dims_by_value["Utlopspunkt"]
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == ALPHA_URL for row in rows)
    registry.close()


def test_cells_copy_printed_name_or_scalar() -> None:
    cells = cells_from_nve2gis(ALPHA_BODY)
    assert cells == [
        ("name", "Utlopspunkt", {"id": "0", "type": "Feature Layer"}),
        ("name", "Banepunkt", {"id": "1", "type": "Feature Layer"}),
    ]
    assert cells_from_nve2gis({"folders": ["Utilities"]}) == [
        ("value", "Utilities", {})
    ]
    assert cells_from_nve2gis({"name": "AlphaBeta", "id": 9}) == [
        ("name", "AlphaBeta", {"id": "9"})
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_nve2gis(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_nve2gis([])


def test_is_nve2gis_url_accepts_only_gis2_host_path() -> None:
    assert is_nve2gis_url(ALPHA_URL)
    assert is_nve2gis_url(LIST_URL)
    assert nve2gis_table_id(ALPHA_URL) == "AlphaBeta"
    assert nve2gis_table_id(NGU_URL) == "NGUFjellskred"
    assert not is_nve2gis_url(NVE_URL)
    assert not is_nve2gis_url(NVEGIS_URL)
    assert not is_nve2gis_url(HOYDEGIS_URL)
    assert not is_nve2gis_url("https://data.norge.no/datasets/x")
    assert not is_nve2gis_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = Nve2gisSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "AlphaBeta"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["NGUFjellskred"]
    assert source.list_dataset_refs(limit=1, offset=3) == []
