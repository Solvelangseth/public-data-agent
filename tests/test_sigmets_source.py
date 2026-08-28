from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.sigmets import (
    SigmetsSource,
    cells_from_sigmets,
    is_sigmets_url,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
    sigmets_table_id,
)

OPENAPI_URL = "https://api.met.no/weatherapi/sigmets/2.0/swagger"
FEATURES_URL = "https://api.met.no/weatherapi/sigmets/2.0/features"
VALUES_URL = "https://api.met.no/weatherapi/sigmets/2.0/values"
CHANGELOG_URL = "https://api.met.no/weatherapi/sigmets/2.0/changelog"
LICENSE_URL = "http://creativecommons.org/licenses/by/4.0"
AVIATION_URL = "https://api.met.no/weatherapi/aviationforecast/2.0/locations"
SIGCHARTS_URL = "https://api.met.no/weatherapi/sigcharts/2.0/locations"
METALERTS_URL = "https://api.met.no/weatherapi/metalerts/2.0/locations"
DATASET_ID = "sigmets:features"

OPENAPI = {
    "swagger": "2.0",
    "info": {
        "title": "Sigmets",
        "description": "Aviation weather SIGMETs and AIRMETs for Norway",
        "license": {"name": "CC BY 4.0", "url": LICENSE_URL},
        "version": "2.0",
    },
    "basePath": "/weatherapi/sigmets/2.0",
    "paths": {
        "/": {
            "get": {
                "description": "Aviation weather SIGMETs and AIRMETs for Norway",
            }
        },
        "/available.{format}": {
            "get": {
                "description": "templated",
                "parameters": [
                    {"name": "format", "in": "path", "required": True, "type": "string"},
                ],
            }
        },
        "/airmets": {
            "get": {
                "description": "Aviation weather SIGMETs and AIRMETs for Norway",
            }
        },
        "/available": {
            "get": {
                "description": "List available resources as XML",
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
        "/sigmets": {
            "get": {
                "description": "Aviation weather SIGMETs and AIRMETs for Norway",
            }
        },
        "/values": {
            "get": {
                "description": "List allowed options for parameters",
            }
        },
        "/windshear": {
            "get": {
                "description": "Aviation weather SIGMETs and AIRMETs for Norway",
            }
        },
    },
}
FEATURES_BODY = {
    "copyright": "MET Norway",
    "features": [
        {
            "assets": {"data": {"title": "Sigmets type=airmets", "nested": True}},
            "id": "airmets",
            "properties": {},
            "type": "Feature",
        },
        {
            "assets": {"data": {"title": "Sigmets type=sigmets"}},
            "id": "sigmets",
            "properties": {},
            "type": "Feature",
        },
        {
            "id": "windshear",
            "properties": {},
            "type": "Feature",
        },
    ],
    "licenseURL": "https://api.met.no/license_data.html",
    "type": "FeatureCollection",
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
        raise AssertionError(f"sigmets fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_root_paths() -> None:
    source = SigmetsSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "airmets",
        "available",
        "changelog",
        "features",
        "healthz",
        "sigmets",
        "values",
        "windshear",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        "https://api.met.no/weatherapi/sigmets/2.0/airmets",
        "https://api.met.no/weatherapi/sigmets/2.0/available",
        CHANGELOG_URL,
        FEATURES_URL,
        "https://api.met.no/weatherapi/sigmets/2.0/healthz",
        "https://api.met.no/weatherapi/sigmets/2.0/sigmets",
        VALUES_URL,
        "https://api.met.no/weatherapi/sigmets/2.0/windshear",
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
            "basePath": "/weatherapi/sigmets/2.0",
            "schemes": ["https"],
        },
        "/features",
        OPENAPI_URL,
    )
    assert with_host == FEATURES_URL


def test_printed_operation_id_is_last_path_segment() -> None:
    assert printed_operation_id("/features") == "features"
    assert printed_operation_id("/windshear") == "windshear"


def test_printed_license_url_copies_swagger_license() -> None:
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({"title": "Sigmets"}) is None


def test_sigmets_is_a_registered_source() -> None:
    assert "sigmets" in SOURCE_IDS
    assert "npiintern" in SOURCE_IDS
    assert "sigcharts" in SOURCE_IDS
    assert "volcanicashforecast" in SOURCE_IDS
    source = build_source("sigmets")
    assert isinstance(source, SigmetsSource)
    assert source.source_id == "sigmets"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = SigmetsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 8
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "sigmets"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == FEATURES_URL
    assert row["title"] == "List available resources as OGC API FeatureCollection"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("met:")
    assert not str(row["id"]).startswith("sigcharts:")
    assert not str(row["id"]).startswith("npiintern:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["sigmets_openapi_path"] == "/features"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_features(tmp_path: Path) -> None:
    source = SigmetsSource(http=CatalogHttp())
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
    assert result.counts.listed == 3
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"airmets", "sigmets", "windshear"}
    assert all(row["measure"] == "id" for row in rows)
    assert json.loads(by_value["airmets"]["dimensions_json"]) == {"id": "airmets"}
    assert json.loads(by_value["sigmets"]["dimensions_json"]) == {"id": "sigmets"}
    assert json.loads(by_value["windshear"]["dimensions_json"]) == {"id": "windshear"}
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == FEATURES_URL for row in rows)
    registry.close()


def test_cells_copy_printed_feature_ids_and_value_arrays() -> None:
    cells = cells_from_sigmets(FEATURES_BODY)
    assert cells == [
        ("id", "airmets", {"id": "airmets"}),
        ("id", "sigmets", {"id": "sigmets"}),
        ("id", "windshear", {"id": "windshear"}),
    ]
    assert cells_from_sigmets({"type": ["airmets", "sigmets", "windshear"]}) == [
        ("type", "airmets", {"type": "airmets"}),
        ("type", "sigmets", {"type": "sigmets"}),
        ("type", "windshear", {"type": "windshear"}),
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_sigmets(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_sigmets({"type": "FeatureCollection", "features": []})


def test_is_sigmets_url_accepts_only_sigmets_host_path() -> None:
    assert is_sigmets_url(FEATURES_URL)
    assert is_sigmets_url(OPENAPI_URL)
    assert sigmets_table_id(FEATURES_URL) == "features"
    assert printed_endpoint_url(OPENAPI, "/features", OPENAPI_URL) == FEATURES_URL
    assert not is_sigmets_url(AVIATION_URL)
    assert not is_sigmets_url(SIGCHARTS_URL)
    assert not is_sigmets_url(METALERTS_URL)
    assert not is_sigmets_url("https://api.met.no/weatherapi/nowcast/2.0/locations")
    assert not is_sigmets_url("https://data.norge.no/datasets/x")
    assert not is_sigmets_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = SigmetsSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "airmets"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=3)
    assert [ref.source_native_id for ref in nxt] == ["features"]
