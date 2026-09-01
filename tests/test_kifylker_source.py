from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.kifylker import (
    LIST_URL,
    KifylkerSource,
    cells_from_kifylker,
    is_kifylker_url,
    kifylker_table_id,
    printed_item_url,
)

TROMS_URL = "https://api.kartverket.no/kommuneinfo/v1/fylker/55"
FINNMARK_URL = "https://api.kartverket.no/kommuneinfo/v1/fylker/56"
KOMMUNEINFO_FYLKER_URL = "https://api.kartverket.no/kommuneinfo/v1/fylker"
KOMMUNEINFO_KOMMUNER_URL = "https://api.kartverket.no/kommuneinfo/v1/kommuner"
BRREG_URL = "https://data.brreg.no/enhetsregisteret/api/kommuner/0301"
DATANORGE_URL = "https://data.norge.no/datasets/x"
NORGES_BANK_URL = "https://data.norges-bank.no/api/agencyscheme?format=sdmx-json"
DATASET_ID = "kifylker:55"

CATALOG = [
    {
        "fylkesnavn": "Troms",
        "fylkesnummer": "55",
    },
    {
        "fylkesnavn": "Finnmark",
        "fylkesnummer": "56",
    },
    {
        "fylkesnavn": "missing fylkesnummer is skipped",
    },
]
ITEM_BODY = {
    "fylkesnavn": "Troms",
    "fylkesnummer": "55",
    "avgrensningsboks": {"type": "Polygon", "coordinates": []},
    "kommuner": [{"kommunenummer": "5501", "kommunenavn": "Tromsø"}],
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
        if url == TROMS_URL:
            return JsonResponse(status=200, url=url, body=ITEM_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"kifylker fetch must GET, not POST {url}")


def test_printed_refs_copy_fylkesnummer() -> None:
    source = KifylkerSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["55", "56"]
    assert [ref.source_native_uri for ref in refs] == [TROMS_URL, FINNMARK_URL]
    assert all("data.brreg.no" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/kommuner" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_joins_printed_fylkesnummer() -> None:
    assert printed_item_url({"fylkesnummer": "55"}, LIST_URL) == TROMS_URL


def test_kifylker_is_a_registered_source() -> None:
    assert "kifylker" in SOURCE_IDS
    assert "kommuneinfo" in SOURCE_IDS
    assert "fdkorg" in SOURCE_IDS
    assert "datanorge" in SOURCE_IDS
    assert "brreg" in SOURCE_IDS
    assert "nbagency" in SOURCE_IDS
    assert "nbdps" in SOURCE_IDS
    assert "vegwms" in SOURCE_IDS
    assert "brrolletype" in SOURCE_IDS
    assert "brkommuner" in SOURCE_IDS
    assert "nguminer" in SOURCE_IDS
    assert "brrollegruppe" in SOURCE_IDS
    assert "mdirgis" in SOURCE_IDS
    assert "ssbcorr" in SOURCE_IDS
    assert "bwgis" in SOURCE_IDS
    assert "broppdater" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("fdkorg") + 1] == "brrolletype"
    assert SOURCE_IDS[SOURCE_IDS.index("brrolletype") + 1] == "brkommuner"
    assert SOURCE_IDS[SOURCE_IDS.index("brkommuner") + 1] == "nguminer"
    assert SOURCE_IDS[SOURCE_IDS.index("nguminer") + 1] == "brrollegruppe"
    assert SOURCE_IDS[SOURCE_IDS.index("brrollegruppe") + 1] == "mdirgis"
    assert SOURCE_IDS[SOURCE_IDS.index("mdirgis") + 1] == "ssbcorr"
    assert SOURCE_IDS[SOURCE_IDS.index("ssbcorr") + 1] == "bwgis"
    assert SOURCE_IDS[SOURCE_IDS.index("bwgis") + 1] == "broppdater"
    assert SOURCE_IDS[SOURCE_IDS.index("broppdater") + 1] == "kifylker"
    assert SOURCE_IDS[SOURCE_IDS.index("kifylker") + 1] == "brrepresent"
    assert SOURCE_IDS[SOURCE_IDS.index("brrepresent") + 1] == "brenheter"
    assert SOURCE_IDS[SOURCE_IDS.index("brenheter") + 1] == "ssbvar"
    assert SOURCE_IDS[SOURCE_IDS.index("ssbvar") + 1] == "nordatlas"
    assert SOURCE_IDS[SOURCE_IDS.index("nordatlas") + 1] == "brunder"
    assert SOURCE_IDS[-1] == "brunder"
    source = build_source("kifylker")
    assert isinstance(source, KifylkerSource)
    assert source.source_id == "kifylker"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = KifylkerSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "kifylker"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == TROMS_URL
    assert row["title"] == "Troms"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("kommuneinfo:")
    assert not str(row["id"]).startswith("brreg:")
    nxt = registry.get_dataset("kifylker:56")
    assert nxt is not None
    assert nxt["title"] == "Finnmark"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "55"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["kifylker_fylke"]["fylkesnummer"] == "55"
    assert "avgrensningsboks" not in payload["kifylker_fylke"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_fylkesnavn(tmp_path: Path) -> None:
    source = KifylkerSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == TROMS_URL
    assert result.table_id == "55"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["Troms"]
    assert all(row["measure"] == "fylkesnavn" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["fylkesnummer"] == "55"
    assert "avgrensningsboks" not in dims
    assert "kommuner" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == TROMS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_fylke() -> None:
    cells = cells_from_kifylker(ITEM_BODY)
    assert cells[0][0] == "fylkesnavn"
    assert cells[0][1] == "Troms"
    assert cells[0][2]["fylkesnummer"] == "55"
    assert "avgrensningsboks" not in cells[0][2]
    assert "kommuner" not in cells[0][2]
    fallback = cells_from_kifylker({"fylkesnummer": "55"})
    assert fallback == [("fylkesnummer", "55", {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_kifylker(["Troms"])
    with pytest.raises(ValueError, match="fylke members"):
        cells_from_kifylker({"avgrensningsboks": {"type": "Polygon"}})


def test_is_kifylker_url_accepts_only_fylke_item_paths() -> None:
    assert is_kifylker_url(TROMS_URL)
    assert not is_kifylker_url(LIST_URL)
    assert not is_kifylker_url(KOMMUNEINFO_FYLKER_URL)
    assert not is_kifylker_url(KOMMUNEINFO_KOMMUNER_URL)
    assert not is_kifylker_url(TROMS_URL + "/omrade")
    assert kifylker_table_id(TROMS_URL) == "55"
    assert not is_kifylker_url(BRREG_URL)
    assert not is_kifylker_url(DATANORGE_URL)
    assert not is_kifylker_url(NORGES_BANK_URL)
    assert not is_kifylker_url(None)


def test_limit_and_offset_slice_printed_fylker() -> None:
    source = KifylkerSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["55"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["56"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
