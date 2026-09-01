from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.stperioder import (
    LIST_URL,
    StperioderSource,
    cells_from_stperioder,
    is_stperioder_url,
    printed_item_url,
    stperioder_table_id,
)

PERIOD_2025_URL = (
    "https://data.stortinget.no/eksport/representanter"
    "?stortingsperiodeid=2025-2029&format=json"
)
PERIOD_2021_URL = (
    "https://data.stortinget.no/eksport/representanter"
    "?stortingsperiodeid=2021-2025&format=json"
)
STORTINGET_PERIODER_URL = "https://data.stortinget.no/eksport/stortingsperioder?format=json"
STORTINGET_SESJONER_URL = "https://data.stortinget.no/eksport/sesjoner?format=json"
BRUNDER_URL = "https://data.brreg.no/enhetsregisteret/api/underenheter/933489272"
DATANORGE_URL = "https://data.norge.no/datasets/x"
DATASET_ID = "stperioder:2025-2029"

CATALOG = {
    "stortingsperioder_liste": [
        {"id": "2025-2029", "versjon": "1.6"},
        {"id": "2021-2025", "versjon": "1.6"},
        {"versjon": "missing id is skipped"},
    ]
}
ITEM_BODY = {
    "stortingsperiode_id": "2025-2029",
    "representanter_liste": [
        {
            "id": "AR",
            "fornavn": "Abid",
            "etternavn": "Raja",
            "kjoenn": "mann",
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
        if url == PERIOD_2025_URL:
            return JsonResponse(status=200, url=url, body=ITEM_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"stperioder fetch must GET, not POST {url}")


def test_printed_refs_copy_periode_id() -> None:
    source = StperioderSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["2025-2029", "2021-2025"]
    assert [ref.source_native_uri for ref in refs] == [PERIOD_2025_URL, PERIOD_2021_URL]
    assert all("/sesjoner" not in (ref.source_native_uri or "") for ref in refs)
    assert all("brreg" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_joins_printed_periode_id() -> None:
    assert printed_item_url({"id": "2025-2029"}, LIST_URL) == PERIOD_2025_URL


def test_stperioder_is_a_registered_source() -> None:
    assert "stperioder" in SOURCE_IDS
    assert "stortinget" in SOURCE_IDS
    assert "brunder" in SOURCE_IDS
    assert "brenheter" in SOURCE_IDS
    assert "ssbvar" in SOURCE_IDS
    assert "nordatlas" in SOURCE_IDS
    assert "datanorge" in SOURCE_IDS
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
    assert SOURCE_IDS[-1] == "dsbgis"
    source = build_source("stperioder")
    assert isinstance(source, StperioderSource)
    assert source.source_id == "stperioder"


def test_harvest_writes_printed_periode_id_and_null_license(tmp_path: Path) -> None:
    source = StperioderSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "stperioder"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == PERIOD_2025_URL
    assert row["title"] == "2025-2029"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("stortinget:")
    assert not str(row["id"]).startswith("brunder:")
    nxt = registry.get_dataset("stperioder:2021-2025")
    assert nxt is not None
    assert nxt["title"] == "2021-2025"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "2025-2029"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["stperioder_periode"]["id"] == "2025-2029"
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_fornavn(tmp_path: Path) -> None:
    source = StperioderSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == PERIOD_2025_URL
    assert result.table_id == "2025-2029"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["Abid"]
    assert all(row["measure"] == "fornavn" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["etternavn"] == "Raja"
    assert dims["id"] == "AR"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == PERIOD_2025_URL for row in rows)
    registry.close()


def test_cells_copy_printed_representanter() -> None:
    cells = cells_from_stperioder(ITEM_BODY)
    assert cells[0][0] == "fornavn"
    assert cells[0][1] == "Abid"
    assert cells[0][2]["etternavn"] == "Raja"
    fallback = cells_from_stperioder({"id": "2025-2029"})
    assert fallback == [("id", "2025-2029", {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_stperioder(["Abid"])
    with pytest.raises(ValueError, match="representant members"):
        cells_from_stperioder({"representanter_liste": [{"fylke": {"id": "Oslo"}}]})


def test_is_stperioder_url_accepts_only_representanter_periode_paths() -> None:
    assert is_stperioder_url(PERIOD_2025_URL)
    assert is_stperioder_url(PERIOD_2021_URL)
    assert stperioder_table_id(PERIOD_2025_URL) == "2025-2029"
    assert not is_stperioder_url(LIST_URL)
    assert not is_stperioder_url(STORTINGET_PERIODER_URL)
    assert not is_stperioder_url(STORTINGET_SESJONER_URL)
    assert not is_stperioder_url("https://data.stortinget.no/eksport/representanter")
    assert not is_stperioder_url(BRUNDER_URL)
    assert not is_stperioder_url(DATANORGE_URL)
    assert not is_stperioder_url(None)


def test_limit_and_offset_slice_printed_perioder() -> None:
    source = StperioderSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["2025-2029"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["2021-2025"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
