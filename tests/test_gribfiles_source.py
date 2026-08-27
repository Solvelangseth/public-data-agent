from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.gribfiles import (
    GribfilesSource,
    cells_from_gribfiles,
    gribfiles_table_id,
    is_gribfiles_url,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://api.met.no/weatherapi/gribfiles/1.1/swagger"
LOCATIONS_URL = "https://api.met.no/weatherapi/gribfiles/1.1/locations"
FEATURES_URL = "https://api.met.no/weatherapi/gribfiles/1.1/features"
AVAILABLE_URL = "https://api.met.no/weatherapi/gribfiles/1.1/available"
LICENSE_URL = "http://creativecommons.org/licenses/by/4.0"
DATASET_ID = "gribfiles:locations"

OPENAPI = {
    "swagger": "2.0",
    "info": {
        "title": "Gribfiles",
        "description": "Serve GRIB files on the coast from Oslo and Western Norway",
        "license": {"name": "CC BY 4.0", "url": LICENSE_URL},
        "version": "1.1",
    },
    "basePath": "/weatherapi/gribfiles/1.1",
    "paths": {
        "/": {
            "get": {
                "description": "Serve GRIB files on the coast from Oslo and Western Norway",
                "parameters": [
                    {"name": "area", "in": "query", "required": True, "type": "string"},
                    {"name": "content", "in": "query", "required": True, "type": "string"},
                ],
            }
        },
        "/available": {
            "get": {
                "description": "List available resources as XML",
                "parameters": [
                    {"name": "area", "in": "query", "required": False, "type": "string"},
                    {"name": "content", "in": "query", "required": False, "type": "string"},
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
        "/current": {
            "get": {
                "description": "Serve GRIB files on the coast from Oslo and Western Norway",
                "parameters": [
                    {"name": "area", "in": "query", "required": True, "type": "string"},
                ],
            }
        },
        "/features": {
            "get": {
                "description": "List available resources as OGC API FeatureCollection",
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
        "/waves": {
            "get": {
                "description": "Serve GRIB files on the coast from Oslo and Western Norway",
                "parameters": [
                    {"name": "area", "in": "query", "required": True, "type": "string"},
                ],
            }
        },
        "/weather": {
            "get": {
                "description": "Serve GRIB files on the coast from Oslo and Western Norway",
                "parameters": [
                    {"name": "area", "in": "query", "required": True, "type": "string"},
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
            "id": "n-northsea",
            "properties": {
                "collection": ["current", "weather", "waves"],
                "id": "n-northsea",
                "name": "N-NORTHSEA",
                "title": "N-NORTHSEA",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-2.0, 58.5], [6.0, 58.5], [6.0, 62.0], [-2.0, 62.0], [-2.0, 58.5]]],
            },
        },
        {
            "type": "Feature",
            "id": "oslofjord",
            "properties": {
                "name": "OSLOFJORD",
                "title": "OSLOFJORD",
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
        raise AssertionError(f"gribfiles fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_required_param_paths() -> None:
    source = GribfilesSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "available",
        "changelog",
        "features",
        "locations",
        "values",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        AVAILABLE_URL,
        "https://api.met.no/weatherapi/gribfiles/1.1/changelog",
        FEATURES_URL,
        LOCATIONS_URL,
        "https://api.met.no/weatherapi/gribfiles/1.1/values",
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
            "basePath": "/weatherapi/gribfiles/1.1",
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
    assert printed_license_url({"title": "Gribfiles"}) is None


def test_gribfiles_is_a_registered_source() -> None:
    assert "gribfiles" in SOURCE_IDS
    assert "soundprofile" in SOURCE_IDS
    assert "transformering" in SOURCE_IDS
    assert "polarsatellite" in SOURCE_IDS
    source = build_source("gribfiles")
    assert isinstance(source, GribfilesSource)
    assert source.source_id == "gribfiles"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = GribfilesSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 5
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "gribfiles"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == LOCATIONS_URL
    assert row["title"] == "List available locations as GeoJSON FeatureCollection"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("met:")
    assert not str(row["id"]).startswith("soundprofile:")
    assert not str(row["id"]).startswith("transformering:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["gribfiles_openapi_path"] == "/locations"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_locations(tmp_path: Path) -> None:
    source = GribfilesSource(http=CatalogHttp())
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
    assert set(by_value) == {"N-NORTHSEA", "OSLOFJORD"}
    assert by_value["N-NORTHSEA"]["measure"] == "name"
    dims = json.loads(by_value["N-NORTHSEA"]["dimensions_json"])
    assert dims["id"] == "n-northsea"
    assert dims["title"] == "N-NORTHSEA"
    assert "collection" not in dims
    assert "geometry" not in dims
    assert "resources" not in dims
    assert by_value["OSLOFJORD"]["measure"] == "name"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == LOCATIONS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_feature_name_or_id() -> None:
    cells = cells_from_gribfiles(LOCATIONS_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "N-NORTHSEA"
    assert dims["id"] == "n-northsea"
    assert "collection" not in dims
    assert "geometry" not in dims
    measure, value, dims = cells[1]
    assert measure == "name"
    assert value == "OSLOFJORD"
    assert dims["id"] == "oslofjord"
    fallback = cells_from_gribfiles(
        {
            "type": "FeatureCollection",
            "features": [{"id": None, "properties": {"title": "WEST_NORWAY"}}],
        }
    )
    assert fallback == [("title", "WEST_NORWAY", {})]
    with pytest.raises(ValueError, match="FeatureCollection"):
        cells_from_gribfiles({"features": []})
    with pytest.raises(ValueError, match="features array"):
        cells_from_gribfiles({"type": "FeatureCollection"})


def test_is_gribfiles_url_accepts_only_gribfiles_host_path() -> None:
    assert is_gribfiles_url(LOCATIONS_URL)
    assert is_gribfiles_url(OPENAPI_URL)
    assert gribfiles_table_id(LOCATIONS_URL) == "locations"
    assert printed_endpoint_url(OPENAPI, "/locations", OPENAPI_URL) == LOCATIONS_URL
    assert not is_gribfiles_url("https://api.met.no/weatherapi/soundprofile/1.0/locations")
    assert not is_gribfiles_url("https://api.met.no/weatherapi/polarsatellite/1.1/locations")
    assert not is_gribfiles_url("https://api.met.no/weatherapi/geosatellite/1.4/features")
    assert not is_gribfiles_url("https://api.met.no/weatherapi/metgm/1.0/features")
    assert not is_gribfiles_url("https://api.met.no/weatherapi/nowcast/2.0/locations")
    assert not is_gribfiles_url("https://api.met.no/weatherapi/metalerts/2.0/locations")
    assert not is_gribfiles_url("https://ws.geonorge.no/hoydedata/v1/datakilder")
    assert not is_gribfiles_url("https://ws.geonorge.no/transformering/v1/projeksjoner")
    assert not is_gribfiles_url("https://data.norge.no/datasets/x")
    assert not is_gribfiles_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = GribfilesSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "available"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=3)
    assert [ref.source_native_id for ref in nxt] == ["locations"]
