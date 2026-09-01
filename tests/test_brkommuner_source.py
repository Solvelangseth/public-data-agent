from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.brkommuner import (
    LIST_URL,
    BrkommunerSource,
    brkommuner_table_id,
    cells_from_brkommuner,
    is_brkommuner_url,
    printed_item_url,
)

OSLO_URL = "https://data.brreg.no/enhetsregisteret/api/kommuner/0301"
EIGERSUND_URL = "https://data.brreg.no/enhetsregisteret/api/kommuner/1101"
ORGFORM_URL = "https://data.brreg.no/enhetsregisteret/api/organisasjonsformer/AS"
ENHETER_URL = "https://data.brreg.no/enhetsregisteret/api/enheter"
ROLLER_URL = "https://data.brreg.no/enhetsregisteret/api/roller/representanter"
ROOT_URL = "https://data.brreg.no/enhetsregisteret/api"
FRIVILLIG_URL = "https://data.brreg.no/frivillighetsregisteret/enheter"
KOMMUNEINFO_URL = "https://ws.geonorge.no/kommuneinfo/v1/kommuner"
NORGES_BANK_URL = "https://data.norges-bank.no/api/agencyscheme?format=sdmx-json"
DATASET_ID = "brkommuner:0301"

CATALOG = {
    "_embedded": {
        "kommuner": [
            {
                "nummer": "0301",
                "navn": "OSLO",
                "_links": {"self": {"href": OSLO_URL}},
            },
            {
                "nummer": "1101",
                "navn": "EIGERSUND",
                "_links": {"self": {"href": EIGERSUND_URL}},
            },
            {
                "navn": "missing nummer is skipped",
                "_links": {"self": {"href": "https://data.brreg.no/enhetsregisteret/api/kommuner/x"}},
            },
        ]
    }
}
ITEM_BODY = {
    "nummer": "0301",
    "navn": "OSLO",
    "_links": {"self": {"href": OSLO_URL}},
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
        if url == OSLO_URL:
            return JsonResponse(status=200, url=url, body=ITEM_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"brkommuner fetch must GET, not POST {url}")


def test_printed_refs_copy_kommune_numre() -> None:
    source = BrkommunerSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["0301", "1101"]
    assert [ref.source_native_uri for ref in refs] == [OSLO_URL, EIGERSUND_URL]
    assert all("/organisasjonsformer" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/enheter" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/roller" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_copies_printed_self_href() -> None:
    assert printed_item_url({"nummer": "0301", "_links": {"self": {"href": OSLO_URL}}}, LIST_URL) == (
        OSLO_URL
    )
    assert printed_item_url({"nummer": "0301"}, LIST_URL) == OSLO_URL


def test_brkommuner_is_a_registered_source() -> None:
    assert "brkommuner" in SOURCE_IDS
    assert "brreg" in SOURCE_IDS
    assert "brorgform" in SOURCE_IDS
    assert "brroller" in SOURCE_IDS
    assert "kommuneinfo" in SOURCE_IDS
    assert "frivillig" in SOURCE_IDS
    assert "ssbver" in SOURCE_IDS
    assert "hiwms" in SOURCE_IDS
    assert "nbagency" in SOURCE_IDS
    assert "kvtopo" in SOURCE_IDS
    assert "nbdps" in SOURCE_IDS
    assert "vegwms" in SOURCE_IDS
    assert "fdkorg" in SOURCE_IDS
    assert "brrolletype" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("vegwms") + 1] == "fdkorg"
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
    assert SOURCE_IDS[SOURCE_IDS.index("brunder") + 1] == "kikommuner"
    assert SOURCE_IDS[SOURCE_IDS.index("kikommuner") + 1] == "fbgis"
    assert SOURCE_IDS[-1] == "fbgis"
    source = build_source("brkommuner")
    assert isinstance(source, BrkommunerSource)
    assert source.source_id == "brkommuner"


def test_harvest_writes_printed_nummer_and_null_license(tmp_path: Path) -> None:
    source = BrkommunerSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "brkommuner"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == OSLO_URL
    assert row["title"] == "OSLO"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("brreg:")
    assert not str(row["id"]).startswith("brorgform:")
    assert not str(row["id"]).startswith("kommuneinfo:")
    eigersund = registry.get_dataset("brkommuner:1101")
    assert eigersund is not None
    assert eigersund["title"] == "EIGERSUND"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "0301"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["brkommuner_kommune"]["nummer"] == "0301"
    assert "_links" not in payload["brkommuner_kommune"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_navn(tmp_path: Path) -> None:
    source = BrkommunerSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == OSLO_URL
    assert result.table_id == "0301"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["OSLO"]
    assert all(row["measure"] == "navn" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["nummer"] == "0301"
    assert "_links" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == OSLO_URL for row in rows)
    registry.close()


def test_cells_copy_printed_kommune() -> None:
    cells = cells_from_brkommuner(ITEM_BODY)
    assert cells == [("navn", "OSLO", {"nummer": "0301"})]
    fallback = cells_from_brkommuner({"nummer": "0301"})
    assert fallback == [("nummer", "0301", {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_brkommuner(["OSLO"])
    with pytest.raises(ValueError, match="kommune members"):
        cells_from_brkommuner({"_links": {"self": {"href": OSLO_URL}}})


def test_is_brkommuner_url_accepts_only_kommune_item_paths() -> None:
    assert is_brkommuner_url(OSLO_URL)
    assert not is_brkommuner_url(LIST_URL)
    assert brkommuner_table_id(OSLO_URL) == "0301"
    assert not is_brkommuner_url(ORGFORM_URL)
    assert not is_brkommuner_url(ENHETER_URL)
    assert not is_brkommuner_url(ROLLER_URL)
    assert not is_brkommuner_url(ROOT_URL)
    assert not is_brkommuner_url(FRIVILLIG_URL)
    assert not is_brkommuner_url(KOMMUNEINFO_URL)
    assert not is_brkommuner_url(NORGES_BANK_URL)
    assert not is_brkommuner_url("https://data.norge.no/datasets/x")
    assert not is_brkommuner_url(None)


def test_limit_and_offset_slice_printed_kommuner() -> None:
    source = BrkommunerSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["0301"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["1101"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
