from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.met import (
    MetMetalertsSource,
    cells_from_met,
    is_met_metalerts_url,
    met_table_id,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://api.met.no/weatherapi/metalerts/2.0/swagger"
LOCATIONS_URL = "https://api.met.no/weatherapi/metalerts/2.0/locations"
CURRENT_URL = "https://api.met.no/weatherapi/metalerts/2.0/current"
LICENSE_URL = "http://creativecommons.org/licenses/by/4.0"
DATASET_ID = "met:locations"

OPENAPI = {
    "swagger": "2.0",
    "info": {
        "title": "Metalerts",
        "description": "Weather alerts from the Norwegian Meteorological Institute",
        "license": {"name": "CC BY 4.0", "url": LICENSE_URL},
        "version": "2.0",
    },
    "basePath": "/weatherapi/metalerts/2.0",
    "paths": {
        "/current": {
            "get": {
                "description": "Weather alerts from the Norwegian Meteorological Institute",
            }
        },
        "/current.{format}": {
            "get": {
                "description": "templated",
            }
        },
        "/locations": {
            "get": {
                "description": "List available locations as GeoJSON FeatureCollection",
            }
        },
        "/values": {
            "get": {
                "description": "List allowed options for parameters",
            }
        },
    },
}
LOCATIONS_BODY = {
    "type": "FeatureCollection",
    "copyright": "MET Norway",
    "licenseURL": "https://api.met.no/license_data.html",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "id": "03",
                "name": "Oslo",
                "title": "Oslo",
                "type": "county",
                "collection": ["current", "all", "archive"],
            },
            "geometry": {"type": "Polygon", "coordinates": [[[10.4, 59.9], [10.8, 59.9]]]},
        },
        {
            "type": "Feature",
            "properties": {
                "id": "11",
                "name": "Rogaland",
                "title": "Rogaland",
                "type": "county",
            },
            "geometry": {"type": "Polygon", "coordinates": [[[5.6, 58.8], [6.0, 58.8]]]},
        },
    ],
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
        if url == LOCATIONS_URL:
            return JsonResponse(status=200, url=url, body=LOCATIONS_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"met fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_paths() -> None:
    source = MetMetalertsSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["current", "locations", "values"]
    assert [ref.source_native_uri for ref in refs] == [
        CURRENT_URL,
        LOCATIONS_URL,
        "https://api.met.no/weatherapi/metalerts/2.0/values",
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_joins_printed_basepath_and_origin() -> None:
    url = printed_endpoint_url(OPENAPI, "/locations", OPENAPI_URL)
    assert url == LOCATIONS_URL
    assert "/swagger" not in url
    with_host = printed_endpoint_url(
        {"host": "api.met.no", "basePath": "/weatherapi/metalerts/2.0", "schemes": ["https"]},
        "/locations",
        OPENAPI_URL,
    )
    assert with_host == LOCATIONS_URL


def test_printed_operation_id_is_last_path_segment() -> None:
    assert printed_operation_id("/locations") == "locations"
    assert printed_operation_id("/current") == "current"


def test_printed_license_url_copies_swagger_license() -> None:
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({"title": "Metalerts"}) is None


def test_met_is_a_registered_source() -> None:
    assert "met" in SOURCE_IDS
    source = build_source("met")
    assert isinstance(source, MetMetalertsSource)
    assert source.source_id == "met"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = MetMetalertsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "met"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == LOCATIONS_URL
    assert row["title"] == "List available locations as GeoJSON FeatureCollection"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["met_openapi_path"] == "/locations"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    registry.close()


def test_fetch_gets_printed_locations(tmp_path: Path) -> None:
    source = MetMetalertsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == LOCATIONS_URL
    assert result.table_id == "locations"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["Oslo", "Rogaland"] or values == ["Rogaland", "Oslo"]
    assert all(row["measure"] == "name" for row in rows)
    by_name = {json.loads(row["value_json"]): row for row in rows}
    dims = json.loads(by_name["Oslo"]["dimensions_json"])
    assert dims["id"] == "03"
    assert dims["type"] == "county"
    assert "collection" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == LOCATIONS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_location_name() -> None:
    cells = cells_from_met(LOCATIONS_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "Oslo"
    assert dims["id"] == "03"
    assert dims["type"] == "county"
    assert "collection" not in dims
    fallback = cells_from_met(
        {
            "type": "FeatureCollection",
            "features": [{"properties": {"id": "03", "type": "county"}}],
        }
    )
    assert fallback == [("id", "03", {"type": "county"})]
    with pytest.raises(ValueError, match="FeatureCollection"):
        cells_from_met({"features": []})


def test_is_met_url_accepts_only_metalerts_host_path() -> None:
    assert is_met_metalerts_url(LOCATIONS_URL)
    assert is_met_metalerts_url(OPENAPI_URL)
    assert met_table_id(LOCATIONS_URL) == "locations"
    assert not is_met_metalerts_url("https://data.norge.no/datasets/x")
    assert not is_met_metalerts_url("https://frost.met.no/sources/v0.jsonld")
    assert not is_met_metalerts_url("https://api.met.no/weatherapi/locationforecast/2.0/complete")
    assert not is_met_metalerts_url("https://driftsdata.statnett.no/RestApi/ElspotPowerSituation/GetPowerSituations")
    assert not is_met_metalerts_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = MetMetalertsSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["current"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["locations"]
