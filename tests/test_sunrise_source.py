from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.sunrise import (
    SunriseSource,
    cells_from_sunrise,
    is_sunrise_url,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
    sunrise_table_id,
)

OPENAPI_URL = "https://api.met.no/weatherapi/sunrise/3.0/swagger"
LOCATIONS_URL = "https://api.met.no/weatherapi/sunrise/3.0/locations"
CHANGELOG_URL = "https://api.met.no/weatherapi/sunrise/3.0/changelog"
LICENSE_URL = "http://creativecommons.org/licenses/by/4.0"
DATASET_ID = "sunrise:locations"

OPENAPI = {
    "swagger": "2.0",
    "info": {
        "title": "Sunrise",
        "description": "Sunrise and moon events",
        "license": {"name": "CC BY 4.0", "url": LICENSE_URL},
        "version": "3.0",
    },
    "basePath": "/weatherapi/sunrise/3.0",
    "paths": {
        "/changelog": {
            "get": {
                "description": "RSS feed of changes to this product",
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
        "/moon": {
            "get": {
                "description": "Calculate sun or moon events, as seen from a specific location on Earth",
            }
        },
        "/sun.{format}": {
            "get": {
                "description": "templated",
            }
        },
        "/sun": {
            "get": {
                "description": "Calculate sun or moon events, as seen from a specific location on Earth",
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
            "id": "World",
            "properties": {
                "id": "World",
                "name": "Whole Earth Catalogue",
                "title": "Whole Earth Catalogue",
                "resources": [
                    {
                        "description": "sun",
                        "mimeType": "application/geo+json",
                        "params": ["lat", "lon"],
                        "uri": "sun",
                    }
                ],
            },
            "geometry": {"type": "Polygon", "coordinates": []},
        },
        {
            "type": "Feature",
            "properties": {
                "id": "fallback",
                "title": "Fallback location",
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
        raise AssertionError(f"sunrise fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_paths() -> None:
    source = SunriseSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "changelog",
        "healthz",
        "locations",
        "moon",
        "sun",
        "values",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        CHANGELOG_URL,
        "https://api.met.no/weatherapi/sunrise/3.0/healthz",
        LOCATIONS_URL,
        "https://api.met.no/weatherapi/sunrise/3.0/moon",
        "https://api.met.no/weatherapi/sunrise/3.0/sun",
        "https://api.met.no/weatherapi/sunrise/3.0/values",
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_joins_printed_basepath_and_origin() -> None:
    url = printed_endpoint_url(OPENAPI, "/locations", OPENAPI_URL)
    assert url == LOCATIONS_URL
    assert "/swagger" not in url
    with_host = printed_endpoint_url(
        {
            "host": "api.met.no",
            "basePath": "/weatherapi/sunrise/3.0",
            "schemes": ["https"],
        },
        "/locations",
        OPENAPI_URL,
    )
    assert with_host == LOCATIONS_URL


def test_printed_operation_id_is_last_path_segment() -> None:
    assert printed_operation_id("/locations") == "locations"
    assert printed_operation_id("/healthz") == "healthz"


def test_printed_license_url_copies_swagger_license() -> None:
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({"title": "Sunrise"}) is None


def test_sunrise_is_a_registered_source() -> None:
    assert "sunrise" in SOURCE_IDS
    assert "tidalwater" in SOURCE_IDS
    source = build_source("sunrise")
    assert isinstance(source, SunriseSource)
    assert source.source_id == "sunrise"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = SunriseSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 6
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "sunrise"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == LOCATIONS_URL
    assert row["title"] == "List available locations as GeoJSON FeatureCollection"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("met:")
    assert not str(row["id"]).startswith("nowcast:")
    assert not str(row["id"]).startswith("airquality:")
    assert not str(row["id"]).startswith("tidalwater:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["sunrise_openapi_path"] == "/locations"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_locations(tmp_path: Path) -> None:
    source = SunriseSource(http=CatalogHttp())
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
    assert set(by_value) == {"Whole Earth Catalogue", "Fallback location"}
    assert by_value["Whole Earth Catalogue"]["measure"] == "name"
    assert by_value["Fallback location"]["measure"] == "title"
    dims = json.loads(by_value["Whole Earth Catalogue"]["dimensions_json"])
    assert dims["id"] == "World"
    assert "resources" not in dims
    assert "geometry" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == LOCATIONS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_location_name() -> None:
    cells = cells_from_sunrise(LOCATIONS_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "Whole Earth Catalogue"
    assert dims["id"] == "World"
    assert "resources" not in dims
    fallback = cells_from_sunrise(
        {
            "type": "FeatureCollection",
            "features": [{"properties": {"id": "World", "title": "Whole Earth Catalogue"}}],
        }
    )
    assert fallback == [("title", "Whole Earth Catalogue", {"id": "World"})]
    with pytest.raises(ValueError, match="FeatureCollection"):
        cells_from_sunrise({"features": []})
    with pytest.raises(ValueError, match="features array"):
        cells_from_sunrise({"type": "FeatureCollection"})


def test_is_sunrise_url_accepts_only_sunrise_host_path() -> None:
    assert is_sunrise_url(LOCATIONS_URL)
    assert is_sunrise_url(OPENAPI_URL)
    assert sunrise_table_id(LOCATIONS_URL) == "locations"
    assert printed_endpoint_url(OPENAPI, "/locations", OPENAPI_URL) == LOCATIONS_URL
    assert not is_sunrise_url("https://api.met.no/weatherapi/nowcast/2.0/locations")
    assert not is_sunrise_url("https://api.met.no/weatherapi/metalerts/2.0/locations")
    assert not is_sunrise_url("https://api.met.no/weatherapi/tidalwater/1.1/locations")
    assert not is_sunrise_url(
        "https://api.met.no/weatherapi/airqualityforecast/0.1/stations"
    )
    assert not is_sunrise_url(
        "https://api.met.no/weatherapi/oceanforecast/2.0/locations"
    )
    assert not is_sunrise_url("https://ws.geonorge.no/hoydedata/v1/datakilder")
    assert not is_sunrise_url("https://data.norge.no/datasets/x")
    assert not is_sunrise_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = SunriseSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "changelog"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=2)
    assert [ref.source_native_id for ref in nxt] == ["locations"]
