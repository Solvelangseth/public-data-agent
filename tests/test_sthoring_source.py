from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.sthoring import (
    LIST_URL,
    SthoringSource,
    cells_from_sthoring,
    is_sthoring_url,
    printed_item_url,
    sthoring_table_id,
)

SESSION_2025_URL = (
    "https://data.stortinget.no/eksport/horinger?sesjonid=2025-2026&format=json"
)
SESSION_2024_URL = (
    "https://data.stortinget.no/eksport/horinger?sesjonid=2024-2025&format=json"
)
STORTINGET_SESJONER_URL = "https://data.stortinget.no/eksport/sesjoner?format=json"
STORTINGET_PERIODER_URL = "https://data.stortinget.no/eksport/stortingsperioder?format=json"
STSAKER_URL = "https://data.stortinget.no/eksport/saker?sesjonid=2025-2026&format=json"
STKOMITEER_URL = "https://data.stortinget.no/eksport/komiteer?sesjonid=2025-2026&format=json"
STPARTIER_URL = "https://data.stortinget.no/eksport/partier?sesjonid=2025-2026&format=json"
STSPORRE_URL = (
    "https://data.stortinget.no/eksport/sporretimesporsmal"
    "?sesjonid=2025-2026&format=json"
)
STMOTER_URL = "https://data.stortinget.no/eksport/moter?sesjonid=2025-2026&format=json"
STSKRIFT_URL = (
    "https://data.stortinget.no/eksport/skriftligesporsmal"
    "?sesjonid=2025-2026&format=json"
)
STPERIODER_URL = (
    "https://data.stortinget.no/eksport/representanter"
    "?stortingsperiodeid=2025-2029&format=json"
)
DATANORGE_URL = "https://data.norge.no/datasets/x"
DATASET_ID = "sthoring:2025-2026"

CATALOG = {
    "sesjoner_liste": [
        {"id": "2025-2026", "versjon": "1.6"},
        {"id": "2024-2025", "versjon": "1.6"},
        {"versjon": "missing id is skipped"},
    ]
}
ITEM_BODY = {
    "sesjon_id": "2025-2026",
    "horinger_liste": [
        {
            "id": 10005544,
            "horing_status": "Avholdt",
            "skriftlig": False,
        }
    ],
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
        if url == SESSION_2025_URL:
            return JsonResponse(status=200, url=url, body=ITEM_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"sthoring fetch must GET, not POST {url}")


def test_printed_refs_copy_sesjon_id() -> None:
    source = SthoringSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["2025-2026", "2024-2025"]
    assert [ref.source_native_uri for ref in refs] == [SESSION_2025_URL, SESSION_2024_URL]
    assert all("/saker" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/komiteer" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/partier" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/representanter" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/moter" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/sporretimesporsmal" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/skriftligesporsmal" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_joins_printed_sesjon_id() -> None:
    assert printed_item_url({"id": "2025-2026"}, LIST_URL) == SESSION_2025_URL


def test_sthoring_is_a_registered_source() -> None:
    assert "sthoring" in SOURCE_IDS
    assert "stskrift" in SOURCE_IDS
    assert "nibiogard" in SOURCE_IDS
    assert "dsbgis" in SOURCE_IDS
    assert "kvkrets" in SOURCE_IDS
    assert "kvadm" in SOURCE_IDS
    assert "ssbfritid" in SOURCE_IDS
    assert "stmoter" in SOURCE_IDS
    assert "stsporre" in SOURCE_IDS
    assert "crresult" in SOURCE_IDS
    assert "stpartier" in SOURCE_IDS
    assert "stortinget" in SOURCE_IDS
    assert "stkomiteer" in SOURCE_IDS
    assert "stperioder" in SOURCE_IDS
    assert "stsaker" in SOURCE_IDS
    assert "ssbsubj" in SOURCE_IDS
    assert "datanorge" in SOURCE_IDS
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
    assert SOURCE_IDS[SOURCE_IDS.index("dsbgis") + 1] == "nibiogard"
    assert SOURCE_IDS[SOURCE_IDS.index("nibiogard") + 1] == "stskrift"
    assert SOURCE_IDS[SOURCE_IDS.index("stskrift") + 1] == "sthoring"
    assert SOURCE_IDS[-1] == "sthoring"
    source = build_source("sthoring")
    assert isinstance(source, SthoringSource)
    assert source.source_id == "sthoring"


def test_harvest_writes_printed_sesjon_id_and_null_license(tmp_path: Path) -> None:
    source = SthoringSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "sthoring"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == SESSION_2025_URL
    assert row["title"] == "2025-2026"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("stortinget:")
    assert not str(row["id"]).startswith("stkomiteer:")
    assert not str(row["id"]).startswith("stpartier:")
    assert not str(row["id"]).startswith("stsaker:")
    assert not str(row["id"]).startswith("stsporre:")
    assert not str(row["id"]).startswith("stmoter:")
    nxt = registry.get_dataset("sthoring:2024-2025")
    assert nxt is not None
    assert nxt["title"] == "2024-2025"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "2025-2026"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["sthoring_sesjon"]["id"] == "2025-2026"
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_horing_id(tmp_path: Path) -> None:
    source = SthoringSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == SESSION_2025_URL
    assert result.table_id == "2025-2026"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == [10005544]
    assert all(row["measure"] == "id" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["horing_status"] == "Avholdt"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == SESSION_2025_URL for row in rows)
    registry.close()


def test_cells_copy_printed_horinger() -> None:
    cells = cells_from_sthoring(ITEM_BODY)
    assert cells[0][0] == "id"
    assert cells[0][1] == 10005544
    assert cells[0][2]["horing_status"] == "Avholdt"
    fallback = cells_from_sthoring({"id": "2025-2026"})
    assert fallback == [("id", "2025-2026", {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_sthoring(["10005544"])
    with pytest.raises(ValueError, match="horing members"):
        cells_from_sthoring({"horinger_liste": [{"komite": {"id": "ARBSOS"}}]})


def test_is_sthoring_url_accepts_only_horinger_sesjon_paths() -> None:
    assert is_sthoring_url(SESSION_2025_URL)
    assert is_sthoring_url(SESSION_2024_URL)
    assert sthoring_table_id(SESSION_2025_URL) == "2025-2026"
    assert not is_sthoring_url(LIST_URL)
    assert not is_sthoring_url(STORTINGET_SESJONER_URL)
    assert not is_sthoring_url(STORTINGET_PERIODER_URL)
    assert not is_sthoring_url(STSAKER_URL)
    assert not is_sthoring_url(STKOMITEER_URL)
    assert not is_sthoring_url(STPARTIER_URL)
    assert not is_sthoring_url(STSPORRE_URL)
    assert not is_sthoring_url(STMOTER_URL)
    assert not is_sthoring_url(STSKRIFT_URL)
    assert not is_sthoring_url(STPERIODER_URL)
    assert not is_sthoring_url("https://data.stortinget.no/eksport/horinger")
    assert not is_sthoring_url(DATANORGE_URL)
    assert not is_sthoring_url(None)


def test_limit_and_offset_slice_printed_sesjoner() -> None:
    source = SthoringSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["2025-2026"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["2024-2025"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
