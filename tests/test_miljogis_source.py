from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import classify_access_path, fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.miljogis import (
    MiljogisSource,
    cells_from_miljogis,
    is_miljogis_url,
    miljogis_table_id,
    printed_service_id,
    printed_services,
)

LIST_URL = "https://kart.miljodirektoratet.no/arcgis/rest/services?f=json"
LAKSEFISK_URL = (
    "https://kart.miljodirektoratet.no/arcgis/rest/services/anadrome_laksefisk/MapServer?f=json"
)
ARTFUNKSJON_URL = (
    "https://kart.miljodirektoratet.no/arcgis/rest/services/artfunksjon/MapServer?f=json"
)
FRILUFT_URL = (
    "https://kart.miljodirektoratet.no/arcgis/rest/services/friluftsliv_kartlagt/MapServer?f=json"
)
VANNMLJO_URL = "https://vannmiljoapi.miljodirektoratet.no/swagger/docs/v1"
NVEGIS_URL = "https://gis3.nve.no/map/rest/services/Fjellskred1/MapServer?f=json"
NAVWARNINGS_URL = "https://api.kystverket.no/data/navigationwarnings/coastal/"
HAVNEDATA_URL = "https://api.kartverket.no/havnedata/v1/havner"
DATASET_ID = "miljogis:anadrome_laksefisk"

CATALOG = {
    "currentVersion": 10.91,
    "folders": ["nin_innsyn", "Utilities"],
    "services": [
        {"name": "anadrome_laksefisk", "type": "FeatureServer"},
        {"name": "anadrome_laksefisk", "type": "MapServer"},
        {"name": "artfunksjon", "type": "MapServer"},
        {"name": "friluftsliv_kartlagt", "type": "MapServer"},
        {"name": "", "type": "MapServer"},
        {"name": "SkipMe", "type": "FeatureServer"},
        {"name": "SkipEmptyType", "type": ""},
        {"nested": True},
    ],
}
LAKSEFISK_BODY = {
    "mapName": "Layers",
    "copyrightText": "Miljødirektoratet",
    "layers": [
        {"id": 0, "name": "anadrome_vandringshinder_laks", "type": "Feature Layer"},
        {
            "id": 1,
            "name": "anadrome_vandringshinder_sjoorret",
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
        if url == LAKSEFISK_URL:
            return JsonResponse(status=200, url=url, body=LAKSEFISK_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"miljogis fetch must GET, not POST {url}")


def test_printed_refs_skip_featureserver_folders_and_empty_name() -> None:
    source = MiljogisSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "anadrome_laksefisk",
        "artfunksjon",
        "friluftsliv_kartlagt",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        LAKSEFISK_URL,
        ARTFUNKSJON_URL,
        FRILUFT_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all("nin_innsyn" not in (ref.source_native_uri or "") for ref in refs)
    assert all("Utilities" not in (ref.source_native_uri or "") for ref in refs)
    assert all("FeatureServer" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "SkipMe" for ref in refs)


def test_printed_services_keep_mapserver_document_order() -> None:
    listed = printed_services(CATALOG, LIST_URL)
    assert [ident for ident, _href, _title in listed] == [
        "anadrome_laksefisk",
        "artfunksjon",
        "friluftsliv_kartlagt",
    ]
    assert [href for _ident, href, _title in listed] == [
        LAKSEFISK_URL,
        ARTFUNKSJON_URL,
        FRILUFT_URL,
    ]


def test_printed_service_id_uses_last_path_segment() -> None:
    assert printed_service_id("anadrome_laksefisk") == "anadrome_laksefisk"
    assert printed_service_id("nin_innsyn/NiN") == "NiN"
    assert printed_service_id("/") is None


def test_miljogis_is_a_registered_source() -> None:
    assert "miljogis" in SOURCE_IDS
    assert "miljodir" in SOURCE_IDS
    assert "nvegis" in SOURCE_IDS
    assert "navwarnings" in SOURCE_IDS
    assert "havnedata" in SOURCE_IDS
    source = build_source("miljogis")
    assert isinstance(source, MiljogisSource)
    assert source.source_id == "miljogis"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = MiljogisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "miljogis"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == LAKSEFISK_URL
    assert row["title"] == "anadrome_laksefisk"
    artfunksjon = registry.get_dataset("miljogis:artfunksjon")
    assert artfunksjon is not None
    assert artfunksjon["access_path"] == ARTFUNKSJON_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("miljodir:")
    assert not str(row["id"]).startswith("nvegis:")
    assert not str(row["id"]).startswith("navwarnings:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["miljogis_service_id"] == "anadrome_laksefisk"
    assert payload["miljogis_service_href"] == LAKSEFISK_URL
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_a_mapserver_catalog_is_not_fetched_as_observations(tmp_path: Path) -> None:
    # Fetching the MapServer root once stored each layer's name as a measured
    # value. A catalog of layers is not data.
    assert classify_access_path(LAKSEFISK_URL)["kind"] == "none"

    source = MiljogisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    with pytest.raises(Exception):
        fetch_observations(
            registry,
            DATASET_ID,
            table_id="ignored",
            http=FetchHttp(),
        )
    assert registry.list_observations(DATASET_ID) == []
    registry.close()


def test_cells_copy_printed_name_or_scalar() -> None:
    cells = cells_from_miljogis(LAKSEFISK_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "anadrome_vandringshinder_laks"
    assert dims["id"] == "0"
    assert "nested" not in dims
    assert cells_from_miljogis({"folders": ["nin_innsyn"]}) == [
        ("value", "nin_innsyn", {})
    ]
    assert cells_from_miljogis({"name": "anadrome_laksefisk", "id": 9}) == [
        ("name", "anadrome_laksefisk", {"id": "9"})
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_miljogis(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_miljogis([])


def test_is_miljogis_url_accepts_only_kart_host_path() -> None:
    assert is_miljogis_url(LAKSEFISK_URL)
    assert is_miljogis_url(LIST_URL)
    assert miljogis_table_id(LAKSEFISK_URL) == "anadrome_laksefisk"
    assert miljogis_table_id(ARTFUNKSJON_URL) == "artfunksjon"
    assert not is_miljogis_url(VANNMLJO_URL)
    assert not is_miljogis_url(NVEGIS_URL)
    assert not is_miljogis_url(NAVWARNINGS_URL)
    assert not is_miljogis_url(HAVNEDATA_URL)
    assert not is_miljogis_url("https://data.norge.no/datasets/x")
    assert not is_miljogis_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = MiljogisSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "anadrome_laksefisk"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["artfunksjon"]
    assert source.list_dataset_refs(limit=1, offset=3) == []
