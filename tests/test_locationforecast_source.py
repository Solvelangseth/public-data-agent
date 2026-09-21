from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.locationforecast import (
    LocationforecastSource,
    cells_from_locationforecast,
    is_locationforecast_url,
    locationforecast_table_id,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://api.met.no/weatherapi/locationforecast/2.0/swagger"
LOCATIONS_URL = "https://api.met.no/weatherapi/locationforecast/2.0/locations"
CHANGELOG_URL = "https://api.met.no/weatherapi/locationforecast/2.0/changelog"
HEALTHZ_URL = "https://api.met.no/weatherapi/locationforecast/2.0/healthz"
SCHEMA_URL = "https://api.met.no/weatherapi/locationforecast/2.0/schema"
STATUS_URL = "https://api.met.no/weatherapi/locationforecast/2.0/status"
LICENSE_URL = "http://creativecommons.org/licenses/by/4.0"
DATASET_ID = "locationforecast:locations"

OPENAPI = {
    "swagger": "2.0",
    "info": {
        "title": "Locationforecast",
        "description": "Weather forecasts for any location on earth",
        "license": {"name": "CC BY 4.0", "url": LICENSE_URL},
        "version": "2.0",
    },
    "basePath": "/weatherapi/locationforecast/2.0",
    "paths": {
        "/changelog": {
            "get": {
                "description": "RSS feed of changes to this product",
            }
        },
        "/classic": {
            "get": {
                "description": "Weather forecasts for any location on earth",
                "parameters": [
                    {"name": "lat", "in": "query", "required": True, "type": "number"},
                    {"name": "lon", "in": "query", "required": True, "type": "number"},
                    {"name": "altitude", "in": "query", "required": False, "type": "number"},
                ],
            }
        },
        "/classic.{format}": {
            "get": {
                "description": "templated",
                "parameters": [
                    {"name": "lat", "in": "query", "required": True, "type": "number"},
                    {"name": "lon", "in": "query", "required": True, "type": "number"},
                    {"name": "format", "in": "path", "required": True, "type": "string"},
                ],
            }
        },
        "/compact": {
            "get": {
                "description": "Weather forecasts for any location on earth",
                "parameters": [
                    {"name": "lat", "in": "query", "required": True, "type": "number"},
                    {"name": "lon", "in": "query", "required": True, "type": "number"},
                ],
            }
        },
        "/complete": {
            "get": {
                "description": "Weather forecasts for any location on earth",
                "parameters": [
                    {"name": "lat", "in": "query", "required": True, "type": "number"},
                    {"name": "lon", "in": "query", "required": True, "type": "number"},
                ],
            }
        },
        "/healthz": {
            "get": {
                "description": "Check health status for product",
            }
        },
        "/locations": {
            "get": {
                "description": "List available locations as GeoJSON FeatureCollection",
            }
        },
        "/schema": {
            "get": {
                "description": "Schema for XML data",
            }
        },
        "/status": {
            "get": {
                "description": "Weather forecasts for any location on earth",
            }
        },
        "/status.{format}": {
            "get": {
                "description": "templated",
                "parameters": [
                    {"name": "format", "in": "path", "required": True, "type": "string"},
                ],
            }
        },
    },
}
LOCATIONS_BODY = {
    "type": "FeatureCollection",
    "copyright": "MET Norway",
    "features": [
        {
            "type": "Feature",
            "id": "ecmwf",
            "properties": {
                "id": "ecmwf",
                "name": "ECMWF area",
                "title": "ECMWF area",
                "resources": [{"uri": "compact", "params": ["lat", "lon"]}],
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-180, -90], [-180, 90], [180, 90], [180, -90], [-180, -90]]],
            },
        },
        {
            "type": "Feature",
            "id": "meps",
            "properties": {
                "name": "MEPS area",
                "title": "MEPS area",
            },
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
        raise AssertionError(f"locationforecast fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_required_param_paths() -> None:
    source = LocationforecastSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "changelog",
        "healthz",
        "locations",
        "schema",
        "status",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        CHANGELOG_URL,
        HEALTHZ_URL,
        LOCATIONS_URL,
        SCHEMA_URL,
        STATUS_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]
    assert "" not in [ref.source_native_id for ref in refs]
    assert all("classic" not in (ref.source_native_id or "") for ref in refs)
    assert all("compact" not in (ref.source_native_id or "") for ref in refs)
    assert all("complete" not in (ref.source_native_id or "") for ref in refs)


def test_endpoint_url_joins_printed_basepath_and_origin() -> None:
    url = printed_endpoint_url(OPENAPI, "/locations", OPENAPI_URL)
    assert url == LOCATIONS_URL
    assert "/swagger" not in url
    with_host = printed_endpoint_url(
        {
            "host": "api.met.no",
            "basePath": "/weatherapi/locationforecast/2.0",
            "schemes": ["https"],
        },
        "/locations",
        OPENAPI_URL,
    )
    assert with_host == LOCATIONS_URL


def test_printed_operation_id_is_last_path_segment() -> None:
    assert printed_operation_id("/locations") == "locations"
    assert printed_operation_id("/schema") == "schema"


def test_printed_license_url_copies_swagger_license() -> None:
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({"title": "Locationforecast"}) is None


def test_locationforecast_is_a_registered_source() -> None:
    assert "locationforecast" in SOURCE_IDS
    assert "routeforecast" in SOURCE_IDS
    assert "volcanicashforecast" in SOURCE_IDS
    assert "sigcharts" in SOURCE_IDS
    assert "nlaroutes" in SOURCE_IDS
    source = build_source("locationforecast")
    assert isinstance(source, LocationforecastSource)
    assert source.source_id == "locationforecast"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = LocationforecastSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    assert counts.ignored == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "locationforecast"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == LOCATIONS_URL
    assert row["title"] == "List available locations as GeoJSON FeatureCollection"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("met:")
    assert not str(row["id"]).startswith("routeforecast:")
    assert not str(row["id"]).startswith("volcanicashforecast:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["locationforecast_openapi_path"] == "/locations"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_locations(tmp_path: Path) -> None:
    source = LocationforecastSource(http=CatalogHttp())
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
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"ECMWF area", "MEPS area"}
    assert by_value["ECMWF area"]["measure"] == "name"
    dims = json.loads(by_value["ECMWF area"]["dimensions_json"])
    assert dims["id"] == "ecmwf"
    assert dims["title"] == "ECMWF area"
    assert "geometry" not in dims
    assert "resources" not in dims
    assert by_value["MEPS area"]["measure"] == "name"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == LOCATIONS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_feature_name_or_id() -> None:
    cells = cells_from_locationforecast(LOCATIONS_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "ECMWF area"
    assert dims["id"] == "ecmwf"
    assert dims["title"] == "ECMWF area"
    assert "geometry" not in dims
    assert "resources" not in dims
    measure, value, dims = cells[1]
    assert measure == "name"
    assert value == "MEPS area"
    assert dims["id"] == "meps"
    fallback = cells_from_locationforecast(
        {
            "type": "FeatureCollection",
            "features": [{"id": None, "properties": {"title": "ECMWF area"}}],
        }
    )
    assert fallback == [("title", "ECMWF area", {})]
    with pytest.raises(ValueError, match="FeatureCollection"):
        cells_from_locationforecast({"features": []})
    with pytest.raises(ValueError, match="features array"):
        cells_from_locationforecast({"type": "FeatureCollection"})


def test_is_locationforecast_url_accepts_only_locationforecast_host_path() -> None:
    assert is_locationforecast_url(LOCATIONS_URL)
    assert is_locationforecast_url(OPENAPI_URL)
    assert locationforecast_table_id(LOCATIONS_URL) == "locations"
    assert printed_endpoint_url(OPENAPI, "/locations", OPENAPI_URL) == LOCATIONS_URL
    assert not is_locationforecast_url("https://api.met.no/weatherapi/routeforecast/2.0/locations")
    assert not is_locationforecast_url("https://api.met.no/weatherapi/volcanicashforecast/0.1/reftimes")
    assert not is_locationforecast_url("https://api.met.no/weatherapi/sigcharts/2.0/locations")
    assert not is_locationforecast_url("https://api.met.no/weatherapi/nlaroutes/1.0/locations")
    assert not is_locationforecast_url("https://api.met.no/weatherapi/nowcast/2.0/locations")
    assert not is_locationforecast_url("https://api.met.no/weatherapi/metalerts/2.0/locations")
    assert not is_locationforecast_url("https://ws.geonorge.no/hoydedata/v1/datakilder")
    assert not is_locationforecast_url("https://data.norge.no/datasets/x")
    assert not is_locationforecast_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = LocationforecastSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "changelog"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=2)
    assert [ref.source_native_id for ref in nxt] == ["locations"]
