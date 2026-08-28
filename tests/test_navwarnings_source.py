from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.navwarnings import (
    NavwarningsSource,
    cells_from_navwarnings,
    is_navwarnings_url,
    navwarnings_table_id,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://api.kystverket.no/openapi.json"
COASTAL_URL = "https://api.kystverket.no/data/navigationwarnings/coastal/"
NAVAREA_URL = "https://api.kystverket.no/data/navigationwarnings/navareaxix/"
DADJOKE_URL = "https://api.kystverket.no/data/dadjokes"
KYSTDATAHUSET_URL = "https://kystdatahuset.no/ws/api/ais/realtime"
NVEGIS_URL = "https://gis3.nve.no/map/rest/services/Fjellskred1/MapServer?f=json"
DATASET_ID = "navwarnings:coastal"

OPENAPI = {
    "openapi": "3.1.0",
    "info": {
        "title": "Norwegian Coastal Administration - Data API",
        "version": "0.1.0",
    },
    "paths": {
        "/data/navigationwarnings/coastal/": {
            "get": {
                "summary": "Coastal Navigation Warnings",
                "operationId": "coastal_navigation_warnings_data_navigationwarnings_coastal__get",
            }
        },
        "/data/navigationwarnings/navareaxix/": {
            "get": {
                "summary": "Get Navigation Warnings For Navarea Xix",
                "operationId": "get_navigation_warnings_for_navarea_xix_data_navigationwarnings_navareaxix__get",
            }
        },
        "/data/dadjokes": {
            "get": {
                "summary": "Dadjoke",
                "operationId": "dadjoke_data_dadjokes_get",
            }
        },
        "/data/navigationwarnings/{eventid}": {
            "get": {
                "operationId": "one_warning",
                "parameters": [
                    {"name": "eventid", "in": "path", "required": True},
                ],
            }
        },
        "/data/search": {
            "get": {
                "operationId": "search_warnings",
                "parameters": [
                    {"name": "q", "in": "query", "required": True},
                ],
            }
        },
    },
}
COASTAL_BODY = [
    {
        "eventid": 857985,
        "status": "active",
        "eventclass": "NAVCO",
        "warningnumber": "287/2026",
        "location": "Rekefjordboen",
        "message_no": "REKEFJORDBOEN LYSBOEYE ER SLUKKET",
        "nested": {"skip": True},
    },
    {
        "eventid": 857986,
        "status": "active",
        "eventclass": "NAVCO",
        "warningnumber": "288/2026",
        "location": "Andenes",
        "message_no": "ANDENES LYKTE ER SLUKKET",
    },
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
        if url == COASTAL_URL:
            return JsonResponse(status=200, url=url, body=COASTAL_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"navwarnings fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_keep_collection_gets() -> None:
    source = NavwarningsSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "coastal",
        "navareaxix",
        "dadjokes",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        COASTAL_URL,
        NAVAREA_URL,
        DADJOKE_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_uses_document_origin_when_servers_absent() -> None:
    url = printed_endpoint_url(OPENAPI, "/data/navigationwarnings/coastal/", OPENAPI_URL)
    assert url == COASTAL_URL
    assert "openapi.json" not in url
    origin_only = printed_endpoint_url({}, "/data/dadjokes", OPENAPI_URL)
    assert origin_only == DADJOKE_URL


def test_printed_operation_id_keeps_last_segment() -> None:
    assert printed_operation_id("/data/navigationwarnings/coastal/") == "coastal"
    assert printed_operation_id("/data/navigationwarnings/navareaxix/") == "navareaxix"
    assert printed_operation_id("/data/dadjokes") == "dadjokes"


def test_printed_license_url_stays_null_without_printed_url() -> None:
    assert printed_license_url(OPENAPI["info"]) is None
    assert printed_license_url({"license": {"name": "NLOD"}}) is None
    assert printed_license_url({"license": {"url": "https://example.invalid/license"}}) == (
        "https://example.invalid/license"
    )


def test_navwarnings_is_a_registered_source() -> None:
    assert "navwarnings" in SOURCE_IDS
    assert "kystverket" in SOURCE_IDS
    assert "nvegis" in SOURCE_IDS
    assert "miljorapporter" in SOURCE_IDS
    source = build_source("navwarnings")
    assert isinstance(source, NavwarningsSource)
    assert source.source_id == "navwarnings"


def test_harvest_writes_printed_id_and_keeps_license_null(tmp_path: Path) -> None:
    source = NavwarningsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "navwarnings"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == COASTAL_URL
    assert row["title"] == "Coastal Navigation Warnings"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("kystverket:")
    assert not str(row["id"]).startswith("nvegis:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["navwarnings_openapi_path"] == "/data/navigationwarnings/coastal/"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_coastal_warnings(tmp_path: Path) -> None:
    source = NavwarningsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == COASTAL_URL
    assert result.table_id == "coastal"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"Rekefjordboen", "Andenes"}
    assert by_value["Rekefjordboen"]["measure"] == "location"
    dims = json.loads(by_value["Rekefjordboen"]["dimensions_json"])
    assert dims["warningnumber"] == "287/2026"
    assert dims["eventid"] == "857985"
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == COASTAL_URL for row in rows)
    registry.close()


def test_cells_copy_printed_location_or_warningnumber() -> None:
    cells = cells_from_navwarnings(COASTAL_BODY)
    assert cells[0][0] == "location"
    assert cells[0][1] == "Rekefjordboen"
    assert cells[0][2]["warningnumber"] == "287/2026"
    assert "nested" not in cells[0][2]
    assert cells_from_navwarnings({"warningnumber": "1/2026", "eventid": 9}) == [
        ("warningnumber", "1/2026", {"eventid": "9"})
    ]
    assert cells_from_navwarnings("Rekefjordboen") == [
        ("value", "Rekefjordboen", {"value": "Rekefjordboen"})
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_navwarnings(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_navwarnings([])


def test_is_navwarnings_url_accepts_only_data_path() -> None:
    assert is_navwarnings_url(COASTAL_URL)
    assert is_navwarnings_url(NAVAREA_URL)
    assert is_navwarnings_url(DADJOKE_URL)
    assert navwarnings_table_id(COASTAL_URL) == "coastal"
    assert printed_endpoint_url(OPENAPI, "/data/navigationwarnings/coastal/", OPENAPI_URL) == (
        COASTAL_URL
    )
    assert not is_navwarnings_url(OPENAPI_URL)
    assert not is_navwarnings_url(KYSTDATAHUSET_URL)
    assert not is_navwarnings_url(NVEGIS_URL)
    assert not is_navwarnings_url("https://data.norge.no/datasets/x")
    assert not is_navwarnings_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = NavwarningsSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "coastal"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["navareaxix"]
    assert source.list_dataset_refs(limit=1, offset=3) == []
