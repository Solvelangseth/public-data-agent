from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import classify_access_path, fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.miljodir import (
    UNIT_SCHEME,
    MiljodirVannmiljoSource,
    cells_from_miljodir,
    is_miljodir_unit_list_url,
    is_miljodir_url,
    lookups_from_miljodir_units,
    miljodir_table_id,
    printed_endpoint_url,
    printed_operation_id,
)

OPENAPI_URL = "https://vannmiljoapi.miljodirektoratet.no/swagger/docs/v1"
MEDIUM_URL = "https://vannmiljoapi.miljodirektoratet.no/api/Public/GetMediumList"
UNIT_URL = "https://vannmiljoapi.miljodirektoratet.no/api/Public/GetUnitList"
DATASET_ID = "miljodir:Public_GetMediumList"
UNIT_ID = "miljodir:Public_GetUnitList"

OPENAPI = {
    "swagger": "2.0",
    "info": {"version": "v1", "title": "Vannmiljø Web Api"},
    "host": "vannmiljoapi.miljodirektoratet.no",
    "basePath": "/",
    "schemes": ["https"],
    "paths": {
        "/api/Public/GetMediumList": {
            "get": {
                "operationId": "Public_GetMediumList",
                "summary": "Returnerer en liste av Medium objekter.",
            }
        },
        "/api/Public/GetUnitList": {
            "get": {
                "operationId": "Public_GetUnitList",
                "summary": "Returnerer en liste av Unit objekter.",
            }
        },
        "/api/Public/DownloadAttachment/{id}": {
            "get": {
                "operationId": "Public_DownloadAttachment",
                "summary": "templated",
            }
        },
        "/api/Public/GetRegistrations": {
            "post": {"operationId": "Public_GetRegistrations"},
        },
    },
}
MEDIUM_BODY = [
    {
        "MediumID": "BB",
        "Name": "Biota bløtdeler",
        "Description": "Innmat i muslinger",
        "EUcode": "Biota soft body",
        "IsWaterRelated": True,
    },
    {
        "MediumID": "SE",
        "Name": "Sediment",
        "Description": "Bunnmateriale",
        "EUcode": "Sediment",
        "IsWaterRelated": True,
    },
]
UNIT_BODY = [
    {
        "UnitID": 1,
        "Name": "%",
        "Description": "prosent",
        "SortOrder": None,
        "nested": {"skip": True},
    },
    {"UnitID": 2, "Name": "% v.v.", "Description": "prosent på våtvektbasis"},
]


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == OPENAPI_URL:
            return OPENAPI
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == MEDIUM_URL:
            return JsonResponse(status=200, url=url, body=MEDIUM_BODY)
        if url == UNIT_URL:
            return JsonResponse(status=200, url=url, body=UNIT_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"miljodir fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_post_only_paths() -> None:
    source = MiljodirVannmiljoSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "Public_GetMediumList",
        "Public_GetUnitList",
    ]
    assert [ref.source_native_uri for ref in refs] == [MEDIUM_URL, UNIT_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_joins_printed_host_basepath_and_path() -> None:
    url = printed_endpoint_url(OPENAPI, "/api/Public/GetMediumList", OPENAPI_URL)
    assert url == MEDIUM_URL
    assert "/swagger" not in url
    no_host = printed_endpoint_url(
        {"basePath": "/", "schemes": ["https"]},
        "/api/Public/GetMediumList",
        OPENAPI_URL,
    )
    assert no_host == MEDIUM_URL


def test_printed_operation_id_prefers_swagger_operationId() -> None:
    item = OPENAPI["paths"]["/api/Public/GetMediumList"]
    assert printed_operation_id("/api/Public/GetMediumList", item) == "Public_GetMediumList"
    assert printed_operation_id("/api/Public/GetMediumList") == "GetMediumList"


def test_miljodir_is_a_registered_source() -> None:
    assert "miljodir" in SOURCE_IDS
    source = build_source("miljodir")
    assert isinstance(source, MiljodirVannmiljoSource)
    assert source.source_id == "miljodir"


def test_harvest_writes_printed_id_and_null_license_publisher(tmp_path: Path) -> None:
    source = MiljodirVannmiljoSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "miljodir"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == MEDIUM_URL
    assert row["title"] == "Returnerer en liste av Medium objekter."
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["miljodir_openapi_path"] == "/api/Public/GetMediumList"
    assert payload["license"] is None
    assert payload["publisher"] is None
    registry.close()


def test_fetch_gets_printed_medium_list(tmp_path: Path) -> None:
    source = MiljodirVannmiljoSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == MEDIUM_URL
    assert result.table_id == "GetMediumList"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["Biota bløtdeler", "Sediment"] or values == [
        "Sediment",
        "Biota bløtdeler",
    ]
    assert all(row["measure"] == "Name" for row in rows)
    by_name = {json.loads(row["value_json"]): row for row in rows}
    dims = json.loads(by_name["Sediment"]["dimensions_json"])
    assert dims["MediumID"] == "SE"
    assert dims["EUcode"] == "Sediment"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == MEDIUM_URL for row in rows)
    registry.close()


def test_unit_list_url_is_lookup() -> None:
    assert is_miljodir_unit_list_url(UNIT_URL)
    assert not is_miljodir_unit_list_url(MEDIUM_URL)
    assert classify_access_path(UNIT_URL)["kind"] == "lookup"


def test_fetch_stores_units_as_lookup(tmp_path: Path) -> None:
    source = MiljodirVannmiljoSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        UNIT_ID,
        table_id="GetUnitList",
        http=FetchHttp(),
    )
    assert result.http_status == 200
    assert result.counts.listed == 2
    assert registry.list_observations(UNIT_ID) == []
    rows = registry.list_records(UNIT_ID, kind="entity")
    by_code = {row["subject_code"]: row for row in rows}
    assert by_code["1"]["subject_label"] == "%"
    assert by_code["1"]["subject_scheme"] == UNIT_SCHEME
    assert by_code["2"]["subject_label"] == "% v.v."
    attrs = json.loads(by_code["1"]["attributes_json"])
    assert attrs["Description"] == "prosent"
    assert "SortOrder" not in attrs
    assert "nested" not in attrs
    cap = registry.get_capability(UNIT_ID)
    assert cap["capability"] == "lookup"
    registry.close()


def test_lookups_copy_printed_unit_id() -> None:
    members = lookups_from_miljodir_units(UNIT_BODY)
    assert members[0]["subject_code"] == "1"
    assert members[0]["subject_scheme"] == UNIT_SCHEME
    assert members[0]["subject_label"] == "%"
    assert members[1]["subject_label"] == "% v.v."
    assert "nested" not in members[0]["attributes"]
    with pytest.raises(ValueError, match="JSON array"):
        lookups_from_miljodir_units({"UnitID": 1})
    with pytest.raises(ValueError, match="printed no UnitID"):
        lookups_from_miljodir_units([])


def test_cells_copy_printed_medium_name() -> None:
    cells = cells_from_miljodir(MEDIUM_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "Name"
    assert value == "Biota bløtdeler"
    assert dims["MediumID"] == "BB"
    fallback = cells_from_miljodir([{"MediumID": "SE", "EUcode": "Sediment"}])
    assert fallback == [("MediumID", "SE", {"EUcode": "Sediment"})]
    with pytest.raises(ValueError, match="JSON array"):
        cells_from_miljodir({"Name": "Sediment"})


def test_is_miljodir_url_accepts_only_vannmiljo_api() -> None:
    assert is_miljodir_url(MEDIUM_URL)
    assert is_miljodir_url(UNIT_URL)
    assert miljodir_table_id(MEDIUM_URL) == "GetMediumList"
    assert not is_miljodir_url(OPENAPI_URL)
    assert not is_miljodir_url("https://vann-nett.no/portal-api/Public/GetMediumList")
    assert not is_miljodir_url("https://kystdatahuset.no/ws/api/location/counties")
    assert not is_miljodir_url("https://data.norge.no/datasets/x")
    assert not is_miljodir_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = MiljodirVannmiljoSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "Public_GetMediumList"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["Public_GetUnitList"]
