from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.subjectiveforecast import (
    SubjectiveforecastSource,
    cells_from_subjectiveforecast,
    is_subjectiveforecast_url,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
    subjectiveforecast_table_id,
)

OPENAPI_URL = "https://api.met.no/weatherapi/subjectiveforecast/1.0/swagger"
FEATURES_URL = "https://api.met.no/weatherapi/subjectiveforecast/1.0/features"
CHANGELOG_URL = "https://api.met.no/weatherapi/subjectiveforecast/1.0/changelog"
LICENSE_URL = "http://creativecommons.org/licenses/by/4.0"
DATASET_ID = "subjectiveforecast:features"

OPENAPI = {
    "swagger": "2.0",
    "info": {
        "title": "Subjectiveforecast",
        "description": "Forecasts and analyses charts from the meteorologist",
        "license": {"name": "CC BY 4.0", "url": LICENSE_URL},
        "version": "1.0",
    },
    "basePath": "/weatherapi/subjectiveforecast/1.0",
    "paths": {
        "/": {
            "get": {
                "description": "Forecasts and analyses charts from the meteorologist",
                "parameters": [
                    {"name": "content_type", "required": False, "in": "query"},
                    {"name": "product", "required": True, "in": "query"},
                    {"name": "time", "required": False, "in": "query"},
                ],
            }
        },
        "/available": {
            "get": {
                "description": "List available resources as XML",
            },
            "parameters": [
                {"name": "content_type", "required": False, "in": "query"},
                {"name": "product", "required": False, "in": "query"},
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
                {"name": "content_type", "required": False, "in": "query"},
                {"name": "product", "required": False, "in": "query"},
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
            "id": "analyse_20260825T18",
            "properties": {"datetime": "2026-08-25T18:00:00Z"},
            "assets": {
                "visual": {
                    "title": "Subjectiveforecast content_type=image/png, product=analyse_map",
                    "type": "image/png",
                }
            },
            "geometry": {"FIXME": "NOW"},
        },
        {
            "type": "Feature",
            "id": "prognose_20260828T12",
            "properties": {"datetime": "2026-08-28T12:00:00Z"},
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
        raise AssertionError(f"subjectiveforecast fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_root_image_path() -> None:
    source = SubjectiveforecastSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "available",
        "changelog",
        "features",
        "healthz",
        "values",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        "https://api.met.no/weatherapi/subjectiveforecast/1.0/available",
        CHANGELOG_URL,
        FEATURES_URL,
        "https://api.met.no/weatherapi/subjectiveforecast/1.0/healthz",
        "https://api.met.no/weatherapi/subjectiveforecast/1.0/values",
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
            "basePath": "/weatherapi/subjectiveforecast/1.0",
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
    assert printed_license_url({"title": "Subjectiveforecast"}) is None


def test_subjectiveforecast_is_a_registered_source() -> None:
    assert "subjectiveforecast" in SOURCE_IDS
    assert "geosatellite" in SOURCE_IDS
    assert "tafmetar" in SOURCE_IDS
    assert "subseasonal" in SOURCE_IDS
    source = build_source("subjectiveforecast")
    assert isinstance(source, SubjectiveforecastSource)
    assert source.source_id == "subjectiveforecast"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = SubjectiveforecastSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 5
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "subjectiveforecast"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == FEATURES_URL
    assert row["title"] == "List available resources as OGC API FeatureCollection"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("met:")
    assert not str(row["id"]).startswith("nowcast:")
    assert not str(row["id"]).startswith("geosatellite:")
    assert not str(row["id"]).startswith("tafmetar:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["subjectiveforecast_openapi_path"] == "/features"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_features(tmp_path: Path) -> None:
    source = SubjectiveforecastSource(http=CatalogHttp())
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
        "analyse_20260825T18",
        "prognose_20260828T12",
    }
    assert by_id["analyse_20260825T18"]["measure"] == "datetime"
    assert json.loads(by_id["analyse_20260825T18"]["value_json"]) == "2026-08-25T18:00:00Z"
    dims = json.loads(by_id["analyse_20260825T18"]["dimensions_json"])
    assert dims["id"] == "analyse_20260825T18"
    assert "assets" not in dims
    assert "geometry" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == FEATURES_URL for row in rows)
    registry.close()


def test_cells_copy_printed_feature_id() -> None:
    cells = cells_from_subjectiveforecast(FEATURES_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "datetime"
    assert value == "2026-08-25T18:00:00Z"
    assert dims["id"] == "analyse_20260825T18"
    assert "assets" not in dims
    fallback = cells_from_subjectiveforecast(
        {
            "type": "FeatureCollection",
            "features": [
                {"properties": {"title": "analyse map", "datetime": "2026-08-25T18:00:00Z"}}
            ],
        }
    )
    assert fallback == [
        ("title", "analyse map", {"datetime": "2026-08-25T18:00:00Z"})
    ]
    with pytest.raises(ValueError, match="FeatureCollection"):
        cells_from_subjectiveforecast({"features": []})
    with pytest.raises(ValueError, match="features array"):
        cells_from_subjectiveforecast({"type": "FeatureCollection"})


def test_is_subjectiveforecast_url_accepts_only_subjectiveforecast_host_path() -> None:
    assert is_subjectiveforecast_url(FEATURES_URL)
    assert is_subjectiveforecast_url(OPENAPI_URL)
    assert subjectiveforecast_table_id(FEATURES_URL) == "features"
    assert printed_endpoint_url(OPENAPI, "/features", OPENAPI_URL) == FEATURES_URL
    assert not is_subjectiveforecast_url("https://api.met.no/weatherapi/geosatellite/1.4/features")
    assert not is_subjectiveforecast_url("https://api.met.no/weatherapi/metgm/1.0/features")
    assert not is_subjectiveforecast_url("https://api.met.no/weatherapi/nowcast/2.0/locations")
    assert not is_subjectiveforecast_url("https://api.met.no/weatherapi/oceanforecast/2.0/locations")
    assert not is_subjectiveforecast_url("https://api.met.no/weatherapi/airqualityforecast/0.1/stations")
    assert not is_subjectiveforecast_url("https://api.met.no/weatherapi/tidalwater/1.1/locations")
    assert not is_subjectiveforecast_url("https://api.met.no/weatherapi/sunrise/3.0/locations")
    assert not is_subjectiveforecast_url("https://api.met.no/weatherapi/metalerts/2.0/locations")
    assert not is_subjectiveforecast_url("https://api.met.no/weatherapi/radar/2.0/locations")
    assert not is_subjectiveforecast_url("https://api.met.no/weatherapi/spotwind/1.1/locations")
    assert not is_subjectiveforecast_url("https://api.met.no/weatherapi/textforecast/3.0/landoverview")
    assert not is_subjectiveforecast_url("https://api.met.no/weatherapi/icemap/1.0/locations")
    assert not is_subjectiveforecast_url("https://api.met.no/weatherapi/ncagalewarnings/1.0/locations")
    assert not is_subjectiveforecast_url("https://api.met.no/weatherapi/tafmetar/1.0/locations")
    assert not is_subjectiveforecast_url("https://api.met.no/weatherapi/subseasonal/1.0/locations")
    assert not is_subjectiveforecast_url("https://ws.geonorge.no/hoydedata/v1/datakilder")
    assert not is_subjectiveforecast_url("https://data.norge.no/datasets/x")
    assert not is_subjectiveforecast_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = SubjectiveforecastSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "available"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["changelog"]
