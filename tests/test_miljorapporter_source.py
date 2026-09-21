from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.miljorapporter import (
    MiljorapporterSource,
    cells_from_miljorapporter,
    is_miljorapporter_url,
    miljorapporter_table_id,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://api.fiskeridir.no/miljorapporter-api/v3/api-docs"
REPORTS_URL = "https://api.fiskeridir.no/miljorapporter-api/api/v1/env-reports"
OVERVIEWS_URL = (
    "https://api.fiskeridir.no/miljorapporter-api/api/v1/env-report-overviews"
)
PING_URL = "https://api.fiskeridir.no/miljorapporter-api/api/ping"
ENVREPORTREG_URL = "https://api.fiskeridir.no/envreportreg-public/api/v2/report/search"
VESSEL_URL = "https://api.fiskeridir.no/vessel-api/api/v1/vessels"
BUYER_URL = "https://api.fiskeridir.no/buyer-api/v1/locations"
OMREGNING_URL = "https://api.fiskeridir.no/conversion-factor-api/api/v1/conversionfactors/search"
LICENSE_URL = "https://www.fiskeridir.no/Tall-og-analyse/Lisens-for-bruk-av-Fiskeridirektoratets-data"
DATASET_ID = "miljorapporter:api/v1/env-reports"

OPENAPI = {
    "openapi": "3.0.1",
    "info": {
        "title": "miljorapporter-api",
        "description": "This is a replacement of aqua-env-report, ported to spring-boot",
        "license": {
            "name": "Lisens for bruk av Fiskeridirektoratets data",
            "url": LICENSE_URL,
        },
        "version": "1.0.0",
    },
    "servers": [
        {
            "url": "https://api.fiskeridir.no/miljorapporter-api",
            "description": "Generated server url",
        }
    ],
    "security": [{"Keycloak": []}],
    "paths": {
        "/api/v2/env-reports/{reportId}/attachments/{attachmentId}": {
            "get": {
                "tags": ["Environment Reports with auth"],
                "operationId": "getAttachment",
                "parameters": [
                    {"name": "reportId", "in": "path", "required": True},
                    {"name": "attachmentId", "in": "path", "required": True},
                ],
            }
        },
        "/api/v1/env-reports": {
            "get": {
                "tags": ["Environment Reports"],
                "operationId": "getEnvReports",
                "parameters": [
                    {"name": "siteNo", "in": "query", "required": False},
                    {"name": "range", "in": "query", "required": False},
                ],
            }
        },
        "/api/v1/env-reports/{reportId}": {
            "get": {
                "operationId": "getEnvReport",
                "parameters": [
                    {"name": "reportId", "in": "path", "required": True},
                ],
            }
        },
        "/api/v1/env-report-overviews": {
            "get": {
                "tags": ["Environment Reports"],
                "operationId": "getEnvReportOverviews",
                "parameters": [
                    {"name": "siteNo", "in": "query", "required": False},
                ],
            }
        },
        "/api/ping": {
            "get": {
                "tags": ["PingResource"],
                "operationId": "ping",
            }
        },
    },
}
REPORTS_BODY = [
    {
        "reportId": "AM63689626",
        "siteName": "Leivsethammran",
        "licenseHolderName": "WENBERG FISKEOPPDRETT AS",
        "licenseHolderOrgNo": "937504446",
        "envExaminationType": "b",
        "nested": {"skip": True},
    },
    {
        "reportId": "AM63689627",
        "siteName": "BERGADALEN",
        "licenseHolderName": "EXAMPLE AS",
        "envExaminationType": "c",
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
        if url == REPORTS_URL:
            return JsonResponse(status=200, url=url, body=REPORTS_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"miljorapporter fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_keep_collection_gets() -> None:
    source = MiljorapporterSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "api/v1/env-reports",
        "api/v1/env-report-overviews",
        "api/ping",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        REPORTS_URL,
        OVERVIEWS_URL,
        PING_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_uses_printed_server() -> None:
    url = printed_endpoint_url(OPENAPI, "/api/v1/env-reports", OPENAPI_URL)
    assert url == REPORTS_URL
    assert "api-docs" not in url
    origin_only = printed_endpoint_url({}, "/api/v1/env-reports", OPENAPI_URL)
    assert origin_only == "https://api.fiskeridir.no/api/v1/env-reports"


def test_printed_operation_id_keeps_versioned_path() -> None:
    assert printed_operation_id("/api/v1/env-reports") == "api/v1/env-reports"
    assert printed_operation_id("/api/v1/env-report-overviews") == (
        "api/v1/env-report-overviews"
    )
    assert printed_operation_id("/api/ping") == "api/ping"


def test_printed_license_url_copies_printed_url() -> None:
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({"title": "miljorapporter-api"}) is None
    assert printed_license_url({"license": {"name": "NLOD"}}) is None


def test_miljorapporter_is_a_registered_source() -> None:
    assert "miljorapporter" in SOURCE_IDS
    assert "envreportreg" in SOURCE_IDS
    assert "omregning" in SOURCE_IDS
    assert "fiskeridir" in SOURCE_IDS
    assert "histyles" in SOURCE_IDS
    assert "hitiles" in SOURCE_IDS
    source = build_source("miljorapporter")
    assert isinstance(source, MiljorapporterSource)
    assert source.source_id == "miljorapporter"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = MiljorapporterSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    assert counts.ignored == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "miljorapporter"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == REPORTS_URL
    assert row["title"] == "getEnvReports"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("envreportreg:")
    assert not str(row["id"]).startswith("omregning:")
    assert not str(row["id"]).startswith("fiskeridir:")
    assert not str(row["id"]).startswith("histyles:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["miljorapporter_openapi_path"] == "/api/v1/env-reports"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_reports(tmp_path: Path) -> None:
    source = MiljorapporterSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == REPORTS_URL
    assert result.table_id == "api/v1/env-reports"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"Leivsethammran", "BERGADALEN"}
    assert by_value["Leivsethammran"]["measure"] == "siteName"
    dims = json.loads(by_value["Leivsethammran"]["dimensions_json"])
    assert dims["reportId"] == "AM63689626"
    assert dims["licenseHolderOrgNo"] == "937504446"
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == REPORTS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_sitename_or_report_id() -> None:
    cells = cells_from_miljorapporter(REPORTS_BODY)
    assert cells[0][0] == "siteName"
    assert cells[0][1] == "Leivsethammran"
    assert cells[0][2]["reportId"] == "AM63689626"
    assert "nested" not in cells[0][2]
    assert cells_from_miljorapporter({"reportId": "AM1", "licenseHolderName": "AS"}) == [
        ("reportId", "AM1", {"licenseHolderName": "AS"})
    ]
    assert cells_from_miljorapporter("Leivsethammran") == [
        ("value", "Leivsethammran", {"value": "Leivsethammran"})
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_miljorapporter(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_miljorapporter([])


def test_is_miljorapporter_url_accepts_only_miljorapporter_path() -> None:
    assert is_miljorapporter_url(REPORTS_URL)
    assert is_miljorapporter_url(OPENAPI_URL)
    assert miljorapporter_table_id(REPORTS_URL) == "api/v1/env-reports"
    assert printed_endpoint_url(OPENAPI, "/api/v1/env-reports", OPENAPI_URL) == REPORTS_URL
    assert not is_miljorapporter_url(ENVREPORTREG_URL)
    assert not is_miljorapporter_url(VESSEL_URL)
    assert not is_miljorapporter_url(BUYER_URL)
    assert not is_miljorapporter_url(OMREGNING_URL)
    assert not is_miljorapporter_url("https://kart.hi.no/data/ogc/tiles/v1")
    assert not is_miljorapporter_url("https://data.norge.no/datasets/x")
    assert not is_miljorapporter_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = MiljorapporterSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "api/v1/env-reports"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["api/v1/env-report-overviews"]
    assert source.list_dataset_refs(limit=1, offset=3) == []
