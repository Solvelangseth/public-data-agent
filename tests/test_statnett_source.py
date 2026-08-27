from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.statnett import (
    StatnettDriftsdataSource,
    cells_from_statnett,
    is_statnett_url,
    printed_endpoint_url,
    printed_operation_id,
    statnett_table_id,
)

OPENAPI_URL = "https://driftsdata.statnett.no/restapi/swagger/docs/v1"
SITUATIONS_URL = (
    "https://driftsdata.statnett.no/RestApi/ElspotPowerSituation/GetPowerSituations"
)
LAST_CHANGES_URL = (
    "https://driftsdata.statnett.no/RestApi/ElspotPowerSituation/LastChanges"
)
SEPARATOR_LAST_CHANGES_URL = (
    "https://driftsdata.statnett.no/RestApi/ElspotSeparatorLine/LastChanges"
)
DATASET_ID = "statnett:ElspotPowerSituation_GetPowerSituations"

OPENAPI = {
    "swagger": "2.0",
    "info": {"version": "v1", "title": "Statnett.Driftsdata.RestApi"},
    "host": "driftsdata.statnett.no",
    "basePath": "/RestApi",
    "schemes": ["http", "https"],
    "paths": {
        "/ElspotPowerSituation/LastChanges": {
            "get": {
                "operationId": "ElspotPowerSituation_LastChanges",
                "summary": "Returns timestamps of the last changes in the Elspot power situation.",
            }
        },
        "/ElspotPowerSituation/GetPowerSituations": {
            "get": {
                "operationId": "ElspotPowerSituation_GetPowerSituations",
                "summary": "Returns Elspot power situation information for a given time.",
            }
        },
        "/ElspotSeparatorLine/LastChanges": {
            "get": {
                "operationId": "ElspotSeparatorLine_LastChanges",
                "summary": "Returns the timestamps of the last changes in Elspot separator line information.",
            }
        },
        "/ElspotSeparatorLine/LineData/{id}": {
            "get": {
                "operationId": "ElspotSeparatorLine_LineDataById",
                "summary": "templated",
            }
        },
    },
}
SITUATIONS_BODY = [
    {
        "elspotId": "NO3",
        "elspotCoordinates": "495,467,489,460",
        "powerSituation": "Normal",
        "translatedText": {"no": {"shortDescription": "Normalt"}},
    },
    {
        "elspotId": "NO4",
        "elspotCoordinates": "635,332",
        "powerSituation": "Tight",
        "translatedText": {"en": {"shortDescription": "Tight"}},
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
        if url == SITUATIONS_URL:
            return JsonResponse(status=200, url=url, body=SITUATIONS_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"statnett fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_paths_and_keep_distinct_lastchanges() -> None:
    source = StatnettDriftsdataSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "ElspotPowerSituation_LastChanges",
        "ElspotPowerSituation_GetPowerSituations",
        "ElspotSeparatorLine_LastChanges",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        LAST_CHANGES_URL,
        SITUATIONS_URL,
        SEPARATOR_LAST_CHANGES_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_joins_printed_host_basepath_and_path() -> None:
    url = printed_endpoint_url(
        OPENAPI, "/ElspotPowerSituation/GetPowerSituations", OPENAPI_URL
    )
    assert url == SITUATIONS_URL
    assert "/swagger" not in url
    no_host = printed_endpoint_url(
        {"basePath": "/RestApi", "schemes": ["https"]},
        "/ElspotPowerSituation/GetPowerSituations",
        OPENAPI_URL,
    )
    assert no_host == SITUATIONS_URL


def test_printed_operation_id_prefers_swagger_operationId() -> None:
    item = OPENAPI["paths"]["/ElspotPowerSituation/GetPowerSituations"]
    assert printed_operation_id("/ElspotPowerSituation/GetPowerSituations", item) == (
        "ElspotPowerSituation_GetPowerSituations"
    )
    assert printed_operation_id("/ElspotPowerSituation/GetPowerSituations") == (
        "GetPowerSituations"
    )


def test_statnett_is_a_registered_source() -> None:
    assert "statnett" in SOURCE_IDS
    source = build_source("statnett")
    assert isinstance(source, StatnettDriftsdataSource)
    assert source.source_id == "statnett"


def test_harvest_writes_printed_id_and_null_license_publisher(tmp_path: Path) -> None:
    source = StatnettDriftsdataSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "statnett"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == SITUATIONS_URL
    assert row["title"] == "Returns Elspot power situation information for a given time."
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    last_a = registry.get_dataset("statnett:ElspotPowerSituation_LastChanges")
    last_b = registry.get_dataset("statnett:ElspotSeparatorLine_LastChanges")
    assert last_a is not None and last_b is not None
    assert last_a["access_path"] != last_b["access_path"]
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["statnett_openapi_path"] == "/ElspotPowerSituation/GetPowerSituations"
    assert payload["license"] is None
    assert payload["publisher"] is None
    registry.close()


def test_fetch_gets_printed_power_situations(tmp_path: Path) -> None:
    source = StatnettDriftsdataSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == SITUATIONS_URL
    assert result.table_id == "GetPowerSituations"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["NO3", "NO4"] or values == ["NO4", "NO3"]
    assert all(row["measure"] == "elspotId" for row in rows)
    by_id = {json.loads(row["value_json"]): row for row in rows}
    dims = json.loads(by_id["NO3"]["dimensions_json"])
    assert dims["powerSituation"] == "Normal"
    assert dims["elspotCoordinates"] == "495,467,489,460"
    assert "translatedText" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == SITUATIONS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_elspot_id() -> None:
    cells = cells_from_statnett(SITUATIONS_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "elspotId"
    assert value == "NO3"
    assert dims["powerSituation"] == "Normal"
    assert "translatedText" not in dims
    fallback = cells_from_statnett([{"name": "NO1-NO3", "country": "NO"}])
    assert fallback == [("name", "NO1-NO3", {"country": "NO"})]
    with pytest.raises(ValueError, match="JSON array"):
        cells_from_statnett({"elspotId": "NO3"})


def test_is_statnett_url_accepts_only_driftsdata_host() -> None:
    assert is_statnett_url(SITUATIONS_URL)
    assert is_statnett_url(OPENAPI_URL)
    assert statnett_table_id(SITUATIONS_URL) == "GetPowerSituations"
    assert not is_statnett_url("https://data.norge.no/datasets/x")
    assert not is_statnett_url("https://www.statnett.no/RestApi/ElspotPowerSituation/GetPowerSituations")
    assert not is_statnett_url("https://biapi.nve.no/magasinstatistikk/swagger/v1/swagger.json")
    assert not is_statnett_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = StatnettDriftsdataSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "ElspotPowerSituation_LastChanges"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == [
        "ElspotPowerSituation_GetPowerSituations"
    ]
