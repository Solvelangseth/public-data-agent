from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.aviationforecast import (
    AviationforecastSource,
    cells_from_aviationforecast,
    is_aviationforecast_url,
    aviationforecast_table_id,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://api.met.no/weatherapi/aviationforecast/2.0/swagger"
AVAILABLE_URL = "https://api.met.no/weatherapi/aviationforecast/2.0/available"
CHANGELOG_URL = "https://api.met.no/weatherapi/aviationforecast/2.0/changelog"
FEATURES_URL = "https://api.met.no/weatherapi/aviationforecast/2.0/features"
HEALTHZ_URL = "https://api.met.no/weatherapi/aviationforecast/2.0/healthz"
LOCATIONS_URL = "https://api.met.no/weatherapi/aviationforecast/2.0/locations"
VALUES_URL = "https://api.met.no/weatherapi/aviationforecast/2.0/values"
LICENSE_URL = "http://creativecommons.org/licenses/by/4.0"
DATASET_ID = "aviationforecast:locations"
SIGMETS_URL = "https://api.met.no/weatherapi/sigmets/2.0/features"
LOCATIONFORECAST_URL = "https://api.met.no/weatherapi/locationforecast/2.0/locations"
TAFMETAR_URL = "https://api.met.no/weatherapi/tafmetar/1.0/locations"
GREP_URL = "https://data.udir.no/kl06/v201906/aarstrinn"
REGOBS_URL = "https://api.regobs.no/v5/KdvElements"

OPENAPI = {
    "swagger": "2.0",
    "info": {
        "title": "Aviationforecast",
        "description": "Textual aviation weather forecasts",
        "license": {"name": "CC BY 4.0", "url": LICENSE_URL},
        "version": "2.0",
    },
    "basePath": "/weatherapi/aviationforecast/2.0",
    "paths": {
        "/available": {
            "get": {
                "description": "List available resources as XML",
                "parameters": [
                    {"name": "type", "in": "query", "required": False, "type": "string"},
                ],
            }
        },
        "/available.{format}": {
            "get": {
                "description": "templated",
                "parameters": [
                    {"name": "type", "in": "query", "required": False, "type": "string"},
                    {"name": "format", "in": "path", "required": True, "type": "string"},
                ],
            }
        },
        "/aw": {
            "get": {
                "description": "Textual aviation weather forecasts",
                "parameters": [
                    {"name": "icao", "in": "query", "required": True, "type": "string"},
                ],
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
                "parameters": [
                    {"name": "type", "in": "query", "required": False, "type": "string"},
                ],
            }
        },
        "/healthz": {
            "get": {
                "description": "Check health status for product",
            }
        },
        "/iga": {
            "get": {
                "description": "Textual aviation weather forecasts",
                "parameters": [
                    {"name": "wmoheader", "in": "query", "required": True, "type": "string"},
                ],
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
                "parameters": [
                    {"name": "param", "in": "query", "required": False, "type": "string"},
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
            "id": "ENBR",
            "properties": {
                "id": "ENBR",
                "name": "BERGEN/FLESLAND",
                "title": "BERGEN/FLESLAND",
                "type": "ICAO",
                "resources": [{"uri": "aw?icao=ENBR", "mimeType": "text/plain"}],
            },
            "geometry": {"type": "Point", "coordinates": [5.23, 60.28]},
        },
        {
            "type": "Feature",
            "id": "ENGM",
            "properties": {
                "name": "OSLO/GARDERMOEN",
                "title": "OSLO/GARDERMOEN",
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
        raise AssertionError(f"aviationforecast fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_required_param_paths() -> None:
    source = AviationforecastSource(http=CatalogHttp())
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
        CHANGELOG_URL,
        FEATURES_URL,
        HEALTHZ_URL,
        LOCATIONS_URL,
        VALUES_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]
    assert "" not in [ref.source_native_id for ref in refs]
    assert all(ref.source_native_id != "aw" for ref in refs)
    assert all(ref.source_native_id != "iga" for ref in refs)
    assert all("available." not in (ref.source_native_id or "") for ref in refs)


def test_endpoint_url_joins_printed_basepath_and_origin() -> None:
    url = printed_endpoint_url(OPENAPI, "/locations", OPENAPI_URL)
    assert url == LOCATIONS_URL
    assert "/swagger" not in url
    with_host = printed_endpoint_url(
        {
            "host": "api.met.no",
            "basePath": "/weatherapi/aviationforecast/2.0",
            "schemes": ["https"],
        },
        "/locations",
        OPENAPI_URL,
    )
    assert with_host == LOCATIONS_URL


def test_printed_operation_id_is_last_path_segment() -> None:
    assert printed_operation_id("/locations") == "locations"
    assert printed_operation_id("/values") == "values"


def test_printed_license_url_copies_swagger_license() -> None:
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({"title": "Aviationforecast"}) is None


def test_aviationforecast_is_a_registered_source() -> None:
    assert "aviationforecast" in SOURCE_IDS
    assert "locationforecast" in SOURCE_IDS
    assert "tafmetar" in SOURCE_IDS
    assert "regobs" in SOURCE_IDS
    assert "sigmets" in SOURCE_IDS
    assert "grep" in SOURCE_IDS
    assert "kvwms" in SOURCE_IDS
    source = build_source("aviationforecast")
    assert isinstance(source, AviationforecastSource)
    assert source.source_id == "aviationforecast"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = AviationforecastSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 5
    assert counts.ignored == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "aviationforecast"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == LOCATIONS_URL
    assert row["title"] == "List available locations as GeoJSON FeatureCollection"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("met:")
    assert not str(row["id"]).startswith("locationforecast:")
    assert not str(row["id"]).startswith("sigmets:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["aviationforecast_openapi_path"] == "/locations"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_locations(tmp_path: Path) -> None:
    source = AviationforecastSource(http=CatalogHttp())
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
    assert set(by_value) == {"BERGEN/FLESLAND", "OSLO/GARDERMOEN"}
    assert by_value["BERGEN/FLESLAND"]["measure"] == "name"
    dims = json.loads(by_value["BERGEN/FLESLAND"]["dimensions_json"])
    assert dims["id"] == "ENBR"
    assert dims["title"] == "BERGEN/FLESLAND"
    assert "geometry" not in dims
    assert "resources" not in dims
    assert by_value["OSLO/GARDERMOEN"]["measure"] == "name"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == LOCATIONS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_feature_name_or_id() -> None:
    cells = cells_from_aviationforecast(LOCATIONS_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "BERGEN/FLESLAND"
    assert dims["id"] == "ENBR"
    assert dims["title"] == "BERGEN/FLESLAND"
    assert "geometry" not in dims
    assert "resources" not in dims
    measure, value, dims = cells[1]
    assert measure == "name"
    assert value == "OSLO/GARDERMOEN"
    assert dims["id"] == "ENGM"
    fallback = cells_from_aviationforecast(
        {
            "type": "FeatureCollection",
            "features": [{"id": None, "properties": {"title": "BERGEN/FLESLAND"}}],
        }
    )
    assert fallback == [("title", "BERGEN/FLESLAND", {})]
    with pytest.raises(ValueError, match="FeatureCollection"):
        cells_from_aviationforecast({"features": []})
    with pytest.raises(ValueError, match="features array"):
        cells_from_aviationforecast({"type": "FeatureCollection"})


def test_is_aviationforecast_url_accepts_only_aviationforecast_host_path() -> None:
    assert is_aviationforecast_url(LOCATIONS_URL)
    assert is_aviationforecast_url(OPENAPI_URL)
    assert aviationforecast_table_id(LOCATIONS_URL) == "locations"
    assert printed_endpoint_url(OPENAPI, "/locations", OPENAPI_URL) == LOCATIONS_URL
    assert not is_aviationforecast_url(LOCATIONFORECAST_URL)
    assert not is_aviationforecast_url(SIGMETS_URL)
    assert not is_aviationforecast_url("https://api.met.no/weatherapi/sigmets/2.0/swagger")
    assert not is_aviationforecast_url(TAFMETAR_URL)
    assert not is_aviationforecast_url("https://api.met.no/weatherapi/metalerts/2.0/locations")
    assert not is_aviationforecast_url(GREP_URL)
    assert not is_aviationforecast_url(REGOBS_URL)
    assert not is_aviationforecast_url("https://data.norge.no/datasets/x")
    assert not is_aviationforecast_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = AviationforecastSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "available"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=4)
    assert [ref.source_native_id for ref in nxt] == ["locations"]
