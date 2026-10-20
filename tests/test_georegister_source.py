from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.georegister import (
    GeoregisterSource,
    cells_from_georegister,
    georegister_table_id,
    is_georegister_url,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://register.geonorge.no/swagger/docs/v1"
ALERTS_URL = "https://register.geonorge.no/api/alerts"
KOMMUNER_URL = "https://register.geonorge.no/api/v2/organisasjoner/kommuner"
REGISTER_URL = "https://register.geonorge.no/api/register"
SEARCH_URL = "https://register.geonorge.no/api/Search"
SITEMAP_URL = "https://register.geonorge.no/api/sitemap"
DATASET_ID = "georegister:kommuner"

OPENAPI = {
    "swagger": "2.0",
    "info": {"title": "Kartverket.Register", "version": "v1"},
    "host": "register.geonorge.no",
    "schemes": ["http", "https"],
    "paths": {
        "/api/{registerName}": {
            "get": {
                "summary": "Gets register by name",
                "parameters": [{"name": "registerName", "required": True}],
            }
        },
        "/api/alerts": {"get": {"summary": "Get all alerts"}},
        "/api/register": {
            "get": {"summary": "List top level registers. Use id in response to navigate."}
        },
        "/api/Search": {"get": {"summary": "Register search"}},
        "/api/sitemap": {"get": {"summary": "sitemap for search engine"}},
        "/api/OrganizationsApi": {
            "get": {
                "summary": "Get municipality by kommunenummer",
                "parameters": [{"name": "kommunenummer", "required": True}],
            }
        },
        "/api/v2/organisasjoner/kommuner": {"get": {"summary": "Get list of municipalities"}},
    },
}

KOMMUNER_BODY = [
    {
        "Name": "Utsira kommune",
        "OrganizationNumber": "964979901",
        "OrganizationType": "municipality",
        "MunicipalityCode": "1151",
        "nested": {"skip": True},
    },
    {
        "Name": "Askvoll kommune",
        "OrganizationNumber": "838900802",
        "OrganizationType": "municipality",
        "MunicipalityCode": "4645",
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
        if url == KOMMUNER_URL:
            return JsonResponse(status=200, url=url, body=KOMMUNER_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"georegister fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_required_paths() -> None:
    source = GeoregisterSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "alerts",
        "register",
        "Search",
        "sitemap",
        "kommuner",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        ALERTS_URL,
        REGISTER_URL,
        SEARCH_URL,
        SITEMAP_URL,
        KOMMUNER_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert "" not in [ref.source_native_id for ref in refs]


def test_printed_operation_id_is_last_segment() -> None:
    assert printed_operation_id("/api/v2/organisasjoner/kommuner") == "kommuner"
    assert printed_operation_id("/api/alerts") == "alerts"


def test_printed_endpoint_url_uses_printed_host() -> None:
    url = printed_endpoint_url(OPENAPI, "/api/v2/organisasjoner/kommuner", OPENAPI_URL)
    assert url == KOMMUNER_URL
    without_host = printed_endpoint_url({}, "/api/alerts", OPENAPI_URL)
    assert without_host == "https://register.geonorge.no/api/alerts"


def test_printed_license_url_stays_null_when_absent() -> None:
    assert printed_license_url(OPENAPI["info"]) is None
    assert printed_license_url({"title": "Kartverket.Register"}) is None


def test_georegister_is_a_registered_source() -> None:
    assert "georegister" in SOURCE_IDS
    assert "locationforecast" in SOURCE_IDS
    assert "norskelos" in SOURCE_IDS
    assert "routeforecast" in SOURCE_IDS
    assert "kommuneinfo" in SOURCE_IDS
    assert "geonorge" in SOURCE_IDS
    source = build_source("georegister")
    assert isinstance(source, GeoregisterSource)
    assert source.source_id == "georegister"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = GeoregisterSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 5
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "georegister"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == KOMMUNER_URL
    assert row["title"] == "Get list of municipalities"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("geonorge:")
    assert not str(row["id"]).startswith("norskelos:")
    assert not str(row["id"]).startswith("kommuneinfo:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["georegister_openapi_path"] == "/api/v2/organisasjoner/kommuner"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_kommuner(tmp_path: Path) -> None:
    source = GeoregisterSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == KOMMUNER_URL
    assert result.table_id == "kommuner"
    assert result.http_status == 200
    assert result.counts.listed == 2
    # A register of organisations, addressed by organisation number.
    assert registry.observation_count() == 0
    rows = registry.list_records(DATASET_ID, kind="entity")
    assert {row["subject_label"] for row in rows} == {"Utsira kommune", "Askvoll kommune"}
    assert all(row["measure"] is None and row["value_json"] is None for row in rows)
    by_name = {
        row["subject_label"]: (row["subject_code"], json.loads(row["attributes_json"]))
        for row in rows
    }
    assert by_name["Utsira kommune"] == (
        "964979901",
        {"OrganizationType": "municipality", "MunicipalityCode": "1151"},
    )
    assert by_name["Askvoll kommune"] == (
        "838900802",
        {"OrganizationType": "municipality", "MunicipalityCode": "4645"},
    )
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["request_url"] == KOMMUNER_URL for row in rows)
    registry.close()


def test_cells_copy_printed_names() -> None:
    cells = cells_from_georegister(KOMMUNER_BODY)
    assert cells == [
        (
            "Name",
            "Utsira kommune",
            {
                "OrganizationNumber": "964979901",
                "OrganizationType": "municipality",
                "MunicipalityCode": "1151",
            },
        ),
        (
            "Name",
            "Askvoll kommune",
            {
                "OrganizationNumber": "838900802",
                "OrganizationType": "municipality",
                "MunicipalityCode": "4645",
            },
        ),
    ]
    search_cells = cells_from_georegister({"Results": KOMMUNER_BODY})
    assert [value for _measure, value, _dims in search_cells] == [
        "Utsira kommune",
        "Askvoll kommune",
    ]
    with pytest.raises(ValueError, match="JSON array"):
        cells_from_georegister({"reftimes": ["2026-06-09T11:00:00Z"]})
    with pytest.raises(ValueError, match="JSON array"):
        cells_from_georegister("not-json")


def test_is_georegister_url_accepts_only_register_host_path() -> None:
    assert is_georegister_url(KOMMUNER_URL)
    assert is_georegister_url(ALERTS_URL)
    assert is_georegister_url(OPENAPI_URL) is False
    assert georegister_table_id(KOMMUNER_URL) == "kommuner"
    assert georegister_table_id(ALERTS_URL) == "alerts"
    assert not is_georegister_url(
        "https://dnl.kartverket.no/api/ogc/v1/collections/dennorskelos/place/items?f=json"
    )
    assert not is_georegister_url("https://api.kartverket.no/kommuneinfo/v1/fylker")
    assert not is_georegister_url("https://ws.geonorge.no/hoydedata/v1/datakilder")
    assert not is_georegister_url("https://kartkatalog.geonorge.no/api/search")
    assert not is_georegister_url("https://api.met.no/weatherapi/routeforecast/2.0/locations")
    assert not is_georegister_url("https://data.norge.no/datasets/x")
    assert not is_georegister_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = GeoregisterSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["alerts"]
    nxt = source.list_dataset_refs(limit=1, offset=4)
    assert [ref.source_native_id for ref in nxt] == ["kommuner"]
