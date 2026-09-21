from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.offshoremaps import (
    OffshoremapsSource,
    cells_from_offshoremaps,
    is_offshoremaps_url,
    offshoremaps_table_id,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://api.met.no/weatherapi/offshoremaps/1.0/swagger"
FEATURES_URL = "https://api.met.no/weatherapi/offshoremaps/1.0/features"
AVAILABLE_URL = "https://api.met.no/weatherapi/offshoremaps/1.0/available"
LICENSE_URL = "http://creativecommons.org/licenses/by/4.0"
DATASET_ID = "offshoremaps:features"

OPENAPI = {
    "swagger": "2.0",
    "info": {
        "title": "Offshoremaps",
        "description": "Something goes here...",
        "license": {"name": "CC BY 4.0", "url": LICENSE_URL},
        "version": "1.0",
    },
    "basePath": "/weatherapi/offshoremaps/1.0",
    "paths": {
        "/": {
            "get": {
                "description": "Something goes here...",
                "parameters": [
                    {"name": "area", "in": "query", "required": True, "type": "string"},
                    {"name": "time", "in": "query", "required": False, "type": "string"},
                    {"name": "type", "in": "query", "required": False, "type": "string"},
                ],
            }
        },
        "/available": {
            "get": {
                "description": "List available resources as XML",
                "parameters": [
                    {"name": "area", "in": "query", "required": False, "type": "string"},
                    {"name": "type", "in": "query", "required": False, "type": "string"},
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
        "/helicopterlightningobservations": {
            "get": {
                "description": "Something goes here...",
                "parameters": [
                    {"name": "area", "in": "query", "required": True, "type": "string"},
                ],
            }
        },
        "/helicoptersignificantwaveheight": {
            "get": {
                "description": "Something goes here...",
                "parameters": [
                    {"name": "area", "in": "query", "required": True, "type": "string"},
                ],
            }
        },
        "/helicoptertriggeredlightningindex": {
            "get": {
                "description": "Something goes here...",
                "parameters": [
                    {"name": "area", "in": "query", "required": True, "type": "string"},
                ],
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
            "id": "MidNorway_obs_20260827T18",
            "properties": {"datetime": "2026-08-27T18:00:00Z"},
            "geometry": {"type": "Polygon", "coordinates": []},
            "assets": {
                "visual": {
                    "href": "https://api.met.no/weatherapi/offshoremaps/1.0/helicopterlightningobservations?area=central_norway",
                    "roles": ["visual"],
                }
            },
        },
        {
            "type": "Feature",
            "id": "named_area",
            "properties": {
                "name": "Central Norway",
                "datetime": "2026-08-27T18:00:00Z",
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
        if url == FEATURES_URL:
            return JsonResponse(status=200, url=url, body=FEATURES_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"offshoremaps fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_required_param_paths() -> None:
    source = OffshoremapsSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "available",
        "changelog",
        "features",
        "healthz",
        "values",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        AVAILABLE_URL,
        "https://api.met.no/weatherapi/offshoremaps/1.0/changelog",
        FEATURES_URL,
        "https://api.met.no/weatherapi/offshoremaps/1.0/healthz",
        "https://api.met.no/weatherapi/offshoremaps/1.0/values",
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]
    assert "" not in [ref.source_native_id for ref in refs]


def test_endpoint_url_joins_printed_basepath_and_origin() -> None:
    url = printed_endpoint_url(OPENAPI, "/features", OPENAPI_URL)
    assert url == FEATURES_URL
    assert "/swagger" not in url
    with_host = printed_endpoint_url(
        {
            "host": "api.met.no",
            "basePath": "/weatherapi/offshoremaps/1.0",
            "schemes": ["https"],
        },
        "/features",
        OPENAPI_URL,
    )
    assert with_host == FEATURES_URL


def test_printed_operation_id_is_last_path_segment() -> None:
    assert printed_operation_id("/features") == "features"
    assert printed_operation_id("/healthz") == "healthz"


def test_printed_license_url_copies_swagger_license() -> None:
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({"title": "Offshoremaps"}) is None


def test_offshoremaps_is_a_registered_source() -> None:
    assert "offshoremaps" in SOURCE_IDS
    assert "isobaricgrib" in SOURCE_IDS
    assert "oslofjord" in SOURCE_IDS
    assert "metgc" in SOURCE_IDS
    source = build_source("offshoremaps")
    assert isinstance(source, OffshoremapsSource)
    assert source.source_id == "offshoremaps"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = OffshoremapsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 4
    assert counts.ignored == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "offshoremaps"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == FEATURES_URL
    assert row["title"] == "List available resources as OGC API FeatureCollection"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("met:")
    assert not str(row["id"]).startswith("isobaricgrib:")
    assert not str(row["id"]).startswith("oslofjord:")
    assert not str(row["id"]).startswith("metgc:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["offshoremaps_openapi_path"] == "/features"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_features(tmp_path: Path) -> None:
    source = OffshoremapsSource(http=CatalogHttp())
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
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {
        "MidNorway_obs_20260827T18",
        "Central Norway",
    }
    assert by_value["MidNorway_obs_20260827T18"]["measure"] == "id"
    dims = json.loads(by_value["MidNorway_obs_20260827T18"]["dimensions_json"])
    assert dims["datetime"] == "2026-08-27T18:00:00Z"
    assert "assets" not in dims
    assert "geometry" not in dims
    assert by_value["Central Norway"]["measure"] == "name"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == FEATURES_URL for row in rows)
    registry.close()


def test_cells_copy_printed_feature_id_or_name() -> None:
    cells = cells_from_offshoremaps(FEATURES_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "id"
    assert value == "MidNorway_obs_20260827T18"
    assert dims["datetime"] == "2026-08-27T18:00:00Z"
    assert "assets" not in dims
    measure, value, dims = cells[1]
    assert measure == "name"
    assert value == "Central Norway"
    fallback = cells_from_offshoremaps(
        {
            "type": "FeatureCollection",
            "features": [{"id": None, "properties": {"datetime": "2026-08-27T18:00:00Z"}}],
        }
    )
    assert fallback == [("datetime", "2026-08-27T18:00:00Z", {})]
    with pytest.raises(ValueError, match="FeatureCollection"):
        cells_from_offshoremaps({"features": []})
    with pytest.raises(ValueError, match="features array"):
        cells_from_offshoremaps({"type": "FeatureCollection"})


def test_is_offshoremaps_url_accepts_only_offshoremaps_host_path() -> None:
    assert is_offshoremaps_url(FEATURES_URL)
    assert is_offshoremaps_url(OPENAPI_URL)
    assert offshoremaps_table_id(FEATURES_URL) == "features"
    assert printed_endpoint_url(OPENAPI, "/features", OPENAPI_URL) == FEATURES_URL
    assert not is_offshoremaps_url("https://api.met.no/weatherapi/isobaricgrib/1.0/locations")
    assert not is_offshoremaps_url("https://api.met.no/weatherapi/oslofjord/0.1/locations")
    assert not is_offshoremaps_url("https://api.met.no/weatherapi/metgc/1.0/features")
    assert not is_offshoremaps_url("https://api.met.no/weatherapi/gribfiles/1.1/locations")
    assert not is_offshoremaps_url("https://api.met.no/weatherapi/nowcast/2.0/locations")
    assert not is_offshoremaps_url("https://api.met.no/weatherapi/metalerts/2.0/locations")
    assert not is_offshoremaps_url("https://ws.geonorge.no/hoydedata/v1/datakilder")
    assert not is_offshoremaps_url("https://ws.geonorge.no/transformering/v1/projeksjoner")
    assert not is_offshoremaps_url("https://data.norge.no/datasets/x")
    assert not is_offshoremaps_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = OffshoremapsSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "available"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=2)
    assert [ref.source_native_id for ref in nxt] == ["features"]
