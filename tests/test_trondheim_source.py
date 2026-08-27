from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.trondheim import (
    TrondheimOpenDataSource,
    cells_from_trondheim,
    is_trondheim_url,
    printed_dataset_url,
    printed_license_url,
    trondheim_table_id,
)

LIST_URL = "https://data.trondheim.kommune.no/api/v3/datasets/export.json"
BADE_URL = "https://data.trondheim.kommune.no/api/v3/dataset/e736k"
ANSATTE_URL = "https://data.trondheim.kommune.no/api/v3/dataset/2op6g"
DATASET_ID = "trondheim:e736k"
NLOD = "https://data.norge.no/nlod/no/2.0"

CATALOG = [
    {
        "id": "e736k",
        "title": "Badeplasser i Trondheimsregionen",
        "description": "Badeplasser i Trondheim og nabokommuner.",
        "webpage": "https://data.trondheim.kommune.no/dataset/badeplasser-i-trondheimsregionen-e736k",
        "licence": {"url": NLOD, "title": "Norsk lisens for offentlige data (NLOD) 2.0"},
        "resources": [
            {
                "id": "4zz",
                "title": "Badeplasser i Trondheimsregionen",
                "url": "https://data.trondheim.kommune.no/download/e736k/4zz/badeplasser.geojson",
            }
        ],
        "links": [],
    },
    {
        "id": "2op6g",
        "title": "Kommunens ansatte",
        "description": "Ansatte i Trondheim kommune.",
        "webpage": "https://data.trondheim.kommune.no/dataset/kommunens-ansatte-2op6g",
        "licence": {"url": NLOD, "title": "Norsk lisens for offentlige data (NLOD) 2.0"},
        "resources": [],
        "links": [],
    },
    {
        "title": "missing id is skipped",
        "resources": [],
    },
]

BADE_BODY = {
    "id": "e736k",
    "title": "Badeplasser i Trondheimsregionen",
    "resources": {
        "4zz": {
            "title": "Badeplasser i Trondheimsregionen",
            "url": "https://data.trondheim.kommune.no/download/e736k/4zz/badeplasser.geojson",
            "filename": "badeplasser.geojson",
        }
    },
    "links": {
        "zfn": {
            "title": "Badeplasser",
            "url": "https://geoinnsyn3.nois.no/release/",
        }
    },
    "licence": {"url": NLOD, "title": "Norsk lisens for offentlige data (NLOD) 2.0"},
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
        if url == BADE_URL:
            return JsonResponse(status=200, url=url, body=BADE_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"trondheim fetch must GET, not POST {url}")


def test_printed_refs_skip_items_without_id() -> None:
    source = TrondheimOpenDataSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["e736k", "2op6g"]
    assert [ref.source_native_uri for ref in refs] == [BADE_URL, ANSATTE_URL]
    assert LIST_URL not in [ref.source_native_uri for ref in refs]


def test_dataset_url_joins_printed_origin_and_id() -> None:
    url = printed_dataset_url("e736k", LIST_URL)
    assert url == BADE_URL
    assert "/export.json" not in url


def test_printed_license_url_copies_licence_url() -> None:
    assert printed_license_url(CATALOG[0]) == NLOD
    assert printed_license_url({"licence": {"title": "NLOD"}}) is None


def test_trondheim_is_a_registered_source() -> None:
    assert "trondheim" in SOURCE_IDS
    source = build_source("trondheim")
    assert isinstance(source, TrondheimOpenDataSource)
    assert source.source_id == "trondheim"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = TrondheimOpenDataSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "trondheim"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == BADE_URL
    assert row["title"] == "Badeplasser i Trondheimsregionen"
    assert row["publisher_name"] is None
    assert row["license"] == NLOD
    assert not str(row["id"]).startswith("datanorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["trondheim_catalog_item"]["id"] == "e736k"
    assert payload["license"] == NLOD
    assert payload["publisher"] is None
    registry.close()


def test_fetch_gets_printed_badeplass_resources(tmp_path: Path) -> None:
    source = TrondheimOpenDataSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == BADE_URL
    assert result.table_id == "e736k"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert set(values) == {"Badeplasser i Trondheimsregionen", "Badeplasser"}
    assert all(row["measure"] == "title" for row in rows)
    by_name = {json.loads(row["value_json"]): row for row in rows}
    dims = json.loads(by_name["Badeplasser"]["dimensions_json"])
    assert dims["id"] == "zfn"
    assert dims["url"] == "https://geoinnsyn3.nois.no/release/"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == NLOD for row in rows)
    assert all(row["access_path"] == BADE_URL for row in rows)
    registry.close()


def test_cells_copy_printed_resource_and_link_titles() -> None:
    cells = cells_from_trondheim(BADE_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "title"
    assert value == "Badeplasser i Trondheimsregionen"
    assert dims["id"] == "4zz"
    listed = cells_from_trondheim(
        {"resources": [{"id": "s3g", "title": "Antall ansatte.csv"}], "links": []}
    )
    assert listed == [("title", "Antall ansatte.csv", {"id": "s3g"})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_trondheim([{"title": "Badeplasser"}])
    with pytest.raises(ValueError, match="no resources or links"):
        cells_from_trondheim({"id": "24d7n", "resources": {}, "links": {}})


def test_is_trondheim_url_accepts_only_dataset_api() -> None:
    assert is_trondheim_url(BADE_URL)
    assert is_trondheim_url(ANSATTE_URL)
    assert trondheim_table_id(BADE_URL) == "e736k"
    assert not is_trondheim_url(LIST_URL)
    assert not is_trondheim_url(
        "https://data.trondheim.kommune.no/download/e736k/4zz/badeplasser.geojson"
    )
    assert not is_trondheim_url("https://oslo.kommune.no/statistikkbanken/")
    assert not is_trondheim_url("https://data.norge.no/datasets/x")
    assert not is_trondheim_url(None)


def test_limit_and_offset_slice_printed_datasets() -> None:
    source = TrondheimOpenDataSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["e736k"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["2op6g"]
