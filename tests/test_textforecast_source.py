from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.textforecast import (
    TextforecastSource,
    cells_from_textforecast,
    is_textforecast_url,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
    printed_title,
    textforecast_table_id,
)

OPENAPI_URL = "https://api.met.no/weatherapi/textforecast/3.0/swagger"
LANDOVERVIEW_URL = "https://api.met.no/weatherapi/textforecast/3.0/landoverview"
AVAILABLE_URL = "https://api.met.no/weatherapi/textforecast/3.0/available"
FEATURES_URL = "https://api.met.no/weatherapi/textforecast/3.0/features"
LICENSE_URL = "http://creativecommons.org/licenses/by/4.0"
DATASET_ID = "textforecast:landoverview"
PRODUCT_DESCRIPTION = "Textual weather forecast for Norwegian land and sea areas"

OPENAPI = {
    "swagger": "2.0",
    "info": {
        "title": "Textforecast",
        "description": PRODUCT_DESCRIPTION,
        "license": {"name": "CC BY 4.0", "url": LICENSE_URL},
        "version": "3.0",
    },
    "basePath": "/weatherapi/textforecast/3.0",
    "paths": {
        "/": {
            "get": {
                "description": PRODUCT_DESCRIPTION,
                "parameters": [{"name": "forecast", "required": True, "in": "query"}],
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
        "/landoverview": {
            "get": {
                "description": PRODUCT_DESCRIPTION,
            }
        },
        "/landoverview.{format}": {
            "get": {
                "description": PRODUCT_DESCRIPTION,
                "parameters": [{"name": "format", "required": True, "in": "path"}],
            }
        },
        "/values": {
            "get": {
                "description": "List allowed options for parameters",
            }
        },
    },
}
LANDOVERVIEW_BODY = {
    "type": "FeatureCollection",
    "lang": "no",
    "lastChange": "2026-08-27T16:03:10Z",
    "features": [
        {
            "type": "Feature",
            "when": {"interval": ["2026-08-27T18:00:00Z", "2026-08-28T00:00:00Z"]},
            "properties": {
                "area": "Østlandet",
                "text": "Sørøstlig bris.",
                "title": "Varsel for Østlandet",
            },
            "geometry": {"type": "Polygon", "coordinates": [[[10.0, 59.0], [11.0, 59.0]]]},
        },
        {
            "type": "Feature",
            "properties": {
                "area": "Agder",
                "title": "Varsel for Agder",
            },
        },
    ],
}
FEATURES_BODY = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "id": "landoverview",
            "properties": {},
            "assets": {
                "data": {
                    "title": "Textforecast forecast=landoverview",
                }
            },
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
        if url == LANDOVERVIEW_URL:
            return JsonResponse(status=200, url=url, body=LANDOVERVIEW_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"textforecast fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_required_param_paths() -> None:
    source = TextforecastSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "available",
        "changelog",
        "features",
        "landoverview",
        "values",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        AVAILABLE_URL,
        "https://api.met.no/weatherapi/textforecast/3.0/changelog",
        FEATURES_URL,
        LANDOVERVIEW_URL,
        "https://api.met.no/weatherapi/textforecast/3.0/values",
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]
    assert "forecast" not in [ref.source_native_id for ref in refs]


def test_endpoint_url_joins_printed_basepath_and_origin() -> None:
    url = printed_endpoint_url(OPENAPI, "/landoverview", OPENAPI_URL)
    assert url == LANDOVERVIEW_URL
    assert "/swagger" not in url
    with_host = printed_endpoint_url(
        {
            "host": "api.met.no",
            "basePath": "/weatherapi/textforecast/3.0",
            "schemes": ["https"],
        },
        "/landoverview",
        OPENAPI_URL,
    )
    assert with_host == LANDOVERVIEW_URL


def test_printed_operation_id_is_last_path_segment() -> None:
    assert printed_operation_id("/landoverview") == "landoverview"
    assert printed_operation_id("/available") == "available"
    assert printed_operation_id("/severe-weather-outlook") == "severe-weather-outlook"


def test_printed_license_url_copies_swagger_license() -> None:
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({"title": "Textforecast"}) is None


def test_printed_title_uses_path_id_when_description_is_product_blurb() -> None:
    assert (
        printed_title(
            {"description": PRODUCT_DESCRIPTION},
            OPENAPI["info"],
            "landoverview",
        )
        == "landoverview"
    )
    assert (
        printed_title(
            {"description": "List available resources as OGC API FeatureCollection"},
            OPENAPI["info"],
            "features",
        )
        == "List available resources as OGC API FeatureCollection"
    )


def test_textforecast_is_a_registered_source() -> None:
    assert "textforecast" in SOURCE_IDS
    source = build_source("textforecast")
    assert isinstance(source, TextforecastSource)
    assert source.source_id == "textforecast"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = TextforecastSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 5
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "textforecast"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == LANDOVERVIEW_URL
    assert row["title"] == "landoverview"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("met:")
    assert not str(row["id"]).startswith("nowcast:")
    assert not str(row["id"]).startswith("radar:")
    assert not str(row["id"]).startswith("sunrise:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["textforecast_openapi_path"] == "/landoverview"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_landoverview(tmp_path: Path) -> None:
    source = TextforecastSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == LANDOVERVIEW_URL
    assert result.table_id == "landoverview"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"Østlandet", "Agder"}
    assert by_value["Østlandet"]["measure"] == "area"
    assert by_value["Agder"]["measure"] == "area"
    dims = json.loads(by_value["Østlandet"]["dimensions_json"])
    assert dims["title"] == "Varsel for Østlandet"
    assert dims["text"] == "Sørøstlig bris."
    assert "when" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == LANDOVERVIEW_URL for row in rows)
    registry.close()


def test_cells_copy_printed_area_or_feature_id() -> None:
    cells = cells_from_textforecast(LANDOVERVIEW_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "area"
    assert value == "Østlandet"
    assert dims["title"] == "Varsel for Østlandet"
    assert "when" not in dims
    fallback = cells_from_textforecast(FEATURES_BODY)
    assert fallback == [("id", "landoverview", {})]
    with pytest.raises(ValueError, match="FeatureCollection"):
        cells_from_textforecast({"features": []})
    with pytest.raises(ValueError, match="features array"):
        cells_from_textforecast({"type": "FeatureCollection"})


def test_is_textforecast_url_accepts_only_textforecast_host_path() -> None:
    assert is_textforecast_url(LANDOVERVIEW_URL)
    assert is_textforecast_url(OPENAPI_URL)
    assert textforecast_table_id(LANDOVERVIEW_URL) == "landoverview"
    assert printed_endpoint_url(OPENAPI, "/landoverview", OPENAPI_URL) == LANDOVERVIEW_URL
    assert not is_textforecast_url("https://api.met.no/weatherapi/nowcast/2.0/locations")
    assert not is_textforecast_url("https://api.met.no/weatherapi/oceanforecast/2.0/locations")
    assert not is_textforecast_url("https://api.met.no/weatherapi/airqualityforecast/0.1/stations")
    assert not is_textforecast_url("https://api.met.no/weatherapi/tidalwater/1.1/locations")
    assert not is_textforecast_url("https://api.met.no/weatherapi/sunrise/3.0/locations")
    assert not is_textforecast_url("https://api.met.no/weatherapi/metalerts/2.0/locations")
    assert not is_textforecast_url("https://api.met.no/weatherapi/radar/2.0/locations")
    assert not is_textforecast_url("https://api.met.no/weatherapi/spotwind/1.1/locations")
    assert not is_textforecast_url("https://ws.geonorge.no/hoydedata/v1/datakilder")
    assert not is_textforecast_url("https://data.norge.no/datasets/x")
    assert not is_textforecast_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = TextforecastSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "available"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["changelog"]
