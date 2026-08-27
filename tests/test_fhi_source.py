from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.fhi import (
    FhiStatistikkSource,
    cells_from_fhi,
    fhi_table_id,
    is_fhi_url,
    printed_native_id,
    printed_table_url,
)

LIST_URL = "https://statistikk-data.fhi.no/api/open/v1/Common/source"
ABR_URL = "https://statistikk-data.fhi.no/api/open/v1/abr/Table"
DAAR_URL = "https://statistikk-data.fhi.no/api/open/v1/daar/Table"
NOKKEL_URL = "https://statistikk-data.fhi.no/api/open/v1/nokkel/Table"
GS_URL = "https://statistikk-data.fhi.no/api/open/v1/gs/Table"
DATASET_ID = "fhi:abr"

SOURCE_BODY = [
    {
        "id": "abr",
        "title": "Abortregisteret (ABR)",
        "description": "Om svangerskapsbrudd i Norge fra 1979 til i dag.",
        "aboutUrl": "https://www.fhi.no/op/abortregisteret",
        "publishedBy": "Folkehelseinstituttet",
    },
    {
        "id": "daar",
        "title": "Dødsårsaksregisteret (DÅR)",
        "description": "Om dødsfall og dødsårsaker i Norge fra 1951 til i dag.",
        "aboutUrl": "https://www.fhi.no/op/dodsarsaksregisteret/",
        "publishedBy": "Folkehelseinstituttet",
    },
    {
        "id": "nokkel",
        "title": "Folkehelsestatistikk",
        "description": "Statistikk om befolkning.",
        "aboutUrl": "https://www.helsedirektoratet.no/forebygging-diagnose-og-behandling",
        "publishedBy": "Helsedirektoratet",
    },
    {
        "id": "gs",
        "title": "Grossistbasert legemiddelstatistikk",
        "description": "Salg av legemidler.",
        "aboutUrl": "https://www.fhi.no/he/legemiddelbruk",
        "publishedBy": "Folkehelseinstituttet",
    },
]
TABLE_BODY = [
    {
        "tableId": 588,
        "title": "A12b: Svangerskapsavbrot fordelt på prevensjonsbruk og alder",
        "publishedAt": "2026-05-12T05:00:00Z",
        "modifiedAt": "2026-05-11T12:31:46.265306Z",
    },
    {
        "tableId": 589,
        "title": "A12a: Svangerskapsavbrot fordelt på alder",
        "publishedAt": "2026-05-12T05:00:00Z",
        "modifiedAt": "2026-05-11T12:31:46.263593Z",
    },
]


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == LIST_URL:
            return SOURCE_BODY
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == ABR_URL:
            return JsonResponse(status=200, url=url, body=TABLE_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"fhi fetch must GET, not POST {url}")


def test_printed_source_ids_become_refs() -> None:
    source = FhiStatistikkSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["abr", "daar", "nokkel", "gs"]
    assert [ref.source_native_uri for ref in refs] == [
        ABR_URL,
        DAAR_URL,
        NOKKEL_URL,
        GS_URL,
    ]
    assert LIST_URL not in [ref.source_native_uri for ref in refs]


def test_fhi_is_a_registered_source() -> None:
    assert "fhi" in SOURCE_IDS
    source = build_source("fhi")
    assert isinstance(source, FhiStatistikkSource)
    assert source.source_id == "fhi"


def test_harvest_writes_printed_id_without_license(tmp_path: Path) -> None:
    source = FhiStatistikkSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 4
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "fhi"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == ABR_URL
    assert row["title"] == "Abortregisteret (ABR)"
    assert row["publisher_name"] == "Folkehelseinstituttet"
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["fhi_metadata"]["id"] == "abr"
    assert payload["fhi_metadata"]["publishedBy"] == "Folkehelseinstituttet"
    registry.close()


def test_fetch_gets_printed_abr_table_list(tmp_path: Path) -> None:
    source = FhiStatistikkSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == ABR_URL
    assert result.table_id == "abr"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    assert [json.loads(row["value_json"]) for row in rows] == [588, 589]
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["tableId"] == "588"
    assert all(row["publisher_name"] == "Folkehelseinstituttet" for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == ABR_URL for row in rows)
    registry.close()


def test_cells_copy_printed_table_ids() -> None:
    cells = cells_from_fhi(TABLE_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure.startswith("A12b")
    assert value == 588
    assert dims["tableId"] == "588"
    with pytest.raises(ValueError, match="JSON array"):
        cells_from_fhi({"tableId": 588})


def test_is_fhi_url_accepts_only_statistikk_data() -> None:
    assert is_fhi_url(LIST_URL)
    assert is_fhi_url(ABR_URL)
    assert fhi_table_id(ABR_URL) == "abr"
    assert printed_native_id(ABR_URL) == "abr"
    assert printed_table_url("abr") == ABR_URL
    assert not is_fhi_url("https://data.norge.no/datasets/x")
    assert not is_fhi_url("https://www.fhi.no/api/open/v1/abr/Table")
    assert not is_fhi_url("https://statistikk.fhi.no/api/open/v1/abr/Table")


def test_limit_and_offset_slice_printed_sources() -> None:
    source = FhiStatistikkSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=2)] == [
        "abr",
        "daar",
    ]
    nxt = source.list_dataset_refs(limit=1, offset=3)
    assert [ref.source_native_id for ref in nxt] == ["gs"]
