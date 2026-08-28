from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.arcticsdi import (
    ArcticsdiSource,
    arcticsdi_table_id,
    cells_from_arcticsdi,
    is_arcticsdi_url,
    printed_service_id,
    printed_services,
)

LIST_URL = "https://geodata.npolar.no/arcgis/rest/services/ArcticSDI?f=json"
JAN_URL = (
    "https://geodata.npolar.no/arcgis/rest/services/ArcticSDI/"
    "ArcticSDI_NO_JAN/MapServer?f=json"
)
SVA_URL = (
    "https://geodata.npolar.no/arcgis/rest/services/ArcticSDI/"
    "ArcticSDI_NO_SVA/MapServer?f=json"
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
DATASET_ID = "arcticsdi:ArcticSDI_NO_JAN"

CATALOG = {
    "currentVersion": 10.81,
    "folders": [],
    "services": [
        {"name": "ArcticSDI/ArcticSDI_NO_JAN", "type": "MapServer"},
        {"name": "ArcticSDI/ArcticSDI_NO_SVA", "type": "MapServer"},
        {"name": "", "type": "MapServer"},
        {"name": "SkipMe", "type": ""},
        {"nested": True},
    ],
}
JAN_BODY = {
    "mapName": "ArcticSDI_NO_JAN",
    "copyrightText": "",
    "layers": [
        {"id": 0, "name": "ArcticSDI_NO_JAN", "type": "Group Layer"},
        {
            "id": 1,
            "name": "GeographicalNames",
            "type": "Feature Layer",
            "nested": {"skip": True},
        },
        {"id": 2, "name": "Airports", "type": "Feature Layer"},
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
        if url == JAN_URL:
            return JsonResponse(status=200, url=url, body=JAN_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"arcticsdi fetch must GET, not POST {url}")


def test_printed_refs_skip_empty_name_or_type() -> None:
    source = ArcticsdiSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "ArcticSDI_NO_JAN",
        "ArcticSDI_NO_SVA",
    ]
    assert [ref.source_native_uri for ref in refs] == [JAN_URL, SVA_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "SkipMe" for ref in refs)


def test_printed_services_keep_document_order() -> None:
    listed = printed_services(CATALOG, LIST_URL)
    assert [ident for ident, _href, _title in listed] == [
        "ArcticSDI_NO_JAN",
        "ArcticSDI_NO_SVA",
    ]
    assert [href for _ident, href, _title in listed] == [JAN_URL, SVA_URL]


def test_printed_service_id_uses_last_path_segment() -> None:
    assert printed_service_id("ArcticSDI_NO_SVA") == "ArcticSDI_NO_SVA"
    assert printed_service_id("ArcticSDI/ArcticSDI_NO_JAN") == "ArcticSDI_NO_JAN"
    assert printed_service_id("/") is None


def test_arcticsdi_is_a_registered_source() -> None:
    assert "arcticsdi" in SOURCE_IDS
    assert "npitema" in SOURCE_IDS
    assert "npigis" in SOURCE_IDS
    assert "npolar" in SOURCE_IDS
    assert "nvegis" in SOURCE_IDS
    assert "nve2gis" in SOURCE_IDS
    source = build_source("arcticsdi")
    assert isinstance(source, ArcticsdiSource)
    assert source.source_id == "arcticsdi"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = ArcticsdiSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "arcticsdi"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == JAN_URL
    assert row["title"] == "ArcticSDI_NO_JAN"
    svalbard = registry.get_dataset("arcticsdi:ArcticSDI_NO_SVA")
    assert svalbard is not None
    assert svalbard["access_path"] == SVA_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("npitema:")
    assert not str(row["id"]).startswith("npigis:")
    assert not str(row["id"]).startswith("npolar:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["arcticsdi_service_id"] == "ArcticSDI_NO_JAN"
    assert payload["arcticsdi_service_href"] == JAN_URL
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_layer_names(tmp_path: Path) -> None:
    source = ArcticsdiSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == JAN_URL
    assert result.table_id == "ArcticSDI_NO_JAN"
    assert result.http_status == 200
    assert result.counts.listed == 3
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"ArcticSDI_NO_JAN", "GeographicalNames", "Airports"}
    assert by_value["GeographicalNames"]["measure"] == "name"
    dims = json.loads(by_value["GeographicalNames"]["dimensions_json"])
    assert dims["id"] == "1"
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == JAN_URL for row in rows)
    registry.close()


def test_cells_copy_printed_name_or_scalar() -> None:
    cells = cells_from_arcticsdi(JAN_BODY)
    assert len(cells) == 3
    measure, value, dims = cells[1]
    assert measure == "name"
    assert value == "GeographicalNames"
    assert dims["id"] == "1"
    assert "nested" not in dims
    assert cells_from_arcticsdi({"folders": ["ArcticSDI"]}) == [
        ("value", "ArcticSDI", {})
    ]
    assert cells_from_arcticsdi({"name": "ArcticSDI_NO_JAN", "id": 9}) == [
        ("name", "ArcticSDI_NO_JAN", {"id": "9"})
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_arcticsdi(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_arcticsdi([])


def test_is_arcticsdi_url_accepts_only_arcticsdi_path() -> None:
    assert is_arcticsdi_url(JAN_URL)
    assert is_arcticsdi_url(LIST_URL)
    assert arcticsdi_table_id(JAN_URL) == "ArcticSDI_NO_JAN"
    assert arcticsdi_table_id(SVA_URL) == "ArcticSDI_NO_SVA"
    assert not is_arcticsdi_url(NPITEMA_URL)
    assert not is_arcticsdi_url(NPIGIS_URL)
    assert not is_arcticsdi_url(NPOLAR_URL)
    assert not is_arcticsdi_url(NVEGIS_URL)
    assert not is_arcticsdi_url(NVEMAP_URL)
    assert not is_arcticsdi_url("https://data.norge.no/datasets/x")
    assert not is_arcticsdi_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = ArcticsdiSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "ArcticSDI_NO_JAN"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["ArcticSDI_NO_SVA"]
