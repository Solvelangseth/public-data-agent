from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.valg import (
    ValgresultatSource,
    cells_from_valg,
    is_valg_url,
    printed_endpoint_url,
    printed_native_id,
    valg_table_id,
)

LIST_URL = "https://valgresultat.no/api"
ST2009_URL = "https://valgresultat.no/api/2009/st"
FY2011_URL = "https://valgresultat.no/api/2011/fy"
KO2011_URL = "https://valgresultat.no/api/2011/ko"
SA2013_URL = "https://valgresultat.no/api/2013/sa"
DATASET_ID = "valg:2009/st"

ROOT_BODY = {
    "_sublinks": {
        "2009": [{"href": "/2009/st", "navn": "st"}],
        "2011": [
            {"href": "/2011/fy", "navn": "fy"},
            {"href": "/2011/ko", "navn": "ko"},
        ],
        "2013": [{"href": "/2013/sa", "navn": "sa"}],
    },
    "_links": {
        "self": {"href": "/"},
        "related": [{"href": "/2009", "navn": "2009"}],
    },
}
ST2009_BODY = {
    "id": {"valgaar": "2009", "valgtype": "ST", "nivaa": "land", "navn": "norge", "nr": "0"},
    "partier": [
        {
            "id": {"partikode": "A", "navn": "Arbeiderpartiet"},
            "stemmer": {"resultat": {"prosent": 35.37396, "antall": {"total": 949049}}},
        },
        {
            "id": {"partikode": "SV", "navn": "Sosialistisk Venstreparti"},
            "stemmer": {"resultat": {"prosent": 6.20078, "antall": {"total": 166361}}},
        },
    ],
}
COLLECTION_URLS = {ST2009_URL, FY2011_URL, KO2011_URL, SA2013_URL}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == LIST_URL:
            return ROOT_BODY
        if url == ST2009_URL:
            return ST2009_BODY
        if url in COLLECTION_URLS:
            return {"id": {"valgaar": "2011", "valgtype": "FY"}}
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == ST2009_URL:
            return JsonResponse(status=200, url=url, body=ST2009_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"valg fetch must GET, not POST {url}")


def test_printed_sublinks_become_refs_and_year_folders_are_skipped() -> None:
    source = ValgresultatSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "2009/st",
        "2011/fy",
        "2011/ko",
        "2013/sa",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        ST2009_URL,
        FY2011_URL,
        KO2011_URL,
        SA2013_URL,
    ]
    assert "2009" not in [ref.source_native_id for ref in refs]
    assert LIST_URL not in [ref.source_native_uri for ref in refs]


def test_valg_is_a_registered_source() -> None:
    assert "valg" in SOURCE_IDS
    source = build_source("valg")
    assert isinstance(source, ValgresultatSource)
    assert source.source_id == "valg"


def test_harvest_writes_printed_href_without_license_or_publisher(tmp_path: Path) -> None:
    source = ValgresultatSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 4
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "valg"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == ST2009_URL
    assert row["title"] == "2009/st"
    assert row["license"] is None
    assert row["publisher_name"] is None
    assert not str(row["id"]).startswith("datanorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["valg_metadata"]["partier"][0]["id"]["partikode"] == "A"
    registry.close()


def test_fetch_gets_printed_2009_st_url(tmp_path: Path) -> None:
    source = ValgresultatSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == ST2009_URL
    assert result.table_id == "2009/st"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    assert [json.loads(row["value_json"]) for row in rows] == [949049, 166361]
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["partikode"] == "A"
    assert dims["navn"] == "Arbeiderpartiet"
    assert dims["valgaar"] == "2009"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == ST2009_URL for row in rows)
    registry.close()


def test_cells_copy_printed_party_totals() -> None:
    cells = cells_from_valg(ST2009_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "Arbeiderpartiet"
    assert value == 949049
    assert dims["partikode"] == "A"
    assert dims["valgtype"] == "ST"
    with pytest.raises(ValueError, match="partier"):
        cells_from_valg({"id": {"valgaar": "2009"}})


def test_is_valg_url_accepts_only_valgresultat_api() -> None:
    assert is_valg_url(LIST_URL)
    assert is_valg_url(ST2009_URL)
    assert valg_table_id(ST2009_URL) == "2009/st"
    assert printed_native_id("/2009/st") == "2009/st"
    assert printed_endpoint_url(LIST_URL, "/2009/st") == ST2009_URL
    assert not is_valg_url("https://data.norge.no/datasets/x")
    assert not is_valg_url("https://www.valgresultat.no/api/2009/st")
    assert not is_valg_url("https://valgresultat.no/2009/st")
    assert not is_valg_url("https://example.com/api/2009/st")


def test_limit_and_offset_slice_printed_sublinks() -> None:
    source = ValgresultatSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=2)] == [
        "2009/st",
        "2011/fy",
    ]
    nxt = source.list_dataset_refs(limit=1, offset=3)
    assert [ref.source_native_id for ref in nxt] == ["2013/sa"]
