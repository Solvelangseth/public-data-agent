from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.nibio import (
    NibioWeatherSource,
    cells_from_nibio,
    is_nibio_url,
    nibio_table_id,
    printed_endpoint_url,
    printed_license_url,
)

OPENAPI_URL = "https://irh.nibio.no/weather/openapi.json"
PARAMETER_URL = "https://irh.nibio.no/weather/parameter"
AMALGAMATION_TYPE_URL = "https://irh.nibio.no/weather/amalgamationType"
QC_URL = "https://irh.nibio.no/weather/qc"
DATASET_ID = "nibio:parameter"

OPENAPI = {
    "info": {
        "title": "IPM Resource Hub WeatherService",
        "description": "This service enables unifying heterogenous weather datasources.",
        "version": "1.0.0",
    },
    "paths": {
        "/weather/amalgamationType": {
            "get": {"summary": "List all the amalgamation types defined in the platform"}
        },
        "/weather/parameter": {
            "get": {"summary": "List all the weather parameters defined in the platform"}
        },
        "/weather/weatherdatasource/{id}": {
            "get": {"summary": "Return the requested weather datasource"}
        },
        "/weather/qc": {"get": {"summary": "List all QC codes"}},
    },
}
PARAMETER_BODY = [
    {
        "id": 1001,
        "name": "Instantaneous temperature at 2m",
        "description": None,
        "unit": "Celcius",
        "aggregationType": "AVERAGE",
        "dailyUnit": None,
        "dailyAggregationType": None,
    },
    {
        "id": 1002,
        "name": "Mean temperature at 2m",
        "description": "Hourly mean",
        "unit": "Celcius",
        "aggregationType": "AVERAGE",
        "spatial": {"skip": True},
    },
]


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
        if url == PARAMETER_URL:
            return JsonResponse(status=200, url=url, body=PARAMETER_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nibio fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_paths() -> None:
    source = NibioWeatherSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "amalgamationType",
        "parameter",
        "qc",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        AMALGAMATION_TYPE_URL,
        PARAMETER_URL,
        QC_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_uses_origin_when_servers_absent() -> None:
    url = printed_endpoint_url(OPENAPI, "/weather/parameter", OPENAPI_URL)
    assert url == PARAMETER_URL
    assert "/openapi.json" not in url
    with_server = printed_endpoint_url(
        {"servers": [{"url": "https://irh.nibio.no/"}]},
        "/weather/parameter",
        OPENAPI_URL,
    )
    assert with_server == PARAMETER_URL


def test_nibio_is_a_registered_source() -> None:
    assert "nibio" in SOURCE_IDS
    assert "nibiowms" in SOURCE_IDS
    source = build_source("nibio")
    assert isinstance(source, NibioWeatherSource)
    assert source.source_id == "nibio"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = NibioWeatherSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nibio"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == PARAMETER_URL
    assert row["title"] == "List all the weather parameters defined in the platform"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["nibio_openapi_path"] == "/weather/parameter"
    assert payload["license"] is None
    assert payload["publisher"] is None
    registry.close()


def test_fetch_gets_printed_parameter(tmp_path: Path) -> None:
    source = NibioWeatherSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == PARAMETER_URL
    assert result.table_id == "parameter"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    assert [json.loads(row["value_json"]) for row in rows] == [
        "Instantaneous temperature at 2m",
        "Mean temperature at 2m",
    ]
    assert all(row["measure"] == "name" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["id"] == "1001"
    assert dims["unit"] == "Celcius"
    assert dims["aggregationType"] == "AVERAGE"
    assert dims["description"] == ""
    assert "spatial" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == PARAMETER_URL for row in rows)
    registry.close()


def test_cells_copy_printed_name_and_skip_nested() -> None:
    cells = cells_from_nibio(PARAMETER_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "Instantaneous temperature at 2m"
    assert dims["id"] == "1001"
    assert dims["description"] == ""
    assert "spatial" not in dims
    strings = cells_from_nibio(["AVERAGE", "SUM"])
    assert strings == [("value", "AVERAGE", {}), ("value", "SUM", {})]
    fallback = cells_from_nibio([{"id": 0, "unit": "Celcius"}])
    assert fallback == [("id", 0, {"unit": "Celcius"})]
    with pytest.raises(ValueError, match="JSON array"):
        cells_from_nibio({"name": "Instantaneous temperature at 2m"})


def test_is_nibio_url_accepts_only_irh_weather_host() -> None:
    assert is_nibio_url(PARAMETER_URL)
    assert is_nibio_url(OPENAPI_URL)
    assert nibio_table_id(PARAMETER_URL) == "parameter"
    assert printed_license_url({}) is None
    assert printed_license_url({"license": {"url": "https://example.invalid/nlod"}}) == (
        "https://example.invalid/nlod"
    )
    assert not is_nibio_url("https://data.norge.no/datasets/x")
    assert not is_nibio_url("https://lmt.nibio.no/services/rest/weatherstations")
    assert not is_nibio_url("https://www.nibio.no/weather/parameter")
    assert not is_nibio_url("https://irh.nibio.no/other/parameter")
    assert not is_nibio_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = NibioWeatherSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "amalgamationType"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["parameter"]
