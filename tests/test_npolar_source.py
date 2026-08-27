from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.npolar import (
    NpolarSource,
    cells_from_npolar,
    is_npolar_url,
    npolar_table_id,
    printed_collection_url,
)

LIST_URL = "https://api.npolar.no/service/?q=*&format=json"
COUNTRY_URL = "https://api.npolar.no/country/?q=*&format=json"
LANGUAGE_URL = "https://api.npolar.no/language/?q=*&format=json"
DATASET_ID = "npolar:country-api"

CATALOG = {
    "feed": {
        "entries": [
            {
                "id": "language-api",
                "title": "Langauge API",
                "summary": "Langauges",
                "path": "/language",
                "open": True,
            },
            {
                "id": "country-api",
                "title": "Country API",
                "summary": "Countries",
                "path": "/country",
                "open": True,
            },
            {
                "id": "text-api",
                "title": "Text API",
                "summary": "Multilingual text storage",
                "path": "/text",
                "open": True,
            },
        ]
    }
}
COUNTRY_BODY = {
    "feed": {
        "opensearch": {"totalResults": 2, "itemsPerPage": 2, "startIndex": 0},
        "entries": [
            {
                "code": "NO",
                "languages": "nb,nn",
                "native": "Norge",
                "_rev": "1-skip",
                "name": "Norway",
                "_id": "no-1",
                "nested": {"skip": "dict"},
            },
            {
                "code": "SE",
                "name": "Sweden",
                "_id": "se-1",
            },
        ],
    }
}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == LIST_URL:
            return CATALOG
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == COUNTRY_URL:
            return JsonResponse(status=200, url=url, body=COUNTRY_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"npolar fetch must GET, not POST {url}")


def test_printed_refs_copy_service_ids_and_paths() -> None:
    source = NpolarSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "language-api",
        "country-api",
        "text-api",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        LANGUAGE_URL,
        COUNTRY_URL,
        "https://api.npolar.no/text/?q=*&format=json",
    ]
    assert all("dataset/" not in (ref.source_native_uri or "") for ref in refs)


def test_collection_url_uses_catalog_origin_and_printed_query() -> None:
    url = printed_collection_url("/country", LIST_URL)
    assert url == COUNTRY_URL
    assert url.startswith("https://api.npolar.no/country/")
    assert "q=*" in url
    assert "format=json" in url


def test_npolar_is_a_registered_source() -> None:
    assert "npolar" in SOURCE_IDS
    source = build_source("npolar")
    assert isinstance(source, NpolarSource)
    assert source.source_id == "npolar"


def test_harvest_writes_printed_id_and_null_license_publisher(tmp_path: Path) -> None:
    source = NpolarSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "npolar"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == COUNTRY_URL
    assert row["title"] == "Country API"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["npolar_service_path"] == "/country"
    assert payload["license"] is None
    assert payload["publisher"] is None
    registry.close()


def test_fetch_gets_printed_country_feed(tmp_path: Path) -> None:
    source = NpolarSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == COUNTRY_URL
    assert result.table_id == "country"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["Norway", "Sweden"]
    assert all(row["measure"] == "name" for row in rows)
    by_name = {json.loads(row["value_json"]): row for row in rows}
    dims = json.loads(by_name["Norway"]["dimensions_json"])
    assert dims["code"] == "NO"
    assert dims["native"] == "Norge"
    assert "_rev" not in dims
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == COUNTRY_URL for row in rows)
    registry.close()


def test_cells_copy_printed_name() -> None:
    cells = cells_from_npolar(COUNTRY_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "Norway"
    assert dims["code"] == "NO"
    fallback = cells_from_npolar({"feed": {"entries": [{"code": "NO", "id": "x"}]}})
    assert fallback == [("code", "NO", {"id": "x"})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_npolar([{"name": "Norway"}])
    with pytest.raises(ValueError, match="feed.entries"):
        cells_from_npolar({"feed": {"entries": "nope"}})


def test_is_npolar_url_accepts_only_npolar_host() -> None:
    assert is_npolar_url(COUNTRY_URL)
    assert is_npolar_url(LIST_URL)
    assert npolar_table_id(COUNTRY_URL) == "country"
    assert npolar_table_id("https://api.npolar.no/marine/station/?q=*") == "station"
    assert not is_npolar_url("https://geodata.npolar.no/ogc/features/v1/collections")
    assert not is_npolar_url("https://data.norge.no/datasets/x")
    assert not is_npolar_url("https://www.npolar.no/country")
    assert not is_npolar_url(None)


def test_limit_and_offset_slice_printed_services() -> None:
    source = NpolarSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=2)] == [
        "language-api",
        "country-api",
    ]
    nxt = source.list_dataset_refs(limit=1, offset=2)
    assert [ref.source_native_id for ref in nxt] == ["text-api"]
