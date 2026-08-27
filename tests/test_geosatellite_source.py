from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.geosatellite import (
    GeosatelliteSource,
    cells_from_geosatellite,
    geosatellite_table_id,
    is_geosatellite_url,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://api.met.no/weatherapi/geosatellite/1.4/swagger"
FEATURES_URL = "https://api.met.no/weatherapi/geosatellite/1.4/features"
CHANGELOG_URL = "https://api.met.no/weatherapi/geosatellite/1.4/changelog"
LICENSE_URL = "http://creativecommons.org/licenses/by/4.0"
DATASET_ID = "geosatellite:features"

OPENAPI = {
    "swagger": "2.0",
    "info": {
        "title": "Geosatellite",
        "description": "Images from geostationary satellites",
        "license": {"name": "CC BY 4.0", "url": LICENSE_URL},
        "version": "1.4",
    },
    "basePath": "/weatherapi/geosatellite/1.4",
    "paths": {
        "/": {
            "get": {
                "description": "Images from geostationary satellites",
                "parameters": [
                    {"name": "area", "required": False, "in": "query"},
                    {"name": "size", "required": False, "in": "query"},
                    {"name": "time", "required": False, "in": "query"},
                    {"name": "type", "required": False, "in": "query"},
                ],
            }
        },
        "/.{format}": {
            "get": {
                "description": "templated image product",
                "parameters": [{"name": "format", "required": True, "in": "path"}],
            }
        },
        "/available": {
            "get": {
                "description": "List available resources as XML",
            },
            "parameters": [
                {"name": "area", "required": False, "in": "query"},
            ],
        },
        "/available.{format}": {
            "get": {
                "description": "templated",
                "parameters": [{"name": "format", "required": True, "in": "path"}],
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
            },
            "parameters": [
                {"name": "area", "required": False, "in": "query"},
                {"name": "size", "required": False, "in": "query"},
                {"name": "type", "required": False, "in": "query"},
            ],
        },
        "/healthz": {
            "get": {
                "description": "Check health status for product",
            }
        },
        "/values": {
            "get": {
                "description": "List allowed options for parameters",
            }
        },
    },
}
FEATURES_BODY = {
    "type": "FeatureCollection",
    "copyright": "MET Norway",
    "licenseURL": "https://api.met.no/license_data.html",
    "features": [
        {
            "type": "Feature",
            "id": "Mediterranean-Sea-VIS-20240601074500",
            "properties": {"datetime": "2024-06-01T07:45:00Z"},
            "assets": {
                "visual": {
                    "title": "Geosatellite area=mediterranean, size=normal, type=visible",
                    "type": "image/png",
                }
            },
            "geometry": {"FIXME": "NOW"},
        },
        {
            "type": "Feature",
            "id": "Europe-IR-20240601080000",
            "properties": {"datetime": "2024-06-01T08:00:00Z"},
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
        if url == FEATURES_URL:
            return JsonResponse(status=200, url=url, body=FEATURES_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"geosatellite fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_root_image_path() -> None:
    source = GeosatelliteSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "available",
        "changelog",
        "features",
        "healthz",
        "values",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        "https://api.met.no/weatherapi/geosatellite/1.4/available",
        CHANGELOG_URL,
        FEATURES_URL,
        "https://api.met.no/weatherapi/geosatellite/1.4/healthz",
        "https://api.met.no/weatherapi/geosatellite/1.4/values",
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]
    assert "" not in [ref.source_native_id for ref in refs]
    assert "." not in [ref.source_native_id for ref in refs]


def test_endpoint_url_joins_printed_basepath_and_origin() -> None:
    url = printed_endpoint_url(OPENAPI, "/features", OPENAPI_URL)
    assert url == FEATURES_URL
    assert "/swagger" not in url
    with_host = printed_endpoint_url(
        {
            "host": "api.met.no",
            "basePath": "/weatherapi/geosatellite/1.4",
            "schemes": ["https"],
        },
        "/features",
        OPENAPI_URL,
    )
    assert with_host == FEATURES_URL


def test_printed_operation_id_is_last_path_segment() -> None:
    assert printed_operation_id("/features") == "features"
    assert printed_operation_id("/changelog") == "changelog"


def test_printed_license_url_copies_swagger_license() -> None:
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({"title": "Geosatellite"}) is None


def test_geosatellite_is_a_registered_source() -> None:
    assert "geosatellite" in SOURCE_IDS
    assert "tafmetar" in SOURCE_IDS
    assert "icemap" in SOURCE_IDS
    assert "ncagalewarnings" in SOURCE_IDS
    source = build_source("geosatellite")
    assert isinstance(source, GeosatelliteSource)
    assert source.source_id == "geosatellite"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = GeosatelliteSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 5
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "geosatellite"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == FEATURES_URL
    assert row["title"] == "List available resources as OGC API FeatureCollection"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("met:")
    assert not str(row["id"]).startswith("nowcast:")
    assert not str(row["id"]).startswith("tafmetar:")
    assert not str(row["id"]).startswith("icemap:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["geosatellite_openapi_path"] == "/features"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_features(tmp_path: Path) -> None:
    source = GeosatelliteSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == FEATURES_URL
    assert result.table_id == "features"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_id = {json.loads(row["dimensions_json"]).get("id"): row for row in rows}
    assert set(by_id) == {
        "Mediterranean-Sea-VIS-20240601074500",
        "Europe-IR-20240601080000",
    }
    assert by_id["Mediterranean-Sea-VIS-20240601074500"]["measure"] == "datetime"
    assert json.loads(by_id["Mediterranean-Sea-VIS-20240601074500"]["value_json"]) == (
        "2024-06-01T07:45:00Z"
    )
    dims = json.loads(by_id["Mediterranean-Sea-VIS-20240601074500"]["dimensions_json"])
    assert dims["id"] == "Mediterranean-Sea-VIS-20240601074500"
    assert "assets" not in dims
    assert "geometry" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == FEATURES_URL for row in rows)
    registry.close()


def test_cells_copy_printed_feature_id() -> None:
    cells = cells_from_geosatellite(FEATURES_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "datetime"
    assert value == "2024-06-01T07:45:00Z"
    assert dims["id"] == "Mediterranean-Sea-VIS-20240601074500"
    assert "assets" not in dims
    fallback = cells_from_geosatellite(
        {
            "type": "FeatureCollection",
            "features": [{"properties": {"title": "mediterranean visible", "datetime": "2024-06-01T07:45:00Z"}}],
        }
    )
    assert fallback == [
        ("title", "mediterranean visible", {"datetime": "2024-06-01T07:45:00Z"})
    ]
    with pytest.raises(ValueError, match="FeatureCollection"):
        cells_from_geosatellite({"features": []})
    with pytest.raises(ValueError, match="features array"):
        cells_from_geosatellite({"type": "FeatureCollection"})


def test_is_geosatellite_url_accepts_only_geosatellite_host_path() -> None:
    assert is_geosatellite_url(FEATURES_URL)
    assert is_geosatellite_url(OPENAPI_URL)
    assert geosatellite_table_id(FEATURES_URL) == "features"
    assert printed_endpoint_url(OPENAPI, "/features", OPENAPI_URL) == FEATURES_URL
    assert not is_geosatellite_url("https://api.met.no/weatherapi/nowcast/2.0/locations")
    assert not is_geosatellite_url("https://api.met.no/weatherapi/oceanforecast/2.0/locations")
    assert not is_geosatellite_url("https://api.met.no/weatherapi/airqualityforecast/0.1/stations")
    assert not is_geosatellite_url("https://api.met.no/weatherapi/tidalwater/1.1/locations")
    assert not is_geosatellite_url("https://api.met.no/weatherapi/sunrise/3.0/locations")
    assert not is_geosatellite_url("https://api.met.no/weatherapi/metalerts/2.0/locations")
    assert not is_geosatellite_url("https://api.met.no/weatherapi/radar/2.0/locations")
    assert not is_geosatellite_url("https://api.met.no/weatherapi/spotwind/1.1/locations")
    assert not is_geosatellite_url("https://api.met.no/weatherapi/textforecast/3.0/landoverview")
    assert not is_geosatellite_url("https://api.met.no/weatherapi/icemap/1.0/locations")
    assert not is_geosatellite_url("https://api.met.no/weatherapi/ncagalewarnings/1.0/locations")
    assert not is_geosatellite_url("https://api.met.no/weatherapi/tafmetar/1.0/locations")
    assert not is_geosatellite_url("https://ws.geonorge.no/hoydedata/v1/datakilder")
    assert not is_geosatellite_url("https://data.norge.no/datasets/x")
    assert not is_geosatellite_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = GeosatelliteSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "available"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["changelog"]
