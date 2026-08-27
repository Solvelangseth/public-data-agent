from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.radar import (
    RadarSource,
    cells_from_radar,
    is_radar_url,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
    radar_table_id,
)

OPENAPI_URL = "https://api.met.no/weatherapi/radar/2.0/swagger"
LOCATIONS_URL = "https://api.met.no/weatherapi/radar/2.0/locations"
AVAILABLE_URL = "https://api.met.no/weatherapi/radar/2.0/available"
LICENSE_URL = "http://creativecommons.org/licenses/by/4.0"
DATASET_ID = "radar:locations"

OPENAPI = {
    "swagger": "2.0",
    "info": {
        "title": "Radar",
        "description": "Radar composite images for various areas in the Nordic",
        "license": {"name": "CC BY 4.0", "url": LICENSE_URL},
        "version": "2.0",
    },
    "basePath": "/weatherapi/radar/2.0",
    "paths": {
        "/": {
            "get": {
                "description": "Radar composite images for various areas in the Nordic",
                "parameters": [
                    {"name": "area", "required": True, "in": "query"},
                    {"name": "type", "required": True, "in": "query"},
                ],
            }
        },
        "/5level_reflectivity": {
            "get": {
                "description": "Radar composite images for various areas in the Nordic",
                "parameters": [{"name": "area", "required": True, "in": "query"}],
            }
        },
        "/available": {
            "get": {
                "description": "List available resources as XML",
            }
        },
        "/available.{format}": {
            "get": {
                "description": "templated",
            }
        },
        "/changelog": {
            "get": {
                "description": "RSS feed of changes to this product",
            }
        },
        "/locations": {
            "get": {
                "description": "List available locations as GeoJSON FeatureCollection",
            }
        },
        "/status": {
            "get": {
                "description": "Radar composite images for various areas in the Nordic",
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
            "id": "central_norway",
            "properties": {
                "id": "central_norway",
                "name": "Central Norway",
                "title": "Central Norway",
                "collection": ["reflectivity", "preciptype"],
                "resources": [
                    {
                        "description": "reflectivity.png",
                        "mimeType": "image/png",
                    }
                ],
            },
            "geometry": {"type": "Polygon", "coordinates": [[[1.0, 59.8], [17.8, 59.8]]]},
        },
        {
            "type": "Feature",
            "properties": {
                "id": "finnmark",
                "title": "Finnmark",
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
        raise AssertionError(f"radar fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_required_param_paths() -> None:
    source = RadarSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "available",
        "changelog",
        "locations",
        "status",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        AVAILABLE_URL,
        "https://api.met.no/weatherapi/radar/2.0/changelog",
        LOCATIONS_URL,
        "https://api.met.no/weatherapi/radar/2.0/status",
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]
    assert "5level_reflectivity" not in [ref.source_native_id for ref in refs]


def test_endpoint_url_joins_printed_basepath_and_origin() -> None:
    url = printed_endpoint_url(OPENAPI, "/locations", OPENAPI_URL)
    assert url == LOCATIONS_URL
    assert "/swagger" not in url
    with_host = printed_endpoint_url(
        {
            "host": "api.met.no",
            "basePath": "/weatherapi/radar/2.0",
            "schemes": ["https"],
        },
        "/locations",
        OPENAPI_URL,
    )
    assert with_host == LOCATIONS_URL


def test_printed_operation_id_is_last_path_segment() -> None:
    assert printed_operation_id("/locations") == "locations"
    assert printed_operation_id("/available") == "available"


def test_printed_license_url_copies_swagger_license() -> None:
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({"title": "Radar"}) is None


def test_radar_is_a_registered_source() -> None:
    assert "radar" in SOURCE_IDS
    source = build_source("radar")
    assert isinstance(source, RadarSource)
    assert source.source_id == "radar"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = RadarSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 4
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "radar"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == LOCATIONS_URL
    assert row["title"] == "List available locations as GeoJSON FeatureCollection"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("met:")
    assert not str(row["id"]).startswith("nowcast:")
    assert not str(row["id"]).startswith("oceanforecast:")
    assert not str(row["id"]).startswith("sunrise:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["radar_openapi_path"] == "/locations"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_locations(tmp_path: Path) -> None:
    source = RadarSource(http=CatalogHttp())
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
    assert set(by_value) == {"Central Norway", "Finnmark"}
    assert by_value["Central Norway"]["measure"] == "name"
    assert by_value["Finnmark"]["measure"] == "title"
    dims = json.loads(by_value["Central Norway"]["dimensions_json"])
    assert dims["id"] == "central_norway"
    assert "resources" not in dims
    assert "collection" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == LOCATIONS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_location_name() -> None:
    cells = cells_from_radar(LOCATIONS_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "Central Norway"
    assert dims["id"] == "central_norway"
    assert "resources" not in dims
    assert "collection" not in dims
    fallback = cells_from_radar(
        {
            "type": "FeatureCollection",
            "features": [{"properties": {"id": "central_norway", "title": "Central Norway"}}],
        }
    )
    assert fallback == [("title", "Central Norway", {"id": "central_norway"})]
    with pytest.raises(ValueError, match="FeatureCollection"):
        cells_from_radar({"features": []})
    with pytest.raises(ValueError, match="features array"):
        cells_from_radar({"type": "FeatureCollection"})


def test_is_radar_url_accepts_only_radar_host_path() -> None:
    assert is_radar_url(LOCATIONS_URL)
    assert is_radar_url(OPENAPI_URL)
    assert radar_table_id(LOCATIONS_URL) == "locations"
    assert printed_endpoint_url(OPENAPI, "/locations", OPENAPI_URL) == LOCATIONS_URL
    assert not is_radar_url("https://api.met.no/weatherapi/nowcast/2.0/locations")
    assert not is_radar_url("https://api.met.no/weatherapi/oceanforecast/2.0/locations")
    assert not is_radar_url("https://api.met.no/weatherapi/airqualityforecast/0.1/stations")
    assert not is_radar_url("https://api.met.no/weatherapi/tidalwater/1.1/locations")
    assert not is_radar_url("https://api.met.no/weatherapi/sunrise/3.0/locations")
    assert not is_radar_url("https://api.met.no/weatherapi/metalerts/2.0/locations")
    assert not is_radar_url("https://ws.geonorge.no/hoydedata/v1/datakilder")
    assert not is_radar_url("https://data.norge.no/datasets/x")
    assert not is_radar_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = RadarSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "available"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["changelog"]
