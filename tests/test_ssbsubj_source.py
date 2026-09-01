from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.ssbsubj import (
    LIST_URL,
    SsbsubjSource,
    cells_from_ssbsubj,
    is_ssbsubj_url,
    printed_item_url,
    ssbsubj_table_id,
)

AL_URL = "https://data.ssb.no/api/v0/no/table/al"
BF_URL = "https://data.ssb.no/api/v0/no/table/bf"
TABLE_URL = "https://data.ssb.no/api/v0/no/table/01222"
SSBV2_URL = "https://data.ssb.no/api/pxwebapi/v2/tables"
KLASS_URL = "https://data.ssb.no/api/klass/v1/classifications"
CHILD_URL = "https://data.ssb.no/api/v0/no/table/al03"
DATASET_ID = "ssbsubj:al"

CATALOG = [
    {"id": "al", "type": "l", "text": "Arbeid og lønn"},
    {"id": "bf", "type": "l", "text": "Bank og finansmarked"},
    {"id": "01222", "type": "t", "text": "five-digit table id is skipped"},
    {"type": "l", "text": "missing id is skipped"},
]
ITEM_BODY = [
    {"id": "al03", "type": "l", "text": "Arbeidsledighet"},
    {"id": "al04", "type": "l", "text": "Arbeidsmiljø, sykefravær og arbeidskonflikter"},
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
        raise AssertionError(f"ssbsubj fetch must GET, not POST {url}")


def test_printed_refs_copy_subject_ids() -> None:
    source = SsbsubjSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["al", "bf"]
    assert [ref.source_native_uri for ref in refs] == [AL_URL, BF_URL]
    assert all("/api/pxwebapi/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/api/klass/" not in (ref.source_native_uri or "") for ref in refs)
    assert all(not (ref.source_native_id or "").isdigit() for ref in refs)


def test_item_url_joins_printed_subject_id() -> None:
    assert printed_item_url({"id": "al"}, LIST_URL) == AL_URL


def test_ssbsubj_is_a_registered_source() -> None:
    assert "ssbsubj" in SOURCE_IDS
    assert "ssb" in SOURCE_IDS
    assert "ssbv2" in SOURCE_IDS
    assert "ssclass" in SOURCE_IDS
    assert "ssbfam" in SOURCE_IDS
    assert "ssbsec" in SOURCE_IDS
    assert "ssbver" in SOURCE_IDS
    assert "ssbcorr" in SOURCE_IDS
    assert "ssbvar" in SOURCE_IDS
    assert "brunder" in SOURCE_IDS
    assert "kikommuner" in SOURCE_IDS
    assert "fbgis" in SOURCE_IDS
    assert "stperioder" in SOURCE_IDS
    assert "kifylker" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("broppdater") + 1] == "kifylker"
    assert SOURCE_IDS[SOURCE_IDS.index("kifylker") + 1] == "brrepresent"
    assert SOURCE_IDS[SOURCE_IDS.index("brenheter") + 1] == "ssbvar"
    assert SOURCE_IDS[SOURCE_IDS.index("ssbvar") + 1] == "nordatlas"
    assert SOURCE_IDS[SOURCE_IDS.index("nordatlas") + 1] == "brunder"
    assert SOURCE_IDS[SOURCE_IDS.index("brunder") + 1] == "kikommuner"
    assert SOURCE_IDS[SOURCE_IDS.index("kikommuner") + 1] == "fbgis"
    assert SOURCE_IDS[SOURCE_IDS.index("fbgis") + 1] == "stperioder"
    assert SOURCE_IDS[SOURCE_IDS.index("stperioder") + 1] == "nibioar50"
    assert SOURCE_IDS[SOURCE_IDS.index("nibioar50") + 1] == "brorgformen"
    assert SOURCE_IDS[SOURCE_IDS.index("brorgformen") + 1] == "crinst"
    assert SOURCE_IDS[SOURCE_IDS.index("crinst") + 1] == "stsaker"
    assert SOURCE_IDS[SOURCE_IDS.index("stsaker") + 1] == "ssbsubj"
    assert SOURCE_IDS[SOURCE_IDS.index("ssbsubj") + 1] == "stkomiteer"
    assert SOURCE_IDS[SOURCE_IDS.index("stkomiteer") + 1] == "crunit"
    assert SOURCE_IDS[SOURCE_IDS.index("crunit") + 1] == "barmark"
    assert SOURCE_IDS[SOURCE_IDS.index("barmark") + 1] == "crproj"
    assert SOURCE_IDS[SOURCE_IDS.index("crproj") + 1] == "ssbgis"
    assert SOURCE_IDS[SOURCE_IDS.index("ssbgis") + 1] == "stpartier"
    assert SOURCE_IDS[SOURCE_IDS.index("stpartier") + 1] == "crbio"
    assert SOURCE_IDS[SOURCE_IDS.index("crbio") + 1] == "nibioar5f"
    assert SOURCE_IDS[SOURCE_IDS.index("nibioar5f") + 1] == "kvfkb"
    assert SOURCE_IDS[SOURCE_IDS.index("kvfkb") + 1] == "crperson"
    assert SOURCE_IDS[SOURCE_IDS.index("crperson") + 1] == "stsporre"
    assert SOURCE_IDS[SOURCE_IDS.index("stsporre") + 1] == "crresult"
    assert SOURCE_IDS[SOURCE_IDS.index("crresult") + 1] == "stmoter"
    assert SOURCE_IDS[SOURCE_IDS.index("stmoter") + 1] == "ssbfritid"
    assert SOURCE_IDS[SOURCE_IDS.index("ssbfritid") + 1] == "kvadm"
    assert SOURCE_IDS[SOURCE_IDS.index("kvadm") + 1] == "kvkrets"
    assert SOURCE_IDS[SOURCE_IDS.index("kvkrets") + 1] == "dsbgis"
    assert SOURCE_IDS[SOURCE_IDS.index("dsbgis") + 1] == "ssbens"
    assert SOURCE_IDS[-1] == "ssbens"
    source = build_source("ssbsubj")
    assert isinstance(source, SsbsubjSource)
    assert source.source_id == "ssbsubj"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = SsbsubjSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "ssbsubj"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == AL_URL
    assert row["title"] == "Arbeid og lønn"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("ssb:")
    assert not str(row["id"]).startswith("ssbv2:")
    nxt = registry.get_dataset("ssbsubj:bf")
    assert nxt is not None
    assert nxt["title"] == "Bank og finansmarked"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "al"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["ssbsubj_subject"]["id"] == "al"
    assert payload["ssbsubj_subject"]["text"] == "Arbeid og lønn"
    assert payload["ssbsubj_self_href"] == AL_URL
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_child_folder_names(tmp_path: Path) -> None:
    source = SsbsubjSource(http=CatalogHttp())
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
        "Arbeidsledighet",
        "Arbeidsmiljø, sykefravær og arbeidskonflikter",
    }
    assert all(row["measure"] == "text" for row in rows)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    dims = json.loads(by_value["Arbeidsledighet"]["dimensions_json"])
    assert dims["id"] == "al03"
    assert dims["type"] == "l"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == AL_URL for row in rows)
    registry.close()


def test_cells_copy_printed_subject_members() -> None:
    cells = cells_from_ssbsubj(ITEM_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "text"
    assert value == "Arbeidsledighet"
    assert dims["id"] == "al03"
    fallback = cells_from_ssbsubj({"id": "al", "text": "Arbeid og lønn"})
    assert fallback == [("text", "Arbeid og lønn", {"id": "al"})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_ssbsubj("al")
    with pytest.raises(ValueError, match="subject members"):
        cells_from_ssbsubj([])


def test_is_ssbsubj_url_accepts_only_alphabetic_subject_paths() -> None:
    assert is_ssbsubj_url(AL_URL)
    assert is_ssbsubj_url(BF_URL)
    assert ssbsubj_table_id(AL_URL) == "al"
    assert not is_ssbsubj_url(LIST_URL)
    assert not is_ssbsubj_url(TABLE_URL)
    assert not is_ssbsubj_url(CHILD_URL)
    assert not is_ssbsubj_url(SSBV2_URL)
    assert not is_ssbsubj_url(KLASS_URL)
    assert not is_ssbsubj_url("https://data.norge.no/datasets/x")
    assert not is_ssbsubj_url(None)


def test_limit_and_offset_slice_printed_subjects() -> None:
    source = SsbsubjSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["al"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["bf"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
