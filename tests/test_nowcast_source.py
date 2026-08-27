from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.nowcast import (
    NowcastSource,
    cells_from_nowcast,
    is_nowcast_url,
    nowcast_table_id,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://api.met.no/weatherapi/nowcast/2.0/swagger"
LOCATIONS_URL = "https://api.met.no/weatherapi/nowcast/2.0/locations"
CHANGELOG_URL = "https://api.met.no/weatherapi/nowcast/2.0/changelog"
LICENSE_URL = "http://creativecommons.org/licenses/by/4.0"
DATASET_ID = "nowcast:locations"

OPENAPI = {
    "swagger": "2.0",
    "info": {
        "title": "Nowcast",
        "description": "Immediate weather forecast for specified locations in the Nordic area",
        "license": {"name": "CC BY 4.0", "url": LICENSE_URL},
        "version": "2.0",
    },
    "basePath": "/weatherapi/nowcast/2.0",
    "paths": {
        "/changelog": {
            "get": {
                "description": "RSS feed of changes to this product",
            }
        },
        "/classic.{format}": {
            "get": {
                "description": "templated",
            }
        },
        "/locations": {
            "get": {
                "description": "List available locations as GeoJSON FeatureCollection",
            }
        },
        "/status": {
            "get": {
                "description": "Immediate weather forecast for specified locations in the Nordic area",
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
                "resources": [
                    {
                        "description": "complete.json",
                        "mimeType": "application/geo+json",
                    }
                ],
            },
            "geometry": {"type": "Polygon", "coordinates": [[[1.9, 52.3], [2.3, 52.3]]]},
        },
        {
            "type": "Feature",
            "properties": {
                "id": "fallback",
                "title": "Fallback area",
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
        raise AssertionError(f"nowcast fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_paths() -> None:
    source = NowcastSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["changelog", "locations", "status"]
    assert [ref.source_native_uri for ref in refs] == [
        CHANGELOG_URL,
        LOCATIONS_URL,
        "https://api.met.no/weatherapi/nowcast/2.0/status",
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_joins_printed_basepath_and_origin() -> None:
    url = printed_endpoint_url(OPENAPI, "/locations", OPENAPI_URL)
    assert url == LOCATIONS_URL
    assert "/swagger" not in url
    with_host = printed_endpoint_url(
        {"host": "api.met.no", "basePath": "/weatherapi/nowcast/2.0", "schemes": ["https"]},
        "/locations",
        OPENAPI_URL,
    )
    assert with_host == LOCATIONS_URL


def test_printed_operation_id_is_last_path_segment() -> None:
    assert printed_operation_id("/locations") == "locations"
    assert printed_operation_id("/changelog") == "changelog"


def test_printed_license_url_copies_swagger_license() -> None:
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({"title": "Nowcast"}) is None


def test_nowcast_is_a_registered_source() -> None:
    assert "nowcast" in SOURCE_IDS
    source = build_source("nowcast")
    assert isinstance(source, NowcastSource)
    assert source.source_id == "nowcast"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = NowcastSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nowcast"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == LOCATIONS_URL
    assert row["title"] == "List available locations as GeoJSON FeatureCollection"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("met:")
    assert not str(row["id"]).startswith("hoydedata:")
    assert not str(row["id"]).startswith("ngu:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["nowcast_openapi_path"] == "/locations"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_locations(tmp_path: Path) -> None:
    source = NowcastSource(http=CatalogHttp())
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
    assert set(by_value) == {"MEPS area", "Fallback area"}
    assert by_value["MEPS area"]["measure"] == "name"
    assert by_value["Fallback area"]["measure"] == "title"
    dims = json.loads(by_value["MEPS area"]["dimensions_json"])
    assert dims["id"] == "meps"
    assert "resources" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == LOCATIONS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_location_name() -> None:
    cells = cells_from_nowcast(LOCATIONS_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "MEPS area"
    assert dims["id"] == "meps"
    assert "resources" not in dims
    fallback = cells_from_nowcast(
        {
            "type": "FeatureCollection",
            "features": [{"properties": {"id": "meps", "title": "MEPS area"}}],
        }
    )
    assert fallback == [("title", "MEPS area", {"id": "meps"})]
    with pytest.raises(ValueError, match="FeatureCollection"):
        cells_from_nowcast({"features": []})
    with pytest.raises(ValueError, match="features array"):
        cells_from_nowcast({"type": "FeatureCollection"})


def test_is_nowcast_url_accepts_only_nowcast_host_path() -> None:
    assert is_nowcast_url(LOCATIONS_URL)
    assert is_nowcast_url(OPENAPI_URL)
    assert nowcast_table_id(LOCATIONS_URL) == "locations"
    assert printed_endpoint_url(OPENAPI, "/locations", OPENAPI_URL) == LOCATIONS_URL
    assert not is_nowcast_url("https://api.met.no/weatherapi/metalerts/2.0/locations")
    assert not is_nowcast_url("https://api.met.no/weatherapi/locationforecast/2.0/complete")
    assert not is_nowcast_url("https://ws.geonorge.no/hoydedata/v1/datakilder")
    assert not is_nowcast_url("https://geo.ngu.no/api/features/ankringsforhold")
    assert not is_nowcast_url("https://data.norge.no/datasets/x")
    assert not is_nowcast_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = NowcastSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "changelog"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["locations"]
