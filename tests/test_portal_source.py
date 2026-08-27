from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.portal import (
    PortalSource,
    cells_from_portal,
    is_portal_url,
    portal_table_id,
    printed_endpoint_url,
    printed_license_url,
)

OPENAPI_URL = "https://api.fiskeridir.no/aqua-portal-api-public/v3/api-docs"
APPLICATIONS_URL = "https://api.fiskeridir.no/aqua-portal-api-public/api/v1/applications"
LICENSE_URL = (
    "https://www.fiskeridir.no/Tall-og-analyse/Lisens-for-bruk-av-Fiskeridirektoratets-data"
)
DATASET_ID = "portal:applications"

OPENAPI = {
    "info": {
        "title": "Offentlig API for akvakultursøknader",
        "description": "API som tilgjengeliggjør alle akvakultursøknader",
        "license": {
            "name": "Lisens for bruk av Fiskeridirektoratets data",
            "url": LICENSE_URL,
        },
        "version": "1.0.0",
    },
    "servers": [
        {"url": "https://api.fiskeridir.no/aqua-portal-api-public"}
    ],
    "paths": {
        "/api/v1/evaluation/{aquaApplicationNo}": {
            "get": {"summary": "Hent evaluering for et søknadsnummer"}
        },
        "/api/v1/applications": {
            "get": {"summary": "Søk etter akvakultursøknader"}
        },
        "/api/v1/application/{applicationNo}": {
            "get": {"summary": "Hent akvakultursøknad med søknadsnummer"}
        },
    },
}
APPLICATIONS_BODY = {
    "content": [
        {
            "applicationNo": "SP-2023-000001",
            "createdAt": "2023-02-16T11:39:06.540Z",
            "status": "PROCESSED",
            "applicantOrganisationNumber": "858000742",
            "applicantOrganisationName": "FLAKSTADVÅG LAKS AS",
            "type": "CHANGE_SITE",
            "title": "HUNDBERGAN",
            "withdrawnAt": None,
            "submittedAt": None,
            "attachments": [{"id": 1}],
        },
        {
            "applicationNo": "SP-2023-000002",
            "title": None,
            "status": "RECEIVED",
        },
    ],
    "totalElements": 2,
    "page": 0,
    "size": 10,
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
        if url == APPLICATIONS_URL:
            return JsonResponse(status=200, url=url, body=APPLICATIONS_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"portal fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_paths() -> None:
    source = PortalSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["applications"]
    assert [ref.source_native_uri for ref in refs] == [APPLICATIONS_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_uses_printed_absolute_server() -> None:
    url = printed_endpoint_url(OPENAPI, "/api/v1/applications", OPENAPI_URL)
    assert url == APPLICATIONS_URL
    assert "/api-docs" not in url
    relative = printed_endpoint_url(
        {"servers": [{"url": "/"}]},
        "/api/v1/applications",
        OPENAPI_URL,
    )
    assert relative == "https://api.fiskeridir.no/api/v1/applications"


def test_portal_is_a_registered_source() -> None:
    assert "portal" in SOURCE_IDS
    source = build_source("portal")
    assert isinstance(source, PortalSource)
    assert source.source_id == "portal"


def test_harvest_writes_printed_id_license_and_null_publisher(tmp_path: Path) -> None:
    source = PortalSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "portal"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == APPLICATIONS_URL
    assert row["title"] == "Søk etter akvakultursøknader"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("fiskeridir:")
    assert not str(row["id"]).startswith("research:")
    assert not str(row["id"]).startswith("aqua:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["portal_openapi_path"] == "/api/v1/applications"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_applications(tmp_path: Path) -> None:
    source = PortalSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == APPLICATIONS_URL
    assert result.table_id == "applications"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"HUNDBERGAN", "SP-2023-000002"}
    assert by_value["HUNDBERGAN"]["measure"] == "title"
    assert by_value["SP-2023-000002"]["measure"] == "applicationNo"
    dims = json.loads(by_value["HUNDBERGAN"]["dimensions_json"])
    assert dims["applicationNo"] == "SP-2023-000001"
    assert dims["applicantOrganisationNumber"] == "858000742"
    assert "attachments" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == APPLICATIONS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_title_or_application_number() -> None:
    cells = cells_from_portal(APPLICATIONS_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "title"
    assert value == "HUNDBERGAN"
    assert dims["applicationNo"] == "SP-2023-000001"
    assert "attachments" not in dims
    fallback = cells_from_portal(
        {"content": [{"applicationNo": "SP-9", "title": None}]}
    )
    assert fallback == [("applicationNo", "SP-9", {"title": ""})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_portal([{"title": "x"}])
    with pytest.raises(ValueError, match="content array"):
        cells_from_portal({"title": "x"})
    with pytest.raises(ValueError, match="printed no collection members"):
        cells_from_portal({"content": []})


def test_is_portal_url_accepts_only_portal_public_path() -> None:
    assert is_portal_url(APPLICATIONS_URL)
    assert is_portal_url(OPENAPI_URL)
    assert portal_table_id(APPLICATIONS_URL) == "applications"
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({}) is None
    assert not is_portal_url("https://api.fiskeridir.no/vessel-api/api/v1/vessels")
    assert not is_portal_url("https://api.fiskeridir.no/buyer-api/v1/locations")
    assert not is_portal_url("https://api.fiskeridir.no/nytek-public/api/v3/certificates")
    assert not is_portal_url("https://api.fiskeridir.no/pub-aqua/api/v1/areas")
    assert not is_portal_url(
        "https://api.fiskeridir.no/aqua-research-project-api-public/api/v1/research-projects"
    )
    assert not is_portal_url("https://data.norge.no/datasets/x")
    assert not is_portal_url(
        "https://www.fiskeridir.no/aqua-portal-api-public/api/v1/applications"
    )
    assert not is_portal_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = PortalSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "applications"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert nxt == []
