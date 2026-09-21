from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.metgc import (
    MetgcSource,
    cells_from_metgc,
    is_metgc_url,
    metgc_table_id,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://api.met.no/weatherapi/metgc/1.0/swagger"
FEATURES_URL = "https://api.met.no/weatherapi/metgc/1.0/features"
AVAILABLE_URL = "https://api.met.no/weatherapi/metgc/1.0/available"
LICENSE_URL = "http://creativecommons.org/licenses/by/4.0"
DATASET_ID = "metgc:features"

OPENAPI = {
    "swagger": "2.0",
    "info": {
        "title": "Metgc",
        "description": "Deliver meteorological forecast data in METGM/C format for defined areas",
        "license": {"name": "CC BY 4.0", "url": LICENSE_URL},
        "version": "1.0",
    },
    "basePath": "/weatherapi/metgc/1.0",
    "paths": {
        "/": {
            "get": {
                "description": "Deliver meteorological forecast data in METGM/C format for defined areas",
                "parameters": [
                    {"name": "area", "in": "query", "required": True, "type": "string"},
                    {"name": "time", "in": "query", "required": True, "type": "string"},
                ],
            }
        },
        "/available": {
            "get": {
                "description": "List available resources as XML",
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
            "id": "setermoen2_F_20260823_2100Z_0_NOR0_1835E_6880N",
            "properties": {"datetime": "2026-08-23T21:00:00Z"},
            "geometry": {"type": "Polygon", "coordinates": []},
            "assets": {
                "data": {
                    "href": "https://api.met.no/weatherapi/metgc/1.0/?area=setermoen2&time=2026-08-23T21%3A00%3A00Z",
                    "roles": ["data"],
                }
            },
        },
        {
            "type": "Feature",
            "id": "named_area",
            "properties": {
                "name": "Setermoen",
                "datetime": "2026-08-23T21:00:00Z",
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
        raise AssertionError(f"metgc fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_required_param_paths() -> None:
    source = MetgcSource(http=CatalogHttp())
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
        "https://api.met.no/weatherapi/metgc/1.0/changelog",
        FEATURES_URL,
        "https://api.met.no/weatherapi/metgc/1.0/healthz",
        "https://api.met.no/weatherapi/metgc/1.0/values",
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
            "basePath": "/weatherapi/metgc/1.0",
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
    assert printed_license_url({"title": "Metgc"}) is None


def test_metgc_is_a_registered_source() -> None:
    assert "metgc" in SOURCE_IDS
    assert "soundprofile" in SOURCE_IDS
    assert "transformering" in SOURCE_IDS
    assert "polarsatellite" in SOURCE_IDS
    source = build_source("metgc")
    assert isinstance(source, MetgcSource)
    assert source.source_id == "metgc"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = MetgcSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 4
    assert counts.ignored == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "metgc"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == FEATURES_URL
    assert row["title"] == "List available resources as OGC API FeatureCollection"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("met:")
    assert not str(row["id"]).startswith("metgm:")
    assert not str(row["id"]).startswith("soundprofile:")
    assert not str(row["id"]).startswith("transformering:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["metgc_openapi_path"] == "/features"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_features(tmp_path: Path) -> None:
    source = MetgcSource(http=CatalogHttp())
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
        "setermoen2_F_20260823_2100Z_0_NOR0_1835E_6880N",
        "Setermoen",
    }
    assert by_value["setermoen2_F_20260823_2100Z_0_NOR0_1835E_6880N"]["measure"] == "id"
    dims = json.loads(by_value["setermoen2_F_20260823_2100Z_0_NOR0_1835E_6880N"]["dimensions_json"])
    assert dims["datetime"] == "2026-08-23T21:00:00Z"
    assert "assets" not in dims
    assert "geometry" not in dims
    assert by_value["Setermoen"]["measure"] == "name"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == FEATURES_URL for row in rows)
    registry.close()


def test_cells_copy_printed_feature_id_or_name() -> None:
    cells = cells_from_metgc(FEATURES_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "id"
    assert value == "setermoen2_F_20260823_2100Z_0_NOR0_1835E_6880N"
    assert dims["datetime"] == "2026-08-23T21:00:00Z"
    assert "assets" not in dims
    measure, value, dims = cells[1]
    assert measure == "name"
    assert value == "Setermoen"
    fallback = cells_from_metgc(
        {
            "type": "FeatureCollection",
            "features": [{"id": None, "properties": {"datetime": "2026-08-23T21:00:00Z"}}],
        }
    )
    assert fallback == [("datetime", "2026-08-23T21:00:00Z", {})]
    with pytest.raises(ValueError, match="FeatureCollection"):
        cells_from_metgc({"features": []})
    with pytest.raises(ValueError, match="features array"):
        cells_from_metgc({"type": "FeatureCollection"})


def test_is_metgc_url_accepts_only_metgc_host_path() -> None:
    assert is_metgc_url(FEATURES_URL)
    assert is_metgc_url(OPENAPI_URL)
    assert metgc_table_id(FEATURES_URL) == "features"
    assert printed_endpoint_url(OPENAPI, "/features", OPENAPI_URL) == FEATURES_URL
    assert not is_metgc_url("https://api.met.no/weatherapi/metgm/1.0/features")
    assert not is_metgc_url("https://api.met.no/weatherapi/soundprofile/1.0/locations")
    assert not is_metgc_url("https://api.met.no/weatherapi/polarsatellite/1.1/locations")
    assert not is_metgc_url("https://api.met.no/weatherapi/geosatellite/1.4/features")
    assert not is_metgc_url("https://api.met.no/weatherapi/nowcast/2.0/locations")
    assert not is_metgc_url("https://api.met.no/weatherapi/metalerts/2.0/locations")
    assert not is_metgc_url("https://ws.geonorge.no/hoydedata/v1/datakilder")
    assert not is_metgc_url("https://ws.geonorge.no/transformering/v1/projeksjoner")
    assert not is_metgc_url("https://data.norge.no/datasets/x")
    assert not is_metgc_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = MetgcSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "available"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=2)
    assert [ref.source_native_id for ref in nxt] == ["features"]
