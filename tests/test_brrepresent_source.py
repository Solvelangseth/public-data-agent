from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.brrepresent import (
    LIST_URL,
    BrrepresentSource,
    brrepresent_table_id,
    cells_from_brrepresent,
    is_brrepresent_url,
    printed_item_url,
)

AAK_URL = "https://data.brreg.no/enhetsregisteret/api/roller/representanter/A-AK"
AREP_URL = "https://data.brreg.no/enhetsregisteret/api/roller/representanter/AREP"
AUTORISERT_URL = "https://data.brreg.no/enhetsregisteret/autorisert-api/roller/representanter/A-AK"
ENHETER_URL = "https://data.brreg.no/enhetsregisteret/api/enheter"
ORGFORM_URL = "https://data.brreg.no/enhetsregisteret/api/organisasjonsformer/AS"
KOMMUNER_URL = "https://data.brreg.no/enhetsregisteret/api/kommuner"
ROLLETYPER_URL = "https://data.brreg.no/enhetsregisteret/api/roller/rolletyper"
ROLLEGRUPPE_URL = "https://data.brreg.no/enhetsregisteret/api/roller/rollegruppetyper"
ROOT_URL = "https://data.brreg.no/enhetsregisteret/api"
FRIVILLIG_URL = "https://data.brreg.no/frivillighetsregisteret/enheter"
NORGES_BANK_URL = "https://data.norges-bank.no/api/agencyscheme?format=sdmx-json"
DATASET_ID = "brrepresent:A-AK"

CATALOG = {
    "_embedded": {
        "representanter": [
            {
                "kode": "A-AK",
                "beskrivelse": "Representant for A-aksjonærene",
                "_links": {"self": {"href": AUTORISERT_URL}},
            },
            {
                "kode": "AREP",
                "beskrivelse": "Representant for de ansatte",
                "_links": {
                    "self": {
                        "href": "https://data.brreg.no/enhetsregisteret/autorisert-api/roller/representanter/AREP"
                    }
                },
            },
            {
                "beskrivelse": "missing kode is skipped",
                "_links": {"self": {"href": "https://data.brreg.no/enhetsregisteret/api/roller/representanter/x"}},
            },
        ]
    }
}
ITEM_BODY = {
    "kode": "A-AK",
    "beskrivelse": "Representant for A-aksjonærene",
    "_links": {"self": {"href": AUTORISERT_URL}},
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
        if url == AAK_URL:
            return JsonResponse(status=200, url=url, body=ITEM_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"brrepresent fetch must GET, not POST {url}")


def test_printed_refs_copy_representant_kodes() -> None:
    source = BrrepresentSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["A-AK", "AREP"]
    assert [ref.source_native_uri for ref in refs] == [AAK_URL, AREP_URL]
    assert all("/autorisert-api/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/organisasjonsformer" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/kommuner" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/rolletyper" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_joins_printed_kode_onto_public_path() -> None:
    assert printed_item_url({"kode": "A-AK", "_links": {"self": {"href": AUTORISERT_URL}}}, LIST_URL) == AAK_URL
    assert printed_item_url({"kode": "A-AK"}, LIST_URL) == AAK_URL


def test_brrepresent_is_a_registered_source() -> None:
    assert "brrepresent" in SOURCE_IDS
    assert "brrolletype" in SOURCE_IDS
    assert "brrollegruppe" in SOURCE_IDS
    assert "brkommuner" in SOURCE_IDS
    assert "nguminer" in SOURCE_IDS
    assert "brroller" in SOURCE_IDS
    assert "brreg" in SOURCE_IDS
    assert "brorgform" in SOURCE_IDS
    assert "nbagency" in SOURCE_IDS
    assert "kvtopo" in SOURCE_IDS
    assert "nbdps" in SOURCE_IDS
    assert "vegwms" in SOURCE_IDS
    assert "fdkorg" in SOURCE_IDS
    assert "mdirgis" in SOURCE_IDS
    assert "ssbcorr" in SOURCE_IDS
    assert "bwgis" in SOURCE_IDS
    assert "broppdater" in SOURCE_IDS
    assert "kifylker" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("nbdps") + 1] == "vegwms"
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
    assert SOURCE_IDS[-1] == "brrepresent"
    source = build_source("brrepresent")
    assert isinstance(source, BrrepresentSource)
    assert source.source_id == "brrepresent"


def test_harvest_writes_printed_kode_and_null_license(tmp_path: Path) -> None:
    source = BrrepresentSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "brrepresent"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == AAK_URL
    assert row["title"] == "Representant for A-aksjonærene"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("brroller:")
    assert not str(row["id"]).startswith("brrolletype:")
    assert not str(row["id"]).startswith("brreg:")
    arep = registry.get_dataset("brrepresent:AREP")
    assert arep is not None
    assert arep["title"] == "Representant for de ansatte"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "A-AK"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["brrepresent_representant"]["kode"] == "A-AK"
    assert "_links" not in payload["brrepresent_representant"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_beskrivelse(tmp_path: Path) -> None:
    source = BrrepresentSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == AAK_URL
    assert result.table_id == "A-AK"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["Representant for A-aksjonærene"]
    assert all(row["measure"] == "beskrivelse" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["kode"] == "A-AK"
    assert "_links" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == AAK_URL for row in rows)
    registry.close()


def test_cells_copy_printed_representant() -> None:
    cells = cells_from_brrepresent(ITEM_BODY)
    assert cells == [("beskrivelse", "Representant for A-aksjonærene", {"kode": "A-AK"})]
    fallback = cells_from_brrepresent({"kode": "A-AK"})
    assert fallback == [("kode", "A-AK", {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_brrepresent(["A-AK"])
    with pytest.raises(ValueError, match="representant members"):
        cells_from_brrepresent({"_links": {"self": {"href": AUTORISERT_URL}}})


def test_is_brrepresent_url_accepts_only_representant_item_paths() -> None:
    assert is_brrepresent_url(AAK_URL)
    assert not is_brrepresent_url(LIST_URL)
    assert not is_brrepresent_url(AUTORISERT_URL)
    assert brrepresent_table_id(AAK_URL) == "A-AK"
    assert not is_brrepresent_url(ENHETER_URL)
    assert not is_brrepresent_url(ORGFORM_URL)
    assert not is_brrepresent_url(KOMMUNER_URL)
    assert not is_brrepresent_url(ROLLETYPER_URL)
    assert not is_brrepresent_url(ROLLEGRUPPE_URL)
    assert not is_brrepresent_url(ROOT_URL)
    assert not is_brrepresent_url(FRIVILLIG_URL)
    assert not is_brrepresent_url(NORGES_BANK_URL)
    assert not is_brrepresent_url("https://data.norge.no/datasets/x")
    assert not is_brrepresent_url(None)


def test_limit_and_offset_slice_printed_representanter() -> None:
    source = BrrepresentSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["A-AK"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["AREP"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
