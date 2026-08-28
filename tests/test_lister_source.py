from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.lister import (
    ListerSource,
    cells_from_lister,
    is_lister_url,
    lister_table_id,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://lister.artsdatabanken.no/swagger/v1/swagger.json"
ALIENS_URL = "https://lister.artsdatabanken.no/odata/v1/alienspeciesassessment"
ALIENS2023_URL = "https://lister.artsdatabanken.no/odata/v1/alienspeciesassessment2023"
METADATA_URL = "https://lister.artsdatabanken.no/odata/v1/$metadata"
SERVICE_URL = "https://lister.artsdatabanken.no/odata/v1"
NATURE_URL = "https://lister.artsdatabanken.no/odata/v1/naturetypesassessment2025"
SPECIES_URL = "https://lister.artsdatabanken.no/odata/v1/speciesassessment2021"
TEST_URL = "https://lister.artsdatabanken.no/api/test"
KEYED_URL = "https://lister.artsdatabanken.no/odata/v1/naturetypesassessment2025/{key}"
DATASET_ID = "lister:naturetypesassessment2025"

OPENAPI = {
    "openapi": "3.0.4",
    "info": {"title": "Assessments API", "version": "v1"},
    "paths": {
        "/odata/v1/alienspeciesassessment": {
            "get": {"summary": "odata/v1/AlienSpeciesAssessment"},
        },
        "/odata/v1/alienspeciesassessment/{key}": {
            "get": {
                "summary": "odata/v1/AlienSpeciesAssessment/{key}",
                "parameters": [{"name": "key", "in": "path", "required": True}],
            }
        },
        "/odata/v1/alienspeciesassessment2023": {
            "get": {"summary": "odata/v1/AlienSpeciesAssessment2023"},
        },
        "/odata/v1/$metadata": {"get": {"summary": "odata/v1/$metadata"}},
        "/odata/v1": {"get": {"summary": "odata/v1/"}},
        "/odata/v1/naturetypesassessment2025": {
            "get": {"summary": "odata/v1/NatureTypesAssessment2025"},
        },
        "/odata/v1/naturetypesassessment2025/{key}": {
            "get": {
                "summary": "odata/v1/NatureTypesAssessment2025/{key}",
                "parameters": [{"name": "key", "in": "path", "required": True}],
            }
        },
        "/odata/v1/speciesassessment2021": {
            "get": {
                "summary": "odata/v1/SpeciesAssessment2021",
                "parameters": [{"name": "$top", "in": "query", "required": False}],
            }
        },
        "/api/test": {"get": {"operationId": "Ping"}},
        "/api/search": {
            "get": {
                "summary": "requires a query",
                "parameters": [{"name": "q", "in": "query", "required": True}],
            }
        },
        "/api/export": {"post": {"summary": "export"}},
    },
}

NATURE_BODY = {
    "@odata.context": "https://lister.artsdatabanken.no/odata/v1/$metadata#NatureTypesAssessment2025",
    "value": [
        {
            "id": 1,
            "name": "Lite uttørkingseksponert svært til noe kalkfattig nakent berg",
            "popularName": "Lite tørkeutsatt fattig nakent berg",
            "category": "LC",
            "nested": {"skip": True},
        },
        {
            "id": 2,
            "name": "Svært uttørkingseksponert kalkfattig nakent berg",
            "popularName": "Tørkeutsatt fattig nakent berg",
            "category": "NT",
        },
    ],
    "@odata.nextLink": "https://lister.artsdatabanken.no/odata/v1/naturetypesassessment2025?$skip=100",
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
        if url == NATURE_URL:
            return JsonResponse(status=200, url=url, body=NATURE_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"lister fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_required_and_post_paths() -> None:
    source = ListerSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "alienspeciesassessment",
        "alienspeciesassessment2023",
        "$metadata",
        "v1",
        "naturetypesassessment2025",
        "speciesassessment2021",
        "test",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        ALIENS_URL,
        ALIENS2023_URL,
        METADATA_URL,
        SERVICE_URL,
        NATURE_URL,
        SPECIES_URL,
        TEST_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert KEYED_URL not in [ref.source_native_uri for ref in refs]
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]
    assert "" not in [ref.source_native_id for ref in refs]
    assert all(ref.source_native_id != "search" for ref in refs)
    assert all(ref.source_native_id != "export" for ref in refs)


def test_endpoint_url_uses_origin_when_host_absent() -> None:
    url = printed_endpoint_url(OPENAPI, "/odata/v1/naturetypesassessment2025", OPENAPI_URL)
    assert url == NATURE_URL
    assert "swagger" not in url
    with_host = printed_endpoint_url(
        {
            "host": "lister.artsdatabanken.no",
            "schemes": ["https"],
        },
        "/odata/v1/naturetypesassessment2025",
        OPENAPI_URL,
    )
    assert with_host == NATURE_URL
    with_server = printed_endpoint_url(
        {"servers": [{"url": "https://lister.artsdatabanken.no/"}]},
        "/odata/v1/naturetypesassessment2025",
        OPENAPI_URL,
    )
    assert with_server == NATURE_URL


def test_printed_operation_id_is_last_path_segment() -> None:
    assert printed_operation_id("/odata/v1/naturetypesassessment2025") == "naturetypesassessment2025"
    assert printed_operation_id("/odata/v1/$metadata") == "$metadata"
    assert printed_operation_id("/api/test") == "test"


def test_printed_license_url_is_null_when_swagger_prints_none() -> None:
    assert printed_license_url(OPENAPI["info"]) is None
    assert printed_license_url({"title": "Assessments API"}) is None
    assert (
        printed_license_url({"license": {"url": "https://creativecommons.org/licenses/by/4.0"}})
        == "https://creativecommons.org/licenses/by/4.0"
    )


def test_lister_is_a_registered_source() -> None:
    assert "lister" in SOURCE_IDS
    assert "artskart" in SOURCE_IDS
    assert "nortaxa" in SOURCE_IDS
    assert "nin" in SOURCE_IDS
    assert "georegister" in SOURCE_IDS
    source = build_source("lister")
    assert isinstance(source, ListerSource)
    assert source.source_id == "lister"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = ListerSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 7
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "lister"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == NATURE_URL
    assert row["title"] == "odata/v1/NatureTypesAssessment2025"
    ping = registry.get_dataset("lister:test")
    assert ping is not None
    assert ping["title"] == "Ping"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("nin:")
    assert not str(row["id"]).startswith("nortaxa:")
    assert not str(row["id"]).startswith("artskart:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["lister_openapi_path"] == "/odata/v1/naturetypesassessment2025"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_nature_type_names(tmp_path: Path) -> None:
    source = ListerSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == NATURE_URL
    assert result.table_id == "naturetypesassessment2025"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {
        "Lite uttørkingseksponert svært til noe kalkfattig nakent berg",
        "Svært uttørkingseksponert kalkfattig nakent berg",
    }
    assert by_value["Lite uttørkingseksponert svært til noe kalkfattig nakent berg"]["measure"] == "name"
    dims = json.loads(
        by_value["Lite uttørkingseksponert svært til noe kalkfattig nakent berg"]["dimensions_json"]
    )
    assert dims["id"] == "1"
    assert dims["popularName"] == "Lite tørkeutsatt fattig nakent berg"
    assert dims["category"] == "LC"
    assert "nested" not in dims
    assert "@odata.context" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == NATURE_URL for row in rows)
    registry.close()


def test_cells_copy_printed_odata_names_or_scalar() -> None:
    cells = cells_from_lister(NATURE_BODY)
    assert cells == [
        (
            "name",
            "Lite uttørkingseksponert svært til noe kalkfattig nakent berg",
            {
                "id": "1",
                "popularName": "Lite tørkeutsatt fattig nakent berg",
                "category": "LC",
            },
        ),
        (
            "name",
            "Svært uttørkingseksponert kalkfattig nakent berg",
            {
                "id": "2",
                "popularName": "Tørkeutsatt fattig nakent berg",
                "category": "NT",
            },
        ),
    ]
    array_cells = cells_from_lister(NATURE_BODY["value"])
    assert [value for _measure, value, _dims in array_cells] == [
        "Lite uttørkingseksponert svært til noe kalkfattig nakent berg",
        "Svært uttørkingseksponert kalkfattig nakent berg",
    ]
    fallback = cells_from_lister([{"popularName": "nakent berg", "id": 1}])
    assert fallback == [("popularName", "nakent berg", {"id": "1"})]
    assert cells_from_lister("Hello from Production") == [("value", "Hello from Production", {})]
    service = cells_from_lister(
        {"@odata.context": "https://lister.artsdatabanken.no/odata/v1/$metadata", "value": [{"name": "SpeciesAssessment2021", "kind": "EntitySet"}]}
    )
    assert service == [("name", "SpeciesAssessment2021", {"kind": "EntitySet"})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_lister(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_lister({"value": []})


def test_is_lister_url_accepts_only_lister_host_path() -> None:
    assert is_lister_url(NATURE_URL)
    assert is_lister_url(TEST_URL)
    assert is_lister_url(OPENAPI_URL) is False
    assert lister_table_id(NATURE_URL) == "naturetypesassessment2025"
    assert lister_table_id(TEST_URL) == "test"
    assert not is_lister_url("https://artskart.artsdatabanken.no/publicapi/api/observations/list")
    assert not is_lister_url("https://nortaxa.artsdatabanken.no/api/v1/Lists/RankList")
    assert not is_lister_url("https://nin-kode-api.artsdatabanken.no/v3.0/koder/allekoder")
    assert not is_lister_url("https://register.geonorge.no/api/v2/organisasjoner/kommuner")
    assert not is_lister_url("https://data.norge.no/datasets/x")
    assert not is_lister_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = ListerSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "alienspeciesassessment"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=4)
    assert [ref.source_native_id for ref in nxt] == ["naturetypesassessment2025"]
