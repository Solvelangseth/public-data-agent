from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.airquality import (
    AirqualitySource,
    airquality_table_id,
    cells_from_airquality,
    is_airquality_url,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
    printed_title,
)

OPENAPI_URL = "https://api.met.no/weatherapi/airqualityforecast/0.1/swagger"
STATIONS_URL = "https://api.met.no/weatherapi/airqualityforecast/0.1/stations"
AREACLASSES_URL = "https://api.met.no/weatherapi/airqualityforecast/0.1/areaclasses"
LICENSE_URL = "http://creativecommons.org/licenses/by/4.0"
DATASET_ID = "airquality:stations"

OPENAPI = {
    "swagger": "2.0",
    "info": {
        "title": "Airqualityforecast",
        "description": "Something goes here...",
        "license": {"name": "CC BY 4.0", "url": LICENSE_URL},
        "version": "0.1",
    },
    "basePath": "/weatherapi/airqualityforecast/0.1",
    "paths": {
        "/": {
            "get": {
                "description": "Something goes here...",
            }
        },
        "/areaclasses": {
            "get": {
                "description": "Something goes here...",
            }
        },
        "/stations.{format}": {
            "get": {
                "description": "templated",
            }
        },
        "/stations": {
            "get": {
                "description": "Something goes here...",
            }
        },
        "/changelog": {
            "get": {
                "description": "RSS feed of changes to this product",
            }
        },
    },
}
STATIONS_BODY = [
    {
        "name": "Alnabru",
        "eoi": "NO0057A",
        "height": 3.0,
        "longitude": "10.84655",
        "latitude": "59.92767",
        "grunnkrets": {"name": "Alfaset", "areacode": "03013701"},
        "delomrade": {"name": "Alfaset", "areacode": "03013700"},
        "kommune": {"name": "Oslo", "areacode": "0301"},
    },
    {
        "name": "Sofienbergparken",
        "eoi": "NO0074A",
        "height": 10.0,
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
        if url == STATIONS_URL:
            return JsonResponse(status=200, url=url, body=STATIONS_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"airquality fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_root_paths() -> None:
    source = AirqualitySource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "areaclasses",
        "stations",
        "changelog",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        AREACLASSES_URL,
        STATIONS_URL,
        "https://api.met.no/weatherapi/airqualityforecast/0.1/changelog",
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_joins_printed_basepath_and_origin() -> None:
    url = printed_endpoint_url(OPENAPI, "/stations", OPENAPI_URL)
    assert url == STATIONS_URL
    assert "/swagger" not in url
    with_host = printed_endpoint_url(
        {
            "host": "api.met.no",
            "basePath": "/weatherapi/airqualityforecast/0.1",
            "schemes": ["https"],
        },
        "/stations",
        OPENAPI_URL,
    )
    assert with_host == STATIONS_URL


def test_printed_operation_id_is_last_path_segment() -> None:
    assert printed_operation_id("/stations") == "stations"
    assert printed_operation_id("/areaclasses") == "areaclasses"


def test_printed_title_uses_path_when_description_is_placeholder() -> None:
    assert printed_title("/stations", {"description": "Something goes here..."}) == "stations"
    assert (
        printed_title("/changelog", {"description": "RSS feed of changes to this product"})
        == "RSS feed of changes to this product"
    )


def test_printed_license_url_copies_swagger_license() -> None:
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({"title": "Airqualityforecast"}) is None


def test_airquality_is_a_registered_source() -> None:
    assert "airquality" in SOURCE_IDS
    source = build_source("airquality")
    assert isinstance(source, AirqualitySource)
    assert source.source_id == "airquality"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = AirqualitySource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "airquality"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == STATIONS_URL
    assert row["title"] == "stations"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("met:")
    assert not str(row["id"]).startswith("nowcast:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["airquality_openapi_path"] == "/stations"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    assert payload["description"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_stations(tmp_path: Path) -> None:
    source = AirqualitySource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == STATIONS_URL
    assert result.table_id == "stations"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"Alnabru", "Sofienbergparken"}
    assert by_value["Alnabru"]["measure"] == "name"
    dims = json.loads(by_value["Alnabru"]["dimensions_json"])
    assert dims["eoi"] == "NO0057A"
    assert "grunnkrets" not in dims
    assert "kommune" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == STATIONS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_station_name() -> None:
    cells = cells_from_airquality(STATIONS_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "Alnabru"
    assert dims["eoi"] == "NO0057A"
    assert "grunnkrets" not in dims
    fallback = cells_from_airquality([{"eoi": "NO0057A", "height": 3.0}])
    assert fallback == [("eoi", "NO0057A", {"height": "3.0"})]
    with pytest.raises(ValueError, match="JSON array"):
        cells_from_airquality({"stations": []})
    with pytest.raises(ValueError, match="JSON array"):
        cells_from_airquality({"name": "x"})


def test_is_airquality_url_accepts_only_airquality_host_path() -> None:
    assert is_airquality_url(STATIONS_URL)
    assert is_airquality_url(OPENAPI_URL)
    assert airquality_table_id(STATIONS_URL) == "stations"
    assert printed_endpoint_url(OPENAPI, "/stations", OPENAPI_URL) == STATIONS_URL
    assert not is_airquality_url("https://api.met.no/weatherapi/nowcast/2.0/locations")
    assert not is_airquality_url("https://api.met.no/weatherapi/metalerts/2.0/locations")
    assert not is_airquality_url("https://api.met.no/weatherapi/locationforecast/2.0/complete")
    assert not is_airquality_url("https://ws.geonorge.no/hoydedata/v1/datakilder")
    assert not is_airquality_url("https://data.norge.no/datasets/x")
    assert not is_airquality_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = AirqualitySource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "areaclasses"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["stations"]
