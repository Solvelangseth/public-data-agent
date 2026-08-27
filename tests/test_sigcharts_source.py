from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.sigcharts import (
    SigchartsSource,
    cells_from_sigcharts,
    is_sigcharts_url,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
    sigcharts_table_id,
)

OPENAPI_URL = "https://api.met.no/weatherapi/sigcharts/2.0/swagger"
LOCATIONS_URL = "https://api.met.no/weatherapi/sigcharts/2.0/locations"
FEATURES_URL = "https://api.met.no/weatherapi/sigcharts/2.0/features"
AVAILABLE_URL = "https://api.met.no/weatherapi/sigcharts/2.0/available"
LICENSE_URL = "http://creativecommons.org/licenses/by/4.0"
DATASET_ID = "sigcharts:locations"

OPENAPI = {
    "swagger": "2.0",
    "info": {
        "title": "Sigcharts",
        "description": "Significant Weather Charts for aviation",
        "license": {"name": "CC BY 4.0", "url": LICENSE_URL},
        "version": "2.0",
    },
    "basePath": "/weatherapi/sigcharts/2.0",
    "paths": {
        "/": {
            "get": {
                "description": "Significant Weather Charts for aviation",
                "parameters": [
                    {"name": "area", "in": "query", "required": False, "type": "string"},
                    {"name": "offset", "in": "query", "required": False, "type": "integer"},
                    {"name": "time", "in": "query", "required": False, "type": "string"},
                ],
            }
        },
        "/available": {
            "get": {
                "description": "List available resources as XML",
                "parameters": [
                    {"name": "area", "in": "query", "required": False, "type": "string"},
                ],
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
        "/features": {
            "get": {
                "description": "List available resources as OGC API FeatureCollection",
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
        "/values": {
            "get": {
                "description": "List allowed options for parameters",
            }
        },
        "/.{format}": {
            "get": {
                "description": "templated root",
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
            "id": "nordic",
            "properties": {
                "collection": "sigcharts",
                "id": "nordic",
                "name": "Nordic",
                "title": "Nordic",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 50], [40, 50], [40, 80], [0, 80], [0, 50]]],
            },
        },
        {
            "type": "Feature",
            "id": "norway",
            "properties": {
                "name": "Norway",
                "title": "Norway",
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
        raise AssertionError(f"sigcharts fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_root_path() -> None:
    source = SigchartsSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "available",
        "changelog",
        "features",
        "healthz",
        "locations",
        "values",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        AVAILABLE_URL,
        "https://api.met.no/weatherapi/sigcharts/2.0/changelog",
        FEATURES_URL,
        "https://api.met.no/weatherapi/sigcharts/2.0/healthz",
        LOCATIONS_URL,
        "https://api.met.no/weatherapi/sigcharts/2.0/values",
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]
    assert "" not in [ref.source_native_id for ref in refs]


def test_endpoint_url_joins_printed_basepath_and_origin() -> None:
    url = printed_endpoint_url(OPENAPI, "/locations", OPENAPI_URL)
    assert url == LOCATIONS_URL
    assert "/swagger" not in url
    with_host = printed_endpoint_url(
        {
            "host": "api.met.no",
            "basePath": "/weatherapi/sigcharts/2.0",
            "schemes": ["https"],
        },
        "/locations",
        OPENAPI_URL,
    )
    assert with_host == LOCATIONS_URL


def test_printed_operation_id_is_last_path_segment() -> None:
    assert printed_operation_id("/locations") == "locations"
    assert printed_operation_id("/features") == "features"


def test_printed_license_url_copies_swagger_license() -> None:
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({"title": "Sigcharts"}) is None


def test_sigcharts_is_a_registered_source() -> None:
    assert "sigcharts" in SOURCE_IDS
    assert "turbulence" in SOURCE_IDS
    assert "offshoremaps" in SOURCE_IDS
    assert "isobaricgrib" in SOURCE_IDS
    assert "oslofjord" in SOURCE_IDS
    source = build_source("sigcharts")
    assert isinstance(source, SigchartsSource)
    assert source.source_id == "sigcharts"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = SigchartsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 6
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "sigcharts"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == LOCATIONS_URL
    assert row["title"] == "List available locations as GeoJSON FeatureCollection"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("met:")
    assert not str(row["id"]).startswith("turbulence:")
    assert not str(row["id"]).startswith("nlaroutes:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["sigcharts_openapi_path"] == "/locations"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_locations(tmp_path: Path) -> None:
    source = SigchartsSource(http=CatalogHttp())
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
    assert set(by_value) == {"Nordic", "Norway"}
    assert by_value["Nordic"]["measure"] == "name"
    dims = json.loads(by_value["Nordic"]["dimensions_json"])
    assert dims["id"] == "nordic"
    assert dims["title"] == "Nordic"
    assert dims["collection"] == "sigcharts"
    assert "geometry" not in dims
    assert by_value["Norway"]["measure"] == "name"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == LOCATIONS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_feature_name_or_id() -> None:
    cells = cells_from_sigcharts(LOCATIONS_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "Nordic"
    assert dims["id"] == "nordic"
    assert dims["collection"] == "sigcharts"
    assert "geometry" not in dims
    measure, value, dims = cells[1]
    assert measure == "name"
    assert value == "Norway"
    assert dims["id"] == "norway"
    fallback = cells_from_sigcharts(
        {
            "type": "FeatureCollection",
            "features": [{"id": None, "properties": {"title": "Norway"}}],
        }
    )
    assert fallback == [("title", "Norway", {})]
    with pytest.raises(ValueError, match="FeatureCollection"):
        cells_from_sigcharts({"features": []})
    with pytest.raises(ValueError, match="features array"):
        cells_from_sigcharts({"type": "FeatureCollection"})


def test_is_sigcharts_url_accepts_only_sigcharts_host_path() -> None:
    assert is_sigcharts_url(LOCATIONS_URL)
    assert is_sigcharts_url(OPENAPI_URL)
    assert sigcharts_table_id(LOCATIONS_URL) == "locations"
    assert printed_endpoint_url(OPENAPI, "/locations", OPENAPI_URL) == LOCATIONS_URL
    assert not is_sigcharts_url("https://api.met.no/weatherapi/turbulence/2.0/locations")
    assert not is_sigcharts_url("https://api.met.no/weatherapi/nlaroutes/1.0/locations")
    assert not is_sigcharts_url("https://api.met.no/weatherapi/offshoremaps/1.0/features")
    assert not is_sigcharts_url("https://api.met.no/weatherapi/isobaricgrib/1.0/locations")
    assert not is_sigcharts_url("https://api.met.no/weatherapi/nowcast/2.0/locations")
    assert not is_sigcharts_url("https://api.met.no/weatherapi/metalerts/2.0/locations")
    assert not is_sigcharts_url("https://ws.geonorge.no/hoydedata/v1/datakilder")
    assert not is_sigcharts_url("https://ws.geonorge.no/transformering/v1/projeksjoner")
    assert not is_sigcharts_url("https://data.norge.no/datasets/x")
    assert not is_sigcharts_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = SigchartsSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "available"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=4)
    assert [ref.source_native_id for ref in nxt] == ["locations"]
