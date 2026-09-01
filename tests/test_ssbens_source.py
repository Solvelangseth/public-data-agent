from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.ssbens import (
    LIST_URL,
    SsbensSource,
    cells_from_ssbens,
    is_ssbens_url,
    printed_item_url,
    ssbens_table_id,
)

AL_URL = "https://data.ssb.no/api/v0/en/table/al"
BF_URL = "https://data.ssb.no/api/v0/en/table/bf"
NO_AL_URL = "https://data.ssb.no/api/v0/no/table/al"
TABLE_URL = "https://data.ssb.no/api/v0/en/table/01222"
SSBV2_URL = "https://data.ssb.no/api/pxwebapi/v2/tables"
KLASS_URL = "https://data.ssb.no/api/klass/v1/classifications"
CHILD_URL = "https://data.ssb.no/api/v0/en/table/al03"
DATASET_ID = "ssbens:al"

CATALOG = [
    {"id": "al", "type": "l", "text": "Labour market and earnings"},
    {"id": "bf", "type": "l", "text": "Banking and financial markets"},
    {"id": "01222", "type": "t", "text": "five-digit table id is skipped"},
    {"type": "l", "text": "missing id is skipped"},
]
ITEM_BODY = [
    {"id": "al03", "type": "l", "text": "Unemployment"},
    {"id": "al04", "type": "l", "text": "Working environment, sickness absence, strikes and lockouts"},
]


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
        if url == AL_URL:
            return JsonResponse(status=200, url=url, body=ITEM_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"ssbens fetch must GET, not POST {url}")


def test_printed_refs_copy_subject_ids() -> None:
    source = SsbensSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["al", "bf"]
    assert [ref.source_native_uri for ref in refs] == [AL_URL, BF_URL]
    assert all("/api/v0/no/table" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/api/pxwebapi/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/api/klass/" not in (ref.source_native_uri or "") for ref in refs)
    assert all(not (ref.source_native_id or "").isdigit() for ref in refs)


def test_item_url_joins_printed_subject_id() -> None:
    assert printed_item_url({"id": "al"}, LIST_URL) == AL_URL


def test_ssbens_is_a_registered_source() -> None:
    assert "ssbens" in SOURCE_IDS
    assert "ssbsubj" in SOURCE_IDS
    assert "ssb" in SOURCE_IDS
    assert "ssbv2" in SOURCE_IDS
    assert "ssclass" in SOURCE_IDS
    assert "ssbfam" in SOURCE_IDS
    assert "ssbsec" in SOURCE_IDS
    assert "ssbver" in SOURCE_IDS
    assert "ssbcorr" in SOURCE_IDS
    assert "ssbvar" in SOURCE_IDS
    assert "dsbgis" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("kvkrets") + 1] == "dsbgis"
    assert SOURCE_IDS[SOURCE_IDS.index("dsbgis") + 1] == "ssbens"
    assert SOURCE_IDS[-1] == "ssbens"
    source = build_source("ssbens")
    assert isinstance(source, SsbensSource)
    assert source.source_id == "ssbens"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = SsbensSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "ssbens"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == AL_URL
    assert row["title"] == "Labour market and earnings"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("ssbsubj:")
    assert not str(row["id"]).startswith("ssb:")
    assert not str(row["id"]).startswith("ssbv2:")
    nxt = registry.get_dataset("ssbens:bf")
    assert nxt is not None
    assert nxt["title"] == "Banking and financial markets"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "al"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["ssbens_subject"]["id"] == "al"
    assert payload["ssbens_subject"]["text"] == "Labour market and earnings"
    assert payload["ssbens_self_href"] == AL_URL
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_child_folder_names(tmp_path: Path) -> None:
    source = SsbensSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == AL_URL
    assert result.table_id == "al"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert set(values) == {
        "Unemployment",
        "Working environment, sickness absence, strikes and lockouts",
    }
    assert all(row["measure"] == "text" for row in rows)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    dims = json.loads(by_value["Unemployment"]["dimensions_json"])
    assert dims["id"] == "al03"
    assert dims["type"] == "l"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == AL_URL for row in rows)
    registry.close()


def test_cells_copy_printed_subject_members() -> None:
    cells = cells_from_ssbens(ITEM_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "text"
    assert value == "Unemployment"
    assert dims["id"] == "al03"
    fallback = cells_from_ssbens({"id": "al", "text": "Labour market and earnings"})
    assert fallback == [("text", "Labour market and earnings", {"id": "al"})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_ssbens("al")
    with pytest.raises(ValueError, match="subject members"):
        cells_from_ssbens([])


def test_is_ssbens_url_accepts_only_alphabetic_english_subject_paths() -> None:
    assert is_ssbens_url(AL_URL)
    assert is_ssbens_url(BF_URL)
    assert ssbens_table_id(AL_URL) == "al"
    assert not is_ssbens_url(LIST_URL)
    assert not is_ssbens_url(NO_AL_URL)
    assert not is_ssbens_url(TABLE_URL)
    assert not is_ssbens_url(CHILD_URL)
    assert not is_ssbens_url(SSBV2_URL)
    assert not is_ssbens_url(KLASS_URL)
    assert not is_ssbens_url("https://data.norge.no/datasets/x")
    assert not is_ssbens_url(None)


def test_limit_and_offset_slice_printed_subjects() -> None:
    source = SsbensSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["al"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["bf"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
