from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.artskart import (
    ArtskartSource,
    artskart_table_id,
    cells_from_artskart,
    is_artskart_url,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://artskart.artsdatabanken.no/publicapi/swagger/docs/v1"
LOOKUP_URL = "https://artskart.artsdatabanken.no/publicapi/api/Lookup"
LIST_URL = "https://artskart.artsdatabanken.no/publicapi/api/observations/list"
LISTALL_URL = "https://artskart.artsdatabanken.no/publicapi/api/observations/listall"
PING_URL = "https://artskart.artsdatabanken.no/publicapi/api/ping"
TAXON_URL = "https://artskart.artsdatabanken.no/publicapi/api/Taxon"
DATASET_ID = "artskart:list"

OPENAPI = {
    "swagger": "2.0",
    "info": {"title": "Artskart 2 Public Api", "version": "v1"},
    "host": "artskart.artsdatabanken.no",
    "basePath": "/publicapi",
    "schemes": ["https"],
    "paths": {
        "/api/darwincorecache/{id}": {
            "get": {
                "summary": "Get DarwinCore cache by id",
                "parameters": [{"name": "id", "required": True}],
            }
        },
        "/api/Lookup": {"get": {"summary": "Gets all lookuplists"}},
        "/api/observations/list": {
            "get": {
                "summary": "Gets a list of observation based on a filter",
                "parameters": [{"name": "pageIndex", "required": False}],
            }
        },
        "/api/observations/listall": {
            "get": {"summary": "Gets a list of observation based on a filter - test no paging"}
        },
        "/api/observations/Deleted": {
            "get": {
                "summary": "Deleted observations",
                "parameters": [{"name": "afterDateTime", "required": True}],
            }
        },
        "/api/ping": {"get": {"summary": "Ping_GetPing"}},
        "/api/Taxon": {
            "get": {
                "summary": "Get a list(dictionary) of Taxons by search",
                "parameters": [{"name": "search", "required": False}],
            }
        },
        "/api/taxon/{id}": {
            "get": {
                "summary": "Get taxon by id",
                "parameters": [{"name": "id", "required": True}],
            }
        },
    },
}

LIST_BODY = {
    "Observations": [
        {
            "ScientificName": "Myriospora scabrida",
            "species": "scabrida",
            "Id": "urn:catalog:o:l:87",
            "Name": None,
            "Municipality": "Røros",
            "Institution": "Naturhistorisk Museum - UiO",
            "nested": {"skip": True},
        },
        {
            "ScientificName": "Betula pubescens",
            "species": "pubescens",
            "Id": "urn:catalog:o:l:88",
            "Municipality": "Oslo",
            "Institution": "NTNU Vitenskapsmuseet",
        },
    ],
    "PageIndex": 0,
    "PageSize": 20,
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
        if url == LIST_URL:
            return JsonResponse(status=200, url=url, body=LIST_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"artskart fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_required_paths() -> None:
    source = ArtskartSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "Lookup",
        "list",
        "listall",
        "ping",
        "Taxon",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        LOOKUP_URL,
        LIST_URL,
        LISTALL_URL,
        PING_URL,
        TAXON_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert "" not in [ref.source_native_id for ref in refs]


def test_printed_operation_id_is_last_segment() -> None:
    assert printed_operation_id("/api/observations/list") == "list"
    assert printed_operation_id("/api/Lookup") == "Lookup"


def test_printed_endpoint_url_uses_printed_host_and_base_path() -> None:
    url = printed_endpoint_url(OPENAPI, "/api/observations/list", OPENAPI_URL)
    assert url == LIST_URL
    without_host = printed_endpoint_url(
        {"basePath": "/publicapi"}, "/api/Lookup", OPENAPI_URL
    )
    assert without_host == LOOKUP_URL


def test_printed_license_url_stays_null_when_absent() -> None:
    assert printed_license_url(OPENAPI["info"]) is None
    assert printed_license_url({"title": "Artskart 2 Public Api"}) is None


def test_artskart_is_a_registered_source() -> None:
    assert "artskart" in SOURCE_IDS
    assert "nortaxa" in SOURCE_IDS
    assert "georegister" in SOURCE_IDS
    assert "nin" in SOURCE_IDS
    assert "locationforecast" in SOURCE_IDS
    source = build_source("artskart")
    assert isinstance(source, ArtskartSource)
    assert source.source_id == "artskart"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = ArtskartSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 4
    assert counts.ignored == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "artskart"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == LIST_URL
    assert row["title"] == "Gets a list of observation based on a filter"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("nin:")
    assert not str(row["id"]).startswith("georegister:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["artskart_openapi_path"] == "/api/observations/list"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_observations(tmp_path: Path) -> None:
    source = ArtskartSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == LIST_URL
    assert result.table_id == "list"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert set(values) == {"Myriospora scabrida", "Betula pubescens"}
    assert all(row["measure"] == "ScientificName" for row in rows)
    by_name = {
        json.loads(row["value_json"]): json.loads(row["dimensions_json"]) for row in rows
    }
    assert by_name["Myriospora scabrida"] == {
        "species": "scabrida",
        "Id": "urn:catalog:o:l:87",
        "Name": "",
        "Municipality": "Røros",
        "Institution": "Naturhistorisk Museum - UiO",
    }
    assert by_name["Betula pubescens"] == {
        "species": "pubescens",
        "Id": "urn:catalog:o:l:88",
        "Municipality": "Oslo",
        "Institution": "NTNU Vitenskapsmuseet",
    }
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == LIST_URL for row in rows)
    registry.close()


def test_cells_copy_printed_scientific_names() -> None:
    cells = cells_from_artskart(LIST_BODY)
    assert cells == [
        (
            "ScientificName",
            "Myriospora scabrida",
            {
                "species": "scabrida",
                "Id": "urn:catalog:o:l:87",
                "Name": "",
                "Municipality": "Røros",
                "Institution": "Naturhistorisk Museum - UiO",
            },
        ),
        (
            "ScientificName",
            "Betula pubescens",
            {
                "species": "pubescens",
                "Id": "urn:catalog:o:l:88",
                "Municipality": "Oslo",
                "Institution": "NTNU Vitenskapsmuseet",
            },
        ),
    ]
    array_cells = cells_from_artskart(LIST_BODY["Observations"])
    assert [value for _measure, value, _dims in array_cells] == [
        "Myriospora scabrida",
        "Betula pubescens",
    ]
    with pytest.raises(ValueError, match="JSON array"):
        cells_from_artskart({"reftimes": ["2026-06-09T11:00:00Z"]})
    with pytest.raises(ValueError, match="JSON array"):
        cells_from_artskart("not-json")


def test_is_artskart_url_accepts_only_publicapi_host_path() -> None:
    assert is_artskart_url(LIST_URL)
    assert is_artskart_url(LOOKUP_URL)
    assert is_artskart_url(OPENAPI_URL) is False
    assert artskart_table_id(LIST_URL) == "list"
    assert artskart_table_id(LOOKUP_URL) == "Lookup"
    assert not is_artskart_url("https://nortaxa.artsdatabanken.no/api/v1/Lists/RankList")
    assert not is_artskart_url(
        "https://nin-kode-api.artsdatabanken.no/v3.0/koder/allekoder"
    )
    assert not is_artskart_url("https://register.geonorge.no/api/v2/organisasjoner/kommuner")
    assert not is_artskart_url("https://api.met.no/weatherapi/locationforecast/2.0/locations")
    assert not is_artskart_url("https://data.norge.no/datasets/x")
    assert not is_artskart_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = ArtskartSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["Lookup"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["list"]
