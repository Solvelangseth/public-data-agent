from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.oslofjord import (
    OslofjordSource,
    cells_from_oslofjord,
    is_oslofjord_url,
    oslofjord_table_id,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://api.met.no/weatherapi/oslofjord/0.1/swagger"
LOCATIONS_URL = "https://api.met.no/weatherapi/oslofjord/0.1/locations"
FEATURES_URL = "https://api.met.no/weatherapi/oslofjord/0.1/features"
AVAILABLE_URL = "https://api.met.no/weatherapi/oslofjord/0.1/available"
LICENSE_URL = "http://creativecommons.org/licenses/by/4.0"
DATASET_ID = "oslofjord:locations"

OPENAPI = {
    "swagger": "2.0",
    "info": {
        "title": "Oslofjord",
        "description": "Something goes here...",
        "license": {"name": "CC BY 4.0", "url": LICENSE_URL},
        "version": "0.1",
    },
    "basePath": "/weatherapi/oslofjord/0.1",
    "paths": {
        "/": {
            "get": {
                "description": "Something goes here...",
                "parameters": [
                    {"name": "area", "in": "query", "required": True, "type": "string"},
                    {"name": "hour", "in": "query", "required": False, "type": "integer"},
                ],
            }
        },
        "/available": {
            "get": {
                "description": "List available resources as XML",
            },
            "parameters": [
                {"name": "area", "in": "query", "required": False, "type": "string"},
            ],
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
            },
            "parameters": [
                {"name": "area", "in": "query", "required": False, "type": "string"},
            ],
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
            },
            "parameters": [
                {"name": "param", "in": "query", "required": False, "type": "string"},
            ],
        },
    },
}
LOCATIONS_BODY = {
    "type": "FeatureCollection",
    "copyright": "MET Norway",
    "features": [
        {
            "type": "Feature",
            "id": "drammen1",
            "properties": {
                "collection": "oslofjord",
                "id": "drammen1",
                "name": "Drammensfjorden",
                "title": "Drammensfjorden",
                "resources": [
                    {
                        "description": "Chart",
                        "mimeType": "image/png",
                        "uri": "oslofjord?area=drammen1",
                    }
                ],
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[10.4, 59.6], [10.6, 59.6], [10.6, 59.8], [10.4, 59.8], [10.4, 59.6]]],
            },
        },
        {
            "type": "Feature",
            "id": "ferder1",
            "properties": {
                "name": "Indre fjord",
                "title": "Indre fjord",
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
        raise AssertionError(f"oslofjord fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_required_param_paths() -> None:
    source = OslofjordSource(http=CatalogHttp())
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
        "https://api.met.no/weatherapi/oslofjord/0.1/changelog",
        FEATURES_URL,
        "https://api.met.no/weatherapi/oslofjord/0.1/healthz",
        LOCATIONS_URL,
        "https://api.met.no/weatherapi/oslofjord/0.1/values",
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
            "basePath": "/weatherapi/oslofjord/0.1",
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
    assert printed_license_url({"title": "Oslofjord"}) is None


def test_oslofjord_is_a_registered_source() -> None:
    assert "oslofjord" in SOURCE_IDS
    assert "gribfiles" in SOURCE_IDS
    assert "soundprofile" in SOURCE_IDS
    assert "transformering" in SOURCE_IDS
    source = build_source("oslofjord")
    assert isinstance(source, OslofjordSource)
    assert source.source_id == "oslofjord"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = OslofjordSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 6
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "oslofjord"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == LOCATIONS_URL
    assert row["title"] == "List available locations as GeoJSON FeatureCollection"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("met:")
    assert not str(row["id"]).startswith("gribfiles:")
    assert not str(row["id"]).startswith("soundprofile:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["oslofjord_openapi_path"] == "/locations"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_locations(tmp_path: Path) -> None:
    source = OslofjordSource(http=CatalogHttp())
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
    assert set(by_value) == {"Drammensfjorden", "Indre fjord"}
    assert by_value["Drammensfjorden"]["measure"] == "name"
    dims = json.loads(by_value["Drammensfjorden"]["dimensions_json"])
    assert dims["id"] == "drammen1"
    assert dims["title"] == "Drammensfjorden"
    assert dims["collection"] == "oslofjord"
    assert "resources" not in dims
    assert "geometry" not in dims
    assert by_value["Indre fjord"]["measure"] == "name"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == LOCATIONS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_feature_name_or_id() -> None:
    cells = cells_from_oslofjord(LOCATIONS_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "Drammensfjorden"
    assert dims["id"] == "drammen1"
    assert dims["collection"] == "oslofjord"
    assert "resources" not in dims
    assert "geometry" not in dims
    measure, value, dims = cells[1]
    assert measure == "name"
    assert value == "Indre fjord"
    assert dims["id"] == "ferder1"
    fallback = cells_from_oslofjord(
        {
            "type": "FeatureCollection",
            "features": [{"id": None, "properties": {"title": "Ytre fjord"}}],
        }
    )
    assert fallback == [("title", "Ytre fjord", {})]
    with pytest.raises(ValueError, match="FeatureCollection"):
        cells_from_oslofjord({"features": []})
    with pytest.raises(ValueError, match="features array"):
        cells_from_oslofjord({"type": "FeatureCollection"})


def test_is_oslofjord_url_accepts_only_oslofjord_host_path() -> None:
    assert is_oslofjord_url(LOCATIONS_URL)
    assert is_oslofjord_url(OPENAPI_URL)
    assert oslofjord_table_id(LOCATIONS_URL) == "locations"
    assert printed_endpoint_url(OPENAPI, "/locations", OPENAPI_URL) == LOCATIONS_URL
    assert not is_oslofjord_url("https://api.met.no/weatherapi/gribfiles/1.1/locations")
    assert not is_oslofjord_url("https://api.met.no/weatherapi/soundprofile/1.0/locations")
    assert not is_oslofjord_url("https://api.met.no/weatherapi/metgc/1.0/features")
    assert not is_oslofjord_url("https://api.met.no/weatherapi/nowcast/2.0/locations")
    assert not is_oslofjord_url("https://api.met.no/weatherapi/metalerts/2.0/locations")
    assert not is_oslofjord_url("https://ws.geonorge.no/hoydedata/v1/datakilder")
    assert not is_oslofjord_url("https://data.norge.no/datasets/x")
    assert not is_oslofjord_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = OslofjordSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "available"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=4)
    assert [ref.source_native_id for ref in nxt] == ["locations"]
