from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.kikommuner import (
    LIST_URL,
    KikommunerSource,
    cells_from_kikommuner,
    is_kikommuner_url,
    kikommuner_table_id,
    printed_item_url,
)

VALER_URL = "https://api.kartverket.no/kommuneinfo/v1/kommuner/3419"
HEMSEDAL_URL = "https://api.kartverket.no/kommuneinfo/v1/kommuner/3326"
KOMMUNEINFO_KOMMUNER_URL = "https://api.kartverket.no/kommuneinfo/v1/kommuner"
KOMMUNEINFO_FYLKER_URL = "https://api.kartverket.no/kommuneinfo/v1/fylker"
KIFYLKER_URL = "https://api.kartverket.no/kommuneinfo/v1/fylker/55"
ILLUSTRASJON_URL = "https://api.kartverket.no/kommuneinfo/v1/kommuner/illustrasjonskart"
OMRADE_URL = VALER_URL + "/omrade"
BRREG_URL = "https://data.brreg.no/enhetsregisteret/api/kommuner/0301"
DATANORGE_URL = "https://data.norge.no/datasets/x"
NORGES_BANK_URL = "https://data.norges-bank.no/api/agencyscheme?format=sdmx-json"
DATASET_ID = "kikommuner:3419"

CATALOG = [
    {
        "kommunenavn": "Våler",
        "kommunenavnNorsk": "Våler",
        "kommunenummer": "3419",
    },
    {
        "kommunenavn": "Hemsedal",
        "kommunenavnNorsk": "Hemsedal",
        "kommunenummer": "3326",
    },
    {
        "kommunenavn": "missing kommunenummer is skipped",
    },
]
ITEM_BODY = {
    "kommunenavn": "Våler",
    "kommunenavnNorsk": "Våler",
    "kommunenummer": "3419",
    "fylkesnavn": "Innlandet",
    "fylkesnummer": "34",
    "samiskForvaltningsomrade": False,
    "avgrensningsboks": {"type": "Polygon", "coordinates": []},
    "gyldigeNavn": [{"navn": "Våler", "prioritet": 1, "sprak": "Norwegian"}],
    "punktIOmrade": {"type": "Point", "coordinates": [12.0, 60.8]},
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
        if url == VALER_URL:
            return JsonResponse(status=200, url=url, body=ITEM_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"kikommuner fetch must GET, not POST {url}")


def test_printed_refs_copy_kommunenummer() -> None:
    source = KikommunerSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["3419", "3326"]
    assert [ref.source_native_uri for ref in refs] == [VALER_URL, HEMSEDAL_URL]
    assert all("data.brreg.no" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/fylker" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_joins_printed_kommunenummer() -> None:
    assert printed_item_url({"kommunenummer": "3419"}, LIST_URL) == VALER_URL


def test_kikommuner_is_a_registered_source() -> None:
    assert "kikommuner" in SOURCE_IDS
    assert "kifylker" in SOURCE_IDS
    assert "kommuneinfo" in SOURCE_IDS
    assert "brkommuner" in SOURCE_IDS
    assert "brenheter" in SOURCE_IDS
    assert "brrepresent" in SOURCE_IDS
    assert "ssbvar" in SOURCE_IDS
    assert "nordatlas" in SOURCE_IDS
    assert "brunder" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("broppdater") + 1] == "kifylker"
    assert SOURCE_IDS[SOURCE_IDS.index("kifylker") + 1] == "brrepresent"
    assert SOURCE_IDS[SOURCE_IDS.index("brrepresent") + 1] == "brenheter"
    assert SOURCE_IDS[SOURCE_IDS.index("brenheter") + 1] == "ssbvar"
    assert SOURCE_IDS[SOURCE_IDS.index("ssbvar") + 1] == "nordatlas"
    assert SOURCE_IDS[SOURCE_IDS.index("nordatlas") + 1] == "brunder"
    assert SOURCE_IDS[SOURCE_IDS.index("brunder") + 1] == "kikommuner"
    assert SOURCE_IDS[SOURCE_IDS.index("kikommuner") + 1] == "fbgis"
    assert SOURCE_IDS[SOURCE_IDS.index("fbgis") + 1] == "stperioder"
    assert SOURCE_IDS[SOURCE_IDS.index("stperioder") + 1] == "nibioar50"
    assert SOURCE_IDS[SOURCE_IDS.index("nibioar50") + 1] == "brorgformen"
    assert SOURCE_IDS[-1] == "brorgformen"
    source = build_source("kikommuner")
    assert isinstance(source, KikommunerSource)
    assert source.source_id == "kikommuner"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = KikommunerSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "kikommuner"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == VALER_URL
    assert row["title"] == "Våler"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("kommuneinfo:")
    assert not str(row["id"]).startswith("kifylker:")
    assert not str(row["id"]).startswith("brkommuner:")
    nxt = registry.get_dataset("kikommuner:3326")
    assert nxt is not None
    assert nxt["title"] == "Hemsedal"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "3419"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["kikommuner_kommune"]["kommunenummer"] == "3419"
    assert "avgrensningsboks" not in payload["kikommuner_kommune"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_kommunenavn(tmp_path: Path) -> None:
    source = KikommunerSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == VALER_URL
    assert result.table_id == "3419"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["Våler"]
    assert all(row["measure"] == "kommunenavnNorsk" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["kommunenummer"] == "3419"
    assert "avgrensningsboks" not in dims
    assert "gyldigeNavn" not in dims
    assert "punktIOmrade" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == VALER_URL for row in rows)
    registry.close()


def test_cells_copy_printed_kommune() -> None:
    cells = cells_from_kikommuner(ITEM_BODY)
    assert cells[0][0] == "kommunenavnNorsk"
    assert cells[0][1] == "Våler"
    assert cells[0][2]["kommunenummer"] == "3419"
    assert "avgrensningsboks" not in cells[0][2]
    assert "gyldigeNavn" not in cells[0][2]
    assert "punktIOmrade" not in cells[0][2]
    fallback = cells_from_kikommuner({"kommunenummer": "3419"})
    assert fallback == [("kommunenummer", "3419", {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_kikommuner(["Våler"])
    with pytest.raises(ValueError, match="kommune members"):
        cells_from_kikommuner({"avgrensningsboks": {"type": "Polygon"}})


def test_is_kikommuner_url_accepts_only_kommune_item_paths() -> None:
    assert is_kikommuner_url(VALER_URL)
    assert is_kikommuner_url(HEMSEDAL_URL)
    assert not is_kikommuner_url(LIST_URL)
    assert not is_kikommuner_url(KOMMUNEINFO_KOMMUNER_URL)
    assert not is_kikommuner_url(KOMMUNEINFO_FYLKER_URL)
    assert not is_kikommuner_url(KIFYLKER_URL)
    assert not is_kikommuner_url(ILLUSTRASJON_URL)
    assert not is_kikommuner_url(OMRADE_URL)
    assert kikommuner_table_id(VALER_URL) == "3419"
    assert not is_kikommuner_url(BRREG_URL)
    assert not is_kikommuner_url(DATANORGE_URL)
    assert not is_kikommuner_url(NORGES_BANK_URL)
    assert not is_kikommuner_url(None)


def test_limit_and_offset_slice_printed_kommuner() -> None:
    source = KikommunerSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["3419"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["3326"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
