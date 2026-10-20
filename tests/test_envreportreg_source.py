from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.envreportreg import (
    EnvreportregSource,
    cells_from_envreportreg,
    envreportreg_table_id,
    is_envreportreg_url,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://api.fiskeridir.no/envreportreg-public/v3/api-docs"
V2_SEARCH_URL = "https://api.fiskeridir.no/envreportreg-public/api/v2/report/search"
V1_SEARCH_URL = "https://api.fiskeridir.no/envreportreg-public/api/v1/report/search"
VESSEL_URL = "https://api.fiskeridir.no/vessel-api/api/v1/vessels"
BUYER_URL = "https://api.fiskeridir.no/buyer-api/v1/locations"
AQUA_URL = "https://api.fiskeridir.no/pub-aqua/api/v1/areas"
OMREGNING_URL = "https://api.fiskeridir.no/conversion-factor-api/api/v1/conversionfactors/search"
LICENSE_URL = "https://www.fiskeridir.no/Tall-og-analyse/Lisens-for-bruk-av-Fiskeridirektoratets-data"
DATASET_ID = "envreportreg:api/v2/report/search"

OPENAPI = {
    "openapi": "3.0.1",
    "info": {
        "title": "Offentlig API for miljøundersøkelser",
        "description": "Dette API'et lar deg hente informasjon om miljøundersøkelser",
        "license": {
            "name": "Lisens for bruk av Fiskeridirektoratets data",
            "url": LICENSE_URL,
        },
        "version": "1.0.0",
    },
    "servers": [
        {
            "url": "https://api.fiskeridir.no/envreportreg-public",
            "description": "Generated server url",
        }
    ],
    "paths": {
        "/api/v2/report/search": {
            "get": {
                "summary": "Søk etter miljørapporter",
                "operationId": "getReports",
                "parameters": [
                    {"name": "organisationNumber", "in": "query", "required": False},
                ],
            }
        },
        "/api/v2/report/{report_id}": {
            "get": {
                "summary": "Hent en miljørapport med alle tilgjengelige data",
                "parameters": [
                    {"name": "report_id", "in": "path", "required": True},
                ],
            }
        },
        "/api/v1/report/search": {
            "get": {
                "summary": "Søk etter miljørapporter",
                "operationId": "getReports_1",
                "parameters": [
                    {"name": "siteNumber", "in": "query", "required": False},
                ],
            }
        },
    },
}
SEARCH_BODY = {
    "content": [
        {
            "reportId": 22816,
            "siteName": "TORANGSKJERET",
            "organisationNumber": "956876354",
            "envExaminationType": "b",
            "siteCondition": "1",
            "nested": {"skip": True},
        },
        {
            "reportId": 22812,
            "siteName": "BERGADALEN",
            "organisationNumber": "960900626",
            "envExaminationType": "c",
        },
    ],
    "totalElements": 2,
    "page": 0,
    "size": 100,
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
        if url == V2_SEARCH_URL:
            return JsonResponse(status=200, url=url, body=SEARCH_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"envreportreg fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_keep_versioned_search() -> None:
    source = EnvreportregSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "api/v2/report/search",
        "api/v1/report/search",
    ]
    assert [ref.source_native_uri for ref in refs] == [V2_SEARCH_URL, V1_SEARCH_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_uses_printed_server() -> None:
    url = printed_endpoint_url(OPENAPI, "/api/v2/report/search", OPENAPI_URL)
    assert url == V2_SEARCH_URL
    assert "api-docs" not in url
    origin_only = printed_endpoint_url({}, "/api/v2/report/search", OPENAPI_URL)
    assert origin_only == "https://api.fiskeridir.no/api/v2/report/search"


def test_printed_operation_id_keeps_versioned_path() -> None:
    assert printed_operation_id("/api/v2/report/search") == "api/v2/report/search"
    assert printed_operation_id("/api/v1/report/search") == "api/v1/report/search"


def test_printed_license_url_copies_printed_url() -> None:
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({"title": "Offentlig API for miljøundersøkelser"}) is None
    assert printed_license_url({"license": {"name": "NLOD"}}) is None


def test_envreportreg_is_a_registered_source() -> None:
    assert "envreportreg" in SOURCE_IDS
    assert "omregning" in SOURCE_IDS
    assert "fiskeridir" in SOURCE_IDS
    assert "aqua" in SOURCE_IDS
    source = build_source("envreportreg")
    assert isinstance(source, EnvreportregSource)
    assert source.source_id == "envreportreg"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = EnvreportregSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "envreportreg"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == V2_SEARCH_URL
    assert row["title"] == "Søk etter miljørapporter"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("omregning:")
    assert not str(row["id"]).startswith("fiskeridir:")
    assert not str(row["id"]).startswith("aqua:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["envreportreg_openapi_path"] == "/api/v2/report/search"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_reports(tmp_path: Path) -> None:
    source = EnvreportregSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == V2_SEARCH_URL
    assert result.table_id == "api/v2/report/search"
    assert result.http_status == 200
    assert result.counts.listed == 2
    # A survey report is addressed by its report id and names the site it
    # surveyed; neither is a measurement of anything.
    assert registry.observation_count() == 0
    rows = registry.list_records(DATASET_ID, kind="entity")
    by_value = {row["subject_label"]: row for row in rows}
    assert set(by_value) == {"TORANGSKJERET", "BERGADALEN"}
    assert by_value["TORANGSKJERET"]["subject_code"] == "22816"
    assert all(row["measure"] is None and row["value_json"] is None for row in rows)
    attributes = json.loads(by_value["TORANGSKJERET"]["attributes_json"])
    assert attributes["organisationNumber"] == "956876354"
    assert "reportId" not in attributes
    assert "nested" not in attributes
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["request_url"] == V2_SEARCH_URL for row in rows)
    registry.close()


def test_cells_copy_printed_sitename_or_report_id() -> None:
    cells = cells_from_envreportreg(SEARCH_BODY)
    assert cells[0][0] == "siteName"
    assert cells[0][1] == "TORANGSKJERET"
    assert cells[0][2]["reportId"] == "22816"
    assert "nested" not in cells[0][2]
    assert cells_from_envreportreg({"reportId": 1, "organisationNumber": "123"}) == [
        ("reportId", 1, {"organisationNumber": "123"})
    ]
    assert cells_from_envreportreg("TORANGSKJERET") == [
        ("value", "TORANGSKJERET", {"value": "TORANGSKJERET"})
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_envreportreg(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_envreportreg({"content": []})


def test_is_envreportreg_url_accepts_only_envreportreg_path() -> None:
    assert is_envreportreg_url(V2_SEARCH_URL)
    assert is_envreportreg_url(OPENAPI_URL)
    assert envreportreg_table_id(V2_SEARCH_URL) == "api/v2/report/search"
    assert printed_endpoint_url(OPENAPI, "/api/v2/report/search", OPENAPI_URL) == (
        V2_SEARCH_URL
    )
    assert not is_envreportreg_url(VESSEL_URL)
    assert not is_envreportreg_url(BUYER_URL)
    assert not is_envreportreg_url(AQUA_URL)
    assert not is_envreportreg_url(OMREGNING_URL)
    assert not is_envreportreg_url("https://kart.hi.no/data/ogc/coverages/v1/collections")
    assert not is_envreportreg_url("https://data.norge.no/datasets/x")
    assert not is_envreportreg_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = EnvreportregSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "api/v2/report/search"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["api/v1/report/search"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
