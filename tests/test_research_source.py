from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.research import (
    ResearchSource,
    cells_from_research,
    is_research_url,
    printed_endpoint_url,
    printed_license_url,
    research_table_id,
)

OPENAPI_URL = "https://api.fiskeridir.no/aqua-research-project-api-public/v3/api-docs"
PROJECTS_URL = (
    "https://api.fiskeridir.no/aqua-research-project-api-public/api/v1/research-projects"
)
LICENSE_URL = (
    "https://www.fiskeridir.no/Tall-og-analyse/Lisens-for-bruk-av-Fiskeridirektoratets-data"
)
DATASET_ID = "research:research-projects"

OPENAPI = {
    "info": {
        "title": "Offentlig API for akvakulturforskning",
        "description": "API som tilgjengeliggjør all akvakulturforskning",
        "license": {
            "name": "Lisens for bruk av Fiskeridirektoratets data",
            "url": LICENSE_URL,
        },
        "version": "1.0.0",
    },
    "servers": [
        {"url": "https://api.fiskeridir.no/aqua-research-project-api-public"}
    ],
    "paths": {
        "/api/v1/research-report-file/{reportNumber}/{fileId}": {
            "get": {"summary": "Last ned fil tilknyttet en forskningsrapport"}
        },
        "/api/v1/research-projects": {
            "get": {"summary": "Søk etter forskningsprosjekter"}
        },
        "/api/v1/research-project/{projectNumber}": {
            "get": {"summary": "Hent ett forskningsprosjekt"}
        },
    },
}
PROJECTS_BODY = {
    "content": [
        {
            "projectNumber": "FP-000092",
            "name": "Klinisk utprøving av quorum sensing-antagonist",
            "description": "Dokumentere effekt på sårutvikling hos laks.",
            "licenseOwnerOrgNo": "963201230",
            "licenseOwnerOrgName": "VESO AS",
            "researchLicenses": [{"licenseNumber": "H-AV-0001"}],
            "categories": ["FISH_HEALTH"],
        },
        {
            "projectNumber": "FP-000001",
            "name": None,
            "licenseOwnerOrgNo": "999999999",
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
        if url == PROJECTS_URL:
            return JsonResponse(status=200, url=url, body=PROJECTS_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"research fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_paths() -> None:
    source = ResearchSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["research-projects"]
    assert [ref.source_native_uri for ref in refs] == [PROJECTS_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_uses_printed_absolute_server() -> None:
    url = printed_endpoint_url(OPENAPI, "/api/v1/research-projects", OPENAPI_URL)
    assert url == PROJECTS_URL
    assert "/api-docs" not in url
    relative = printed_endpoint_url(
        {"servers": [{"url": "/"}]},
        "/api/v1/research-projects",
        OPENAPI_URL,
    )
    assert relative == "https://api.fiskeridir.no/api/v1/research-projects"


def test_research_is_a_registered_source() -> None:
    assert "research" in SOURCE_IDS
    source = build_source("research")
    assert isinstance(source, ResearchSource)
    assert source.source_id == "research"


def test_harvest_writes_printed_id_license_and_null_publisher(tmp_path: Path) -> None:
    source = ResearchSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "research"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == PROJECTS_URL
    assert row["title"] == "Søk etter forskningsprosjekter"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("fiskeridir:")
    assert not str(row["id"]).startswith("nytek:")
    assert not str(row["id"]).startswith("buyer:")
    assert not str(row["id"]).startswith("aqua:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["research_openapi_path"] == "/api/v1/research-projects"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_research_projects(tmp_path: Path) -> None:
    source = ResearchSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == PROJECTS_URL
    assert result.table_id == "research-projects"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {
        "Klinisk utprøving av quorum sensing-antagonist",
        "FP-000001",
    }
    assert by_value["Klinisk utprøving av quorum sensing-antagonist"]["measure"] == "name"
    assert by_value["FP-000001"]["measure"] == "projectNumber"
    dims = json.loads(
        by_value["Klinisk utprøving av quorum sensing-antagonist"]["dimensions_json"]
    )
    assert dims["projectNumber"] == "FP-000092"
    assert dims["licenseOwnerOrgNo"] == "963201230"
    assert "researchLicenses" not in dims
    assert "categories" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == PROJECTS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_name_or_project_number() -> None:
    cells = cells_from_research(PROJECTS_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "Klinisk utprøving av quorum sensing-antagonist"
    assert dims["projectNumber"] == "FP-000092"
    assert "researchLicenses" not in dims
    fallback = cells_from_research(
        {"content": [{"projectNumber": "FP-9", "name": None}]}
    )
    assert fallback == [("projectNumber", "FP-9", {"name": ""})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_research([{"name": "x"}])
    with pytest.raises(ValueError, match="content array"):
        cells_from_research({"name": "x"})
    with pytest.raises(ValueError, match="printed no collection members"):
        cells_from_research({"content": []})


def test_is_research_url_accepts_only_research_public_path() -> None:
    assert is_research_url(PROJECTS_URL)
    assert is_research_url(OPENAPI_URL)
    assert research_table_id(PROJECTS_URL) == "research-projects"
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({}) is None
    assert not is_research_url("https://api.fiskeridir.no/vessel-api/api/v1/vessels")
    assert not is_research_url("https://api.fiskeridir.no/buyer-api/v1/locations")
    assert not is_research_url("https://api.fiskeridir.no/nytek-public/api/v3/certificates")
    assert not is_research_url("https://api.fiskeridir.no/pub-aqua/api/v1/areas")
    assert not is_research_url("https://data.norge.no/datasets/x")
    assert not is_research_url(
        "https://www.fiskeridir.no/aqua-research-project-api-public/api/v1/research-projects"
    )
    assert not is_research_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = ResearchSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "research-projects"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert nxt == []
