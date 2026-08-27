from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.subseasonal import (
    SubseasonalSource,
    cells_from_subseasonal,
    is_subseasonal_url,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
    subseasonal_table_id,
)

OPENAPI_URL = "https://api.met.no/weatherapi/subseasonal/1.0/swagger"
LOCATIONS_URL = "https://api.met.no/weatherapi/subseasonal/1.0/locations"
COMPLETE_URL = "https://api.met.no/weatherapi/subseasonal/1.0/complete"
LICENSE_URL = "http://creativecommons.org/licenses/by/4.0"
DATASET_ID = "subseasonal:locations"

OPENAPI = {
    "swagger": "2.0",
    "info": {
        "title": "Subseasonal",
        "description": "Long term weather forecast for specified locations in the Nordic area",
        "license": {"name": "CC BY 4.0", "url": LICENSE_URL},
        "version": "1.0",
    },
    "basePath": "/weatherapi/subseasonal/1.0",
    "paths": {
        "/changelog": {
            "get": {
                "description": "RSS feed of changes to this product",
            }
        },
        "/complete": {
            "get": {
                "description": "Long term weather forecast for specified locations in the Nordic area",
                "parameters": [
                    {
                        "name": "lat",
                        "in": "query",
                        "required": True,
                        "type": "number",
                    },
                    {
                        "name": "lon",
                        "in": "query",
                        "required": True,
                        "type": "number",
                    },
                ],
            }
        },
        "/complete.{format}": {
            "get": {
                "description": "templated",
            }
        },
        "/coverage": {
            "get": {
                "description": "Long term weather forecast for specified locations in the Nordic area",
            }
        },
        "/coverage.{format}": {
            "get": {
                "description": "templated",
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
        "/status": {
            "get": {
                "description": "Long term weather forecast for specified locations in the Nordic area",
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
            "id": "meps",
            "properties": {
                "id": "meps",
                "name": "MEPS area",
                "title": "MEPS area",
            },
            "geometry": {"type": "Polygon", "coordinates": []},
        }
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
        raise AssertionError(f"subseasonal fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_paths() -> None:
    source = SubseasonalSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "changelog",
        "complete",
        "coverage",
        "healthz",
        "locations",
        "status",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        "https://api.met.no/weatherapi/subseasonal/1.0/changelog",
        COMPLETE_URL,
        "https://api.met.no/weatherapi/subseasonal/1.0/coverage",
        "https://api.met.no/weatherapi/subseasonal/1.0/healthz",
        LOCATIONS_URL,
        "https://api.met.no/weatherapi/subseasonal/1.0/status",
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
            "basePath": "/weatherapi/subseasonal/1.0",
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
    assert printed_license_url({"title": "Subseasonal"}) is None


def test_subseasonal_is_a_registered_source() -> None:
    assert "subseasonal" in SOURCE_IDS
    assert "ncagalewarnings" in SOURCE_IDS
    assert "icemap" in SOURCE_IDS
    assert "tafmetar" in SOURCE_IDS
    source = build_source("subseasonal")
    assert isinstance(source, SubseasonalSource)
    assert source.source_id == "subseasonal"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = SubseasonalSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 6
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "subseasonal"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == LOCATIONS_URL
    assert row["title"] == "List available locations as GeoJSON FeatureCollection"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("met:")
    assert not str(row["id"]).startswith("nowcast:")
    assert not str(row["id"]).startswith("ncagalewarnings:")
    assert not str(row["id"]).startswith("tafmetar:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["subseasonal_openapi_path"] == "/locations"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_locations(tmp_path: Path) -> None:
    source = SubseasonalSource(http=CatalogHttp())
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
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"MEPS area"}
    assert by_value["MEPS area"]["measure"] == "name"
    dims = json.loads(by_value["MEPS area"]["dimensions_json"])
    assert dims["id"] == "meps"
    assert "resources" not in dims
    assert "geometry" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == LOCATIONS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_location_name() -> None:
    cells = cells_from_subseasonal(LOCATIONS_BODY)
    assert len(cells) == 1
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "MEPS area"
    assert dims["id"] == "meps"
    assert "resources" not in dims
    fallback = cells_from_subseasonal(
        {
            "type": "FeatureCollection",
            "features": [{"id": "meps", "properties": {"title": "MEPS area"}}],
        }
    )
    assert fallback == [("title", "MEPS area", {"id": "meps"})]
    with pytest.raises(ValueError, match="FeatureCollection"):
        cells_from_subseasonal({"features": []})
    with pytest.raises(ValueError, match="features array"):
        cells_from_subseasonal({"type": "FeatureCollection"})


def test_is_subseasonal_url_accepts_only_subseasonal_host_path() -> None:
    assert is_subseasonal_url(LOCATIONS_URL)
    assert is_subseasonal_url(OPENAPI_URL)
    assert subseasonal_table_id(LOCATIONS_URL) == "locations"
    assert printed_endpoint_url(OPENAPI, "/locations", OPENAPI_URL) == LOCATIONS_URL
    assert not is_subseasonal_url("https://api.met.no/weatherapi/nowcast/2.0/locations")
    assert not is_subseasonal_url("https://api.met.no/weatherapi/metalerts/2.0/locations")
    assert not is_subseasonal_url("https://api.met.no/weatherapi/ncagalewarnings/1.0/locations")
    assert not is_subseasonal_url("https://api.met.no/weatherapi/icemap/1.0/locations")
    assert not is_subseasonal_url("https://api.met.no/weatherapi/tafmetar/1.0/locations")
    assert not is_subseasonal_url("https://api.met.no/weatherapi/spotwind/1.1/locations")
    assert not is_subseasonal_url("https://api.met.no/weatherapi/textforecast/3.0/landoverview")
    assert not is_subseasonal_url("https://ws.geonorge.no/hoydedata/v1/datakilder")
    assert not is_subseasonal_url("https://data.norge.no/datasets/x")
    assert not is_subseasonal_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = SubseasonalSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "changelog"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=4)
    assert [ref.source_native_id for ref in nxt] == ["locations"]
