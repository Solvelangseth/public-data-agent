from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.nortaxa import (
    NortaxaSource,
    cells_from_nortaxa,
    is_nortaxa_url,
    nortaxa_table_id,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://nortaxa.artsdatabanken.no/swagger/v1/swagger.json"
RANKLIST_URL = "https://nortaxa.artsdatabanken.no/api/v1/Lists/RankList"
STATUS_URL = "https://nortaxa.artsdatabanken.no/api/v1/Lists/TaxonomicStatusList"
TAXONCOUNT_URL = "https://nortaxa.artsdatabanken.no/api/v1/Statistics/TaxonCount"
SEARCH_URL = "https://nortaxa.artsdatabanken.no/api/v1/TaxonName/Search"
CHANGELOG_URL = "https://nortaxa.artsdatabanken.no/api/v1/TaxonName/ChangeLog"
CHANGELOG2_URL = "https://nortaxa.artsdatabanken.no/api/v1/TaxonName/ChangeLog2"
DATASET_ID = "nortaxa:RankList"

OPENAPI = {
    "swagger": "2.0",
    "info": {
        "title": "Nortaxa",
        "description": "Nortaxa (Norwegian taxonomic register)",
        "contact": {"name": "Artsdatabanken", "email": "taksonomi@artsdatabanken.no"},
        "version": "1.0",
    },
    "paths": {
        "/api/v1/Lists/RankList": {
            "get": {"summary": "Returns list of Ranks"},
        },
        "/api/v1/Lists/TaxonomicStatusList": {
            "get": {"summary": "Returns list of Taxonomic statuses"},
        },
        "/api/v1/Statistics/TaxonCount": {
            "get": {"summary": "Get count of taxa"},
        },
        "/api/v1/TaxonName/ChangeLog2": {
            "get": {"summary": "Get taxon name changes last 7 days"},
        },
        "/api/v1/TaxonName/Search": {
            "get": {
                "summary": "Search",
                "parameters": [
                    {"name": "Search", "in": "query", "required": True, "type": "string"},
                ],
            }
        },
        "/api/v1/TaxonName/ChangeLog": {
            "get": {
                "summary": "Change log",
                "parameters": [
                    {"name": "fromDate", "in": "query", "required": True, "type": "string"},
                ],
            }
        },
        "/api/v1/TaxonName/ByScientificNameId/{id}": {
            "get": {
                "summary": "templated",
                "parameters": [
                    {"name": "id", "in": "path", "required": True, "type": "integer"},
                ],
            }
        },
        "/api/v1/DataTransfer/DataToExcel": {
            "post": {"summary": "export"},
        },
    },
}
RANKLIST_BODY = [
    {"id": 1, "name": "Kingdom"},
    {"id": 2, "name": "Subkingdom", "nested": {"skip": True}},
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
        if url == RANKLIST_URL:
            return JsonResponse(status=200, url=url, body=RANKLIST_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nortaxa fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_required_and_post_paths() -> None:
    source = NortaxaSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "RankList",
        "TaxonomicStatusList",
        "TaxonCount",
        "ChangeLog2",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        RANKLIST_URL,
        STATUS_URL,
        TAXONCOUNT_URL,
        CHANGELOG2_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]
    assert SEARCH_URL not in [ref.source_native_uri for ref in refs]
    assert CHANGELOG_URL not in [ref.source_native_uri for ref in refs]
    assert "" not in [ref.source_native_id for ref in refs]
    assert all("Search" not in (ref.source_native_id or "") for ref in refs)
    assert all(ref.source_native_id != "ChangeLog" for ref in refs)


def test_endpoint_url_uses_origin_when_host_absent() -> None:
    url = printed_endpoint_url(OPENAPI, "/api/v1/Lists/RankList", OPENAPI_URL)
    assert url == RANKLIST_URL
    assert "swagger" not in url
    with_host = printed_endpoint_url(
        {
            "host": "nortaxa.artsdatabanken.no",
            "schemes": ["https"],
        },
        "/api/v1/Lists/RankList",
        OPENAPI_URL,
    )
    assert with_host == RANKLIST_URL
    with_server = printed_endpoint_url(
        {"servers": [{"url": "https://nortaxa.artsdatabanken.no/"}]},
        "/api/v1/Lists/RankList",
        OPENAPI_URL,
    )
    assert with_server == RANKLIST_URL


def test_printed_operation_id_is_last_path_segment() -> None:
    assert printed_operation_id("/api/v1/Lists/RankList") == "RankList"
    assert printed_operation_id("/api/v1/Statistics/TaxonCount") == "TaxonCount"


def test_printed_license_url_is_null_when_swagger_prints_none() -> None:
    assert printed_license_url(OPENAPI["info"]) is None
    assert printed_license_url({"title": "Nortaxa"}) is None
    assert (
        printed_license_url({"license": {"url": "https://creativecommons.org/licenses/by/4.0"}})
        == "https://creativecommons.org/licenses/by/4.0"
    )


def test_nortaxa_is_a_registered_source() -> None:
    assert "nortaxa" in SOURCE_IDS
    assert "nin" in SOURCE_IDS
    assert "locationforecast" in SOURCE_IDS
    source = build_source("nortaxa")
    assert isinstance(source, NortaxaSource)
    assert source.source_id == "nortaxa"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = NortaxaSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 4
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nortaxa"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == RANKLIST_URL
    assert row["title"] == "Returns list of Ranks"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("nin:")
    assert not str(row["id"]).startswith("locationforecast:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["nortaxa_openapi_path"] == "/api/v1/Lists/RankList"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_rank_names(tmp_path: Path) -> None:
    source = NortaxaSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == RANKLIST_URL
    assert result.table_id == "RankList"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"Kingdom", "Subkingdom"}
    assert by_value["Kingdom"]["measure"] == "name"
    dims = json.loads(by_value["Kingdom"]["dimensions_json"])
    assert dims["id"] == "1"
    assert "nested" not in dims
    assert by_value["Subkingdom"]["measure"] == "name"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == RANKLIST_URL for row in rows)
    registry.close()


def test_cells_copy_printed_name_or_scalar() -> None:
    cells = cells_from_nortaxa(RANKLIST_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "Kingdom"
    assert dims["id"] == "1"
    assert "nested" not in dims
    fallback = cells_from_nortaxa([{"displayName": "nom. inval.", "id": 1}])
    assert fallback == [("displayName", "nom. inval.", {"id": "1"})]
    assert cells_from_nortaxa(152929) == [("value", 152929, {})]
    counts = cells_from_nortaxa({"totalCount": 10, "acceptedCount": 8})
    assert counts[0][0] == "totalCount"
    assert counts[0][1] == 10
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_nortaxa(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_nortaxa([])


def test_is_nortaxa_url_accepts_only_nortaxa_host_path() -> None:
    assert is_nortaxa_url(RANKLIST_URL)
    assert is_nortaxa_url(OPENAPI_URL) is False
    assert nortaxa_table_id(RANKLIST_URL) == "RankList"
    assert printed_endpoint_url(OPENAPI, "/api/v1/Lists/RankList", OPENAPI_URL) == RANKLIST_URL
    assert not is_nortaxa_url("https://nin-kode-api.artsdatabanken.no/v3.0/typer/allekoder")
    assert not is_nortaxa_url("https://api.met.no/weatherapi/locationforecast/2.0/locations")
    assert not is_nortaxa_url("https://dnl.kartverket.no/api/ogc/v1/collections")
    assert not is_nortaxa_url("https://data.norge.no/datasets/x")
    assert not is_nortaxa_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = NortaxaSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "RankList"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=2)
    assert [ref.source_native_id for ref in nxt] == ["TaxonCount"]
