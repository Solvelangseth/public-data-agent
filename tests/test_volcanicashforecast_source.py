from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.volcanicashforecast import (
    VolcanicashforecastSource,
    cells_from_volcanicashforecast,
    is_volcanicashforecast_url,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
    volcanicashforecast_table_id,
)

OPENAPI_URL = "https://api.met.no/weatherapi/volcanicashforecast/0.1/swagger"
REFTIMES_URL = "https://api.met.no/weatherapi/volcanicashforecast/0.1/reftimes"
RESOURCES_URL = "https://api.met.no/weatherapi/volcanicashforecast/0.1/resources"
CHANGELOG_URL = "https://api.met.no/weatherapi/volcanicashforecast/0.1/changelog"
LICENSE_URL = "http://creativecommons.org/licenses/by/4.0"
DATASET_ID = "volcanicashforecast:reftimes"

OPENAPI = {
    "swagger": "2.0",
    "info": {
        "title": "Volcanicashforecast",
        "description": "Something goes here...",
        "license": {"name": "CC BY 4.0", "url": LICENSE_URL},
        "version": "0.1",
    },
    "basePath": "/weatherapi/volcanicashforecast/0.1",
    "paths": {
        "/": {
            "get": {
                "description": "Something goes here...",
            }
        },
        "/.{format}": {
            "get": {
                "description": "templated",
                "parameters": [
                    {"name": "format", "in": "path", "required": True, "type": "string"},
                ],
            }
        },
        "/changelog": {
            "get": {
                "description": "RSS feed of changes to this product",
            }
        },
        "/healthz": {
            "get": {
                "description": "Check health status for product",
            }
        },
        "/reftimes": {
            "get": {
                "description": "Something goes here...",
            }
        },
        "/resources": {
            "get": {
                "description": "Something goes here...",
            }
        },
    },
}
REFTIMES_BODY = {
    "reftimes": [
        "2026-06-09T11:00:00Z",
        "2026-06-09T10:00:00Z",
        "2026-05-12T16:00:00Z",
    ]
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
        if url == REFTIMES_URL:
            return JsonResponse(status=200, url=url, body=REFTIMES_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"volcanicashforecast fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_root_paths() -> None:
    source = VolcanicashforecastSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "changelog",
        "healthz",
        "reftimes",
        "resources",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        CHANGELOG_URL,
        "https://api.met.no/weatherapi/volcanicashforecast/0.1/healthz",
        REFTIMES_URL,
        RESOURCES_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]
    assert "" not in [ref.source_native_id for ref in refs]


def test_endpoint_url_joins_printed_basepath_and_origin() -> None:
    url = printed_endpoint_url(OPENAPI, "/reftimes", OPENAPI_URL)
    assert url == REFTIMES_URL
    assert "/swagger" not in url
    with_host = printed_endpoint_url(
        {
            "host": "api.met.no",
            "basePath": "/weatherapi/volcanicashforecast/0.1",
            "schemes": ["https"],
        },
        "/reftimes",
        OPENAPI_URL,
    )
    assert with_host == REFTIMES_URL


def test_printed_operation_id_is_last_path_segment() -> None:
    assert printed_operation_id("/reftimes") == "reftimes"
    assert printed_operation_id("/healthz") == "healthz"


def test_printed_license_url_copies_swagger_license() -> None:
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({"title": "Volcanicashforecast"}) is None


def test_volcanicashforecast_is_a_registered_source() -> None:
    assert "volcanicashforecast" in SOURCE_IDS
    assert "sigcharts" in SOURCE_IDS
    assert "nlaroutes" in SOURCE_IDS
    assert "turbulence" in SOURCE_IDS
    assert "offshoremaps" in SOURCE_IDS
    source = build_source("volcanicashforecast")
    assert isinstance(source, VolcanicashforecastSource)
    assert source.source_id == "volcanicashforecast"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = VolcanicashforecastSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    assert counts.ignored == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "volcanicashforecast"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == REFTIMES_URL
    assert row["title"] == "Something goes here..."
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("met:")
    assert not str(row["id"]).startswith("nlaroutes:")
    assert not str(row["id"]).startswith("turbulence:")
    assert not str(row["id"]).startswith("sigcharts:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["volcanicashforecast_openapi_path"] == "/reftimes"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_reftimes(tmp_path: Path) -> None:
    source = VolcanicashforecastSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == REFTIMES_URL
    assert result.table_id == "reftimes"
    assert result.http_status == 200
    assert result.counts.listed == 3
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == [
        "2026-06-09T11:00:00Z",
        "2026-06-09T10:00:00Z",
        "2026-05-12T16:00:00Z",
    ]
    assert all(row["measure"] == "reftimes" for row in rows)
    assert [json.loads(row["dimensions_json"]) for row in rows] == [
        {"reftimes": "2026-06-09T11:00:00Z"},
        {"reftimes": "2026-06-09T10:00:00Z"},
        {"reftimes": "2026-05-12T16:00:00Z"},
    ]
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == REFTIMES_URL for row in rows)
    registry.close()


def test_cells_copy_printed_reftimes() -> None:
    cells = cells_from_volcanicashforecast(REFTIMES_BODY)
    assert cells == [
        ("reftimes", "2026-06-09T11:00:00Z", {"reftimes": "2026-06-09T11:00:00Z"}),
        ("reftimes", "2026-06-09T10:00:00Z", {"reftimes": "2026-06-09T10:00:00Z"}),
        ("reftimes", "2026-05-12T16:00:00Z", {"reftimes": "2026-05-12T16:00:00Z"}),
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_volcanicashforecast(["2026-06-09T11:00:00Z"])
    with pytest.raises(ValueError, match="reftimes array"):
        cells_from_volcanicashforecast({"type": "FeatureCollection"})


def test_is_volcanicashforecast_url_accepts_only_volcanicashforecast_host_path() -> None:
    assert is_volcanicashforecast_url(REFTIMES_URL)
    assert is_volcanicashforecast_url(OPENAPI_URL)
    assert volcanicashforecast_table_id(REFTIMES_URL) == "reftimes"
    assert printed_endpoint_url(OPENAPI, "/reftimes", OPENAPI_URL) == REFTIMES_URL
    assert not is_volcanicashforecast_url(
        "https://api.met.no/weatherapi/nlaroutes/1.0/locations"
    )
    assert not is_volcanicashforecast_url(
        "https://api.met.no/weatherapi/turbulence/2.0/locations"
    )
    assert not is_volcanicashforecast_url(
        "https://api.met.no/weatherapi/sigcharts/2.0/locations"
    )
    assert not is_volcanicashforecast_url(
        "https://api.met.no/weatherapi/offshoremaps/1.0/features"
    )
    assert not is_volcanicashforecast_url(
        "https://api.met.no/weatherapi/nowcast/2.0/locations"
    )
    assert not is_volcanicashforecast_url(
        "https://api.met.no/weatherapi/metalerts/2.0/locations"
    )
    assert not is_volcanicashforecast_url("https://ws.geonorge.no/hoydedata/v1/datakilder")
    assert not is_volcanicashforecast_url(
        "https://ws.geonorge.no/transformering/v1/projeksjoner"
    )
    assert not is_volcanicashforecast_url("https://data.norge.no/datasets/x")
    assert not is_volcanicashforecast_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = VolcanicashforecastSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "changelog"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=2)
    assert [ref.source_native_id for ref in nxt] == ["reftimes"]
