from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.kystverket import (
    KystverketSource,
    cells_from_kystverket,
    is_kystverket_url,
    kystverket_table_id,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://kystdatahuset.no/ws/swagger/v1/swagger.json"
COUNTIES_URL = "https://kystdatahuset.no/ws/api/location/counties"
GEOJSON_URL = "https://kystdatahuset.no/ws/api/ais/realtime/geojson"
LICENSE_URL = "https://data.norge.no/nlod/en/1.0"
DATASET_ID = "kystverket:api/location/counties"

OPENAPI = {
    "openapi": "3.0.1",
    "info": {
        "title": "Kystdatahuset Open API",
        "description": "Web Service API for open and authorized access to data from the Norwegian Coastal Administration (Kystverket).",
        "license": {
            "name": "Norwegian Licence for Open Government Data (NLOD) 1.0",
            "url": LICENSE_URL,
        },
        "version": "v1",
    },
    "servers": [{"url": "/ws"}],
    "paths": {
        "/api/ais/realtime/geojson": {
            "get": {"summary": "Return GeoJSON for all ships in real time"},
        },
        "/api/location/{id}": {
            "get": {"summary": "templated"},
        },
        "/api/location/counties": {
            "get": {"summary": "Get all counties from NewShipRep location table"},
        },
        "/api/ship/combined/download": {
            "get": {
                "summary": "restricted registry",
                "security": [{"JWT Bearer": [None]}],
            }
        },
        "/api/vocabulary": {
            "get": {"summary": "Retrieve all available vocabularies"},
        },
    },
}
COUNTIES_BODY = {
    "success": True,
    "msg": "",
    "data": [
        {"countyname": "Agder", "countyno": "42"},
        {"countyname": "Oslo", "countyno": "03"},
    ],
    "metadata": {},
    "time": 4,
}


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
        if url == COUNTIES_URL:
            return JsonResponse(status=200, url=url, body=COUNTIES_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"kystverket fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_paths() -> None:
    source = KystverketSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "api/ais/realtime/geojson",
        "api/location/counties",
        "api/ship/combined/download",
        "api/vocabulary",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        GEOJSON_URL,
        COUNTIES_URL,
        "https://kystdatahuset.no/ws/api/ship/combined/download",
        "https://kystdatahuset.no/ws/api/vocabulary",
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_joins_printed_relative_server() -> None:
    url = printed_endpoint_url(OPENAPI, "/api/location/counties", OPENAPI_URL)
    assert url == COUNTIES_URL
    assert "/swagger" not in url
    absolute = printed_endpoint_url(
        {"servers": [{"url": "https://kystdatahuset.no/ws"}]},
        "/api/location/counties",
        OPENAPI_URL,
    )
    assert absolute == COUNTIES_URL


def test_printed_operation_id_is_printed_path() -> None:
    assert printed_operation_id("/api/location/counties") == "api/location/counties"
    assert printed_operation_id("/api/location/all") == "api/location/all"
    assert printed_operation_id("/api/location/norway/all") == "api/location/norway/all"


def test_printed_license_url_copies_openapi_license() -> None:
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({"title": "Kystdatahuset Open API"}) is None


def test_kystverket_is_a_registered_source() -> None:
    assert "kystverket" in SOURCE_IDS
    source = build_source("kystverket")
    assert isinstance(source, KystverketSource)
    assert source.source_id == "kystverket"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = KystverketSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 4
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "kystverket"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == COUNTIES_URL
    assert row["title"] == "Get all counties from NewShipRep location table"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["kystverket_openapi_path"] == "/api/location/counties"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    registry.close()


def test_fetch_gets_printed_counties(tmp_path: Path) -> None:
    source = KystverketSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == COUNTIES_URL
    assert result.table_id == "counties"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["Agder", "Oslo"] or values == ["Oslo", "Agder"]
    assert all(row["measure"] == "countyname" for row in rows)
    by_name = {json.loads(row["value_json"]): row for row in rows}
    dims = json.loads(by_name["Oslo"]["dimensions_json"])
    assert dims["countyno"] == "03"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == COUNTIES_URL for row in rows)
    registry.close()


def test_cells_copy_printed_county_name() -> None:
    cells = cells_from_kystverket(COUNTIES_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "countyname"
    assert value == "Agder"
    assert dims["countyno"] == "42"
    fallback = cells_from_kystverket([{"id": "42", "countyno": "42"}])
    assert fallback == [("id", "42", {"countyno": "42"})]
    with pytest.raises(ValueError, match="data collection"):
        cells_from_kystverket({"success": True, "data": {}})


def test_is_kystverket_url_accepts_only_kystdatahuset_api() -> None:
    assert is_kystverket_url(COUNTIES_URL)
    assert is_kystverket_url(GEOJSON_URL)
    assert kystverket_table_id(COUNTIES_URL) == "counties"
    assert not is_kystverket_url(OPENAPI_URL)
    assert not is_kystverket_url("https://api.kystverket.no/data/navigationwarnings/coastal/")
    assert not is_kystverket_url("https://api.met.no/weatherapi/metalerts/2.0/locations")
    assert not is_kystverket_url("https://data.norge.no/datasets/x")
    assert not is_kystverket_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = KystverketSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "api/ais/realtime/geojson"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["api/location/counties"]
