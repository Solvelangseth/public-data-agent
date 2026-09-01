from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.brenheter import (
    LIST_URL,
    BrenheterSource,
    brenheter_table_id,
    cells_from_brenheter,
    is_brenheter_url,
    printed_item_url,
)

PALMERA_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/916627939"
ZOTKO_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/933365573"
ORGFORM_URL = "https://data.brreg.no/enhetsregisteret/api/organisasjonsformer/AS"
KOMMUNE_URL = "https://data.brreg.no/enhetsregisteret/api/kommuner/0301"
ROLLER_URL = "https://data.brreg.no/enhetsregisteret/api/roller/representanter"
ROOT_URL = "https://data.brreg.no/enhetsregisteret/api"
LASTNED_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/lastned"
ROLLER_ITEM_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/916627939/roller"
ORGFORM_ENHETER_URL = "https://data.brreg.no/enhetsregisteret/api/organisasjonsformer/enheter"
FRIVILLIG_URL = "https://data.brreg.no/frivillighetsregisteret/enheter"
NORGES_BANK_URL = "https://data.norges-bank.no/api/agencyscheme?format=sdmx-json"
DATASET_ID = "brenheter:916627939"

CATALOG = {
    "_embedded": {
        "enheter": [
            {
                "organisasjonsnummer": "916627939",
                "navn": "- P A L M E R A -",
                "_links": {"self": {"href": PALMERA_URL}},
            },
            {
                "organisasjonsnummer": "933365573",
                "navn": "- ZOTKO .NO",
                "_links": {"self": {"href": ZOTKO_URL}},
            },
            {
                "navn": "missing organisasjonsnummer is skipped",
                "_links": {"self": {"href": "https://data.brreg.no/enhetsregisteret/api/enheter/x"}},
            },
        ]
    }
}
ITEM_BODY = {
    "organisasjonsnummer": "916627939",
    "navn": "- P A L M E R A -",
    "_links": {"self": {"href": PALMERA_URL}},
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
        if url == PALMERA_URL:
            return JsonResponse(status=200, url=url, body=ITEM_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"brenheter fetch must GET, not POST {url}")


def test_printed_refs_copy_organisasjonsnummer() -> None:
    source = BrenheterSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["916627939", "933365573"]
    assert [ref.source_native_uri for ref in refs] == [PALMERA_URL, ZOTKO_URL]
    assert all("/organisasjonsformer" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/kommuner" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/roller" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_copies_printed_self_href() -> None:
    assert printed_item_url(
        {"organisasjonsnummer": "916627939", "_links": {"self": {"href": PALMERA_URL}}},
        LIST_URL,
    ) == PALMERA_URL
    assert printed_item_url({"organisasjonsnummer": "916627939"}, LIST_URL) == PALMERA_URL


def test_brenheter_is_a_registered_source() -> None:
    assert "brenheter" in SOURCE_IDS
    assert "brunder" in SOURCE_IDS
    assert "brreg" in SOURCE_IDS
    assert "brorgform" in SOURCE_IDS
    assert "brkommuner" in SOURCE_IDS
    assert "brroller" in SOURCE_IDS
    assert "brrolletype" in SOURCE_IDS
    assert "brrollegruppe" in SOURCE_IDS
    assert "frivillig" in SOURCE_IDS
    assert "ssbcorr" in SOURCE_IDS
    assert "mdirgis" in SOURCE_IDS
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
    assert SOURCE_IDS[SOURCE_IDS.index("fbgis") + 1] == "stperioder"
    assert SOURCE_IDS[SOURCE_IDS.index("stperioder") + 1] == "nibioar50"
    assert SOURCE_IDS[SOURCE_IDS.index("nibioar50") + 1] == "brorgformen"
    assert SOURCE_IDS[SOURCE_IDS.index("brorgformen") + 1] == "crinst"
    assert SOURCE_IDS[SOURCE_IDS.index("crinst") + 1] == "stsaker"
    assert SOURCE_IDS[SOURCE_IDS.index("stsaker") + 1] == "ssbsubj"
    assert SOURCE_IDS[-1] == "ssbsubj"
    source = build_source("brenheter")
    assert isinstance(source, BrenheterSource)
    assert source.source_id == "brenheter"


def test_harvest_writes_printed_organisasjonsnummer_and_null_license(tmp_path: Path) -> None:
    source = BrenheterSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "brenheter"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == PALMERA_URL
    assert row["title"] == "- P A L M E R A -"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("brreg:")
    assert not str(row["id"]).startswith("brorgform:")
    assert not str(row["id"]).startswith("brkommuner:")
    zotko = registry.get_dataset("brenheter:933365573")
    assert zotko is not None
    assert zotko["title"] == "- ZOTKO .NO"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "916627939"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["brenheter_enhet"]["organisasjonsnummer"] == "916627939"
    assert "_links" not in payload["brenheter_enhet"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_navn(tmp_path: Path) -> None:
    source = BrenheterSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == PALMERA_URL
    assert result.table_id == "916627939"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["- P A L M E R A -"]
    assert all(row["measure"] == "navn" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["organisasjonsnummer"] == "916627939"
    assert "_links" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == PALMERA_URL for row in rows)
    registry.close()


def test_cells_copy_printed_enhet() -> None:
    cells = cells_from_brenheter(ITEM_BODY)
    assert cells == [("navn", "- P A L M E R A -", {"organisasjonsnummer": "916627939"})]
    fallback = cells_from_brenheter({"organisasjonsnummer": "916627939"})
    assert fallback == [("organisasjonsnummer", "916627939", {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_brenheter(["- P A L M E R A -"])
    with pytest.raises(ValueError, match="enhet members"):
        cells_from_brenheter({"_links": {"self": {"href": PALMERA_URL}}})


def test_is_brenheter_url_accepts_only_enhet_item_paths() -> None:
    assert is_brenheter_url(PALMERA_URL)
    assert is_brenheter_url(ZOTKO_URL)
    assert not is_brenheter_url(LIST_URL)
    assert brenheter_table_id(PALMERA_URL) == "916627939"
    assert not is_brenheter_url(ORGFORM_URL)
    assert not is_brenheter_url(KOMMUNE_URL)
    assert not is_brenheter_url(ROLLER_URL)
    assert not is_brenheter_url(ROOT_URL)
    assert not is_brenheter_url(LASTNED_URL)
    assert not is_brenheter_url(ROLLER_ITEM_URL)
    assert not is_brenheter_url(ORGFORM_ENHETER_URL)
    assert not is_brenheter_url(FRIVILLIG_URL)
    assert not is_brenheter_url(NORGES_BANK_URL)
    assert not is_brenheter_url("https://data.norge.no/datasets/x")
    assert not is_brenheter_url(None)


def test_limit_and_offset_slice_printed_enheter() -> None:
    source = BrenheterSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["916627939"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["933365573"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
