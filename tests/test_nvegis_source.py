from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.nvegis import (
    NvegisSource,
    cells_from_nvegis,
    is_nvegis_url,
    nvegis_table_id,
    printed_service_id,
    printed_services,
)

LIST_URL = "https://gis3.nve.no/map/rest/services?f=json"
FJELLSKRED_URL = "https://gis3.nve.no/map/rest/services/Fjellskred1/MapServer?f=json"
NETTANLEGG_URL = "https://gis3.nve.no/map/rest/services/Nettanlegg3/MapServer?f=json"
SKREDFARE_URL = "https://gis3.nve.no/map/rest/services/Skredfaresoner3/MapServer?f=json"
SNOSKRED_LOM_URL = (
    "https://gis3.nve.no/map/rest/services/SnoskredAktsomhetLosneOmr/MapServer?f=json"
)
SNOSKRED_URL = "https://gis3.nve.no/map/rest/services/SnoskredAktsomhet/MapServer?f=json"
MAGASIN_URL = "https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk"
HITILES_URL = "https://kart.hi.no/data/ogc/tiles/v1/tileMatrixSets?f=application%2Fjson"
MILJORAPPORTER_URL = "https://api.fiskeridir.no/miljorapporter-api/api/v1/env-reports"
DATASET_ID = "nvegis:Fjellskred1"

CATALOG = {
    "currentVersion": 10.91,
    "folders": ["Mapservices", "Utilities"],
    "services": [
        {"name": "Fjellskred1", "type": "MapServer"},
        {"name": "Nettanlegg3", "type": "MapServer"},
        {"name": "Skredfaresoner3", "type": "MapServer"},
        {"name": "SnoskredAktsomhetLosneOmr", "type": "MapServer"},
        {"name": "SnoskredAktsomhet", "type": "MapServer"},
        {"name": "", "type": "MapServer"},
        {"name": "SkipMe", "type": ""},
        {"nested": True},
    ],
}
FJELLSKRED_BODY = {
    "mapName": "Fjellskred1",
    "copyrightText": "",
    "layers": [
        {"id": 1, "name": "Overvaking_hovedpunkt", "type": "Feature Layer"},
        {
            "id": 4,
            "name": "Ustabilt_fjellparti_hovedpunkt",
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
        if url == FJELLSKRED_URL:
            return JsonResponse(status=200, url=url, body=FJELLSKRED_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nvegis fetch must GET, not POST {url}")


def test_printed_refs_skip_folders_and_empty_name_or_type() -> None:
    source = NvegisSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "Fjellskred1",
        "Nettanlegg3",
        "Skredfaresoner3",
        "SnoskredAktsomhetLosneOmr",
        "SnoskredAktsomhet",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        FJELLSKRED_URL,
        NETTANLEGG_URL,
        SKREDFARE_URL,
        SNOSKRED_LOM_URL,
        SNOSKRED_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all("Mapservices" not in (ref.source_native_uri or "") for ref in refs)
    assert all("Utilities" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "SkipMe" for ref in refs)


def test_printed_services_keep_document_order() -> None:
    listed = printed_services(CATALOG, LIST_URL)
    assert [ident for ident, _href, _title in listed] == [
        "Fjellskred1",
        "Nettanlegg3",
        "Skredfaresoner3",
        "SnoskredAktsomhetLosneOmr",
        "SnoskredAktsomhet",
    ]
    assert [href for _ident, href, _title in listed] == [
        FJELLSKRED_URL,
        NETTANLEGG_URL,
        SKREDFARE_URL,
        SNOSKRED_LOM_URL,
        SNOSKRED_URL,
    ]


def test_printed_service_id_uses_last_path_segment() -> None:
    assert printed_service_id("Fjellskred1") == "Fjellskred1"
    assert printed_service_id("Mapservices/Administrasjon2") == "Administrasjon2"
    assert printed_service_id("/") is None


def test_nvegis_is_a_registered_source() -> None:
    assert "nvegis" in SOURCE_IDS
    assert "nve" in SOURCE_IDS
    assert "hitiles" in SOURCE_IDS
    assert "miljorapporter" in SOURCE_IDS
    source = build_source("nvegis")
    assert isinstance(source, NvegisSource)
    assert source.source_id == "nvegis"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = NvegisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 5
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nvegis"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == FJELLSKRED_URL
    assert row["title"] == "Fjellskred1"
    nettanlegg = registry.get_dataset("nvegis:Nettanlegg3")
    assert nettanlegg is not None
    assert nettanlegg["access_path"] == NETTANLEGG_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("nve:")
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("hitiles:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["nvegis_service_id"] == "Fjellskred1"
    assert payload["nvegis_service_href"] == FJELLSKRED_URL
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_layer_names(tmp_path: Path) -> None:
    source = NvegisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == FJELLSKRED_URL
    assert result.table_id == "Fjellskred1"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"Overvaking_hovedpunkt", "Ustabilt_fjellparti_hovedpunkt"}
    assert by_value["Overvaking_hovedpunkt"]["measure"] == "name"
    dims = json.loads(by_value["Overvaking_hovedpunkt"]["dimensions_json"])
    assert dims["id"] == "1"
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == FJELLSKRED_URL for row in rows)
    registry.close()


def test_cells_copy_printed_name_or_scalar() -> None:
    cells = cells_from_nvegis(FJELLSKRED_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "Overvaking_hovedpunkt"
    assert dims["id"] == "1"
    assert "nested" not in dims
    assert cells_from_nvegis({"folders": ["Mapservices"]}) == [
        ("value", "Mapservices", {})
    ]
    assert cells_from_nvegis({"name": "Fjellskred1", "id": 9}) == [
        ("name", "Fjellskred1", {"id": "9"})
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_nvegis(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_nvegis([])


def test_is_nvegis_url_accepts_only_gis3_host_path() -> None:
    assert is_nvegis_url(FJELLSKRED_URL)
    assert is_nvegis_url(LIST_URL)
    assert nvegis_table_id(FJELLSKRED_URL) == "Fjellskred1"
    assert nvegis_table_id(NETTANLEGG_URL) == "Nettanlegg3"
    assert not is_nvegis_url(MAGASIN_URL)
    assert not is_nvegis_url(HITILES_URL)
    assert not is_nvegis_url(MILJORAPPORTER_URL)
    assert not is_nvegis_url("https://data.norge.no/datasets/x")
    assert not is_nvegis_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = NvegisSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "Fjellskred1"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["Nettanlegg3"]
