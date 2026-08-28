from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.ragis import (
    RagisSource,
    cells_from_ragis,
    is_ragis_url,
    printed_service_id,
    printed_services,
    ragis_table_id,
)

LIST_URL = "https://kart.ra.no/arcgis/rest/services/MABYGIS?f=json"
ASKELADDEN_URL = (
    "https://kart.ra.no/arcgis/rest/services/MABYGIS/MABYGIS_Askeladden/FeatureServer?f=json"
)
ASKELADDEN_MAP_URL = (
    "https://kart.ra.no/arcgis/rest/services/MABYGIS/MABYGIS_Askeladden/MapServer?f=json"
)
ADMIN_URL = "https://kart.ra.no/arcgis/rest/services/MABYGIS/admin/MapServer?f=json"
REST_RO_URL = (
    "https://kart.ra.no/arcgis/rest/services/MABYGIS/MABYGIS_rest_ro/FeatureServer?f=json"
)
REST_RO_LAYER_URL = (
    "https://kart.ra.no/arcgis/rest/services/MABYGIS/MABYGIS_rest_ro/FeatureServer/0?f=json"
)
ANDRETJENESTER_URL = "https://kart.ra.no/arcgis/rest/services/Andretjenester?f=json"
OGC_URL = "https://api.ra.no/LokaliteterEnkeltminnerOgSikringssoner"
WMS_URL = (
    "https://kart.ra.no/wms/kulturminner2?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetCapabilities"
)
NPIINTERN_URL = (
    "https://geodata.npolar.no/arcgis/rest/services/Basisdata_Intern/"
    "NP_Antarktis_WMTS_3031/MapServer?f=json"
)
DATASET_ID = "ragis:MABYGIS_Askeladden"

CATALOG = {
    "currentVersion": 11.3,
    "folders": [],
    "services": [
        {"name": "MABYGIS/admin", "type": "MapServer"},
        {"name": "MABYGIS/MABYGIS_Askeladden", "type": "FeatureServer"},
        {"name": "MABYGIS/MABYGIS_Askeladden", "type": "MapServer"},
        {"name": "MABYGIS/MABYGIS_rest_ro", "type": "FeatureServer"},
        {"name": "MABYGIS/MABYGIS_rest_ro", "type": "MapServer"},
        {"name": "", "type": "MapServer"},
        {"name": "SkipEmptyType", "type": ""},
        {"nested": True},
    ],
}
ASKELADDEN_BODY = {
    "name": "MABYGIS_Askeladden",
    "serviceDescription": "MABYGIS data visning i Askeladden",
    "copyrightText": "",
    "layers": [
        {
            "id": 1,
            "name": "Dispensasjoner",
            "type": "Feature Layer",
            "nested": {"skip": True},
        }
    ],
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
        if url == ASKELADDEN_URL:
            return JsonResponse(status=200, url=url, body=ASKELADDEN_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"ragis fetch must GET, not POST {url}")


def test_printed_refs_skip_admin_rest_ro_and_empty() -> None:
    source = RagisSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["MABYGIS_Askeladden"]
    assert [ref.source_native_uri for ref in refs] == [ASKELADDEN_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "admin" for ref in refs)
    assert all(ref.source_native_id != "MABYGIS_rest_ro" for ref in refs)
    assert all(ref.source_native_id != "SkipEmptyType" for ref in refs)
    assert ASKELADDEN_MAP_URL not in [ref.source_native_uri for ref in refs]


def test_printed_services_keep_first_printed_type() -> None:
    listed = printed_services(CATALOG, LIST_URL)
    assert [ident for ident, _href, _title in listed] == ["MABYGIS_Askeladden"]
    assert [href for _ident, href, _title in listed] == [ASKELADDEN_URL]


def test_printed_service_id_uses_last_path_segment() -> None:
    assert printed_service_id("MABYGIS_Askeladden") == "MABYGIS_Askeladden"
    assert printed_service_id("MABYGIS/MABYGIS_Askeladden") == "MABYGIS_Askeladden"
    assert printed_service_id("/") is None


def test_ragis_is_a_registered_source() -> None:
    assert "ragis" in SOURCE_IDS
    assert "riksantikvaren" in SOURCE_IDS
    assert "npiintern" in SOURCE_IDS
    assert "hoydegis" in SOURCE_IDS
    assert "nvegis" in SOURCE_IDS
    assert "miljogis" in SOURCE_IDS
    source = build_source("ragis")
    assert isinstance(source, RagisSource)
    assert source.source_id == "ragis"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = RagisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "ragis"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == ASKELADDEN_URL
    assert row["title"] == "MABYGIS_Askeladden"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("riksantikvaren:")
    assert not str(row["id"]).startswith("npiintern:")
    assert not str(row["id"]).startswith("hoydegis:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["ragis_service_id"] == "MABYGIS_Askeladden"
    assert payload["ragis_service_href"] == ASKELADDEN_URL
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_layer_names(tmp_path: Path) -> None:
    source = RagisSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == ASKELADDEN_URL
    assert result.table_id == "MABYGIS_Askeladden"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    assert len(rows) == 1
    assert json.loads(rows[0]["value_json"]) == "Dispensasjoner"
    assert rows[0]["measure"] == "name"
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["id"] == "1"
    assert dims["type"] == "Feature Layer"
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == ASKELADDEN_URL for row in rows)
    registry.close()


def test_cells_copy_printed_name_or_scalar() -> None:
    cells = cells_from_ragis(ASKELADDEN_BODY)
    assert len(cells) == 1
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "Dispensasjoner"
    assert dims["id"] == "1"
    assert "nested" not in dims
    assert cells_from_ragis({"folders": ["MABYGIS"]}) == [("value", "MABYGIS", {})]
    assert cells_from_ragis({"name": "MABYGIS_Askeladden", "id": 9}) == [
        ("name", "MABYGIS_Askeladden", {"id": "9"})
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_ragis(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_ragis([])


def test_is_ragis_url_accepts_only_mabygis_leftover_path() -> None:
    assert is_ragis_url(ASKELADDEN_URL)
    assert is_ragis_url(LIST_URL)
    assert is_ragis_url(ADMIN_URL)
    assert is_ragis_url(REST_RO_URL)
    assert ragis_table_id(ASKELADDEN_URL) == "MABYGIS_Askeladden"
    assert ragis_table_id(ASKELADDEN_MAP_URL) == "MABYGIS_Askeladden"
    assert not is_ragis_url(REST_RO_LAYER_URL)
    assert not is_ragis_url(ANDRETJENESTER_URL)
    assert not is_ragis_url(OGC_URL)
    assert not is_ragis_url(WMS_URL)
    assert not is_ragis_url(NPIINTERN_URL)
    assert not is_ragis_url("https://data.norge.no/datasets/x")
    assert not is_ragis_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = RagisSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "MABYGIS_Askeladden"
    ]
    assert source.list_dataset_refs(limit=1, offset=1) == []
