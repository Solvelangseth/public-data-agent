from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.brrolletype import (
    LIST_URL,
    BrrolletypeSource,
    brrolletype_table_id,
    cells_from_brrolletype,
    is_brrolletype_url,
    printed_item_url,
)

ADOS_URL = "https://data.brreg.no/enhetsregisteret/api/roller/rolletyper/ADOS"
DAGL_URL = "https://data.brreg.no/enhetsregisteret/api/roller/rolletyper/DAGL"
AUTORISERT_URL = "https://data.brreg.no/enhetsregisteret/autorisert-api/roller/rolletyper/ADOS"
ENHETER_URL = "https://data.brreg.no/enhetsregisteret/api/enheter"
ORGFORM_URL = "https://data.brreg.no/enhetsregisteret/api/organisasjonsformer/AS"
KOMMUNER_URL = "https://data.brreg.no/enhetsregisteret/api/kommuner"
REPRESENTANTER_URL = "https://data.brreg.no/enhetsregisteret/api/roller/representanter"
ROOT_URL = "https://data.brreg.no/enhetsregisteret/api"
FRIVILLIG_URL = "https://data.brreg.no/frivillighetsregisteret/enheter"
NORGES_BANK_URL = "https://data.norges-bank.no/api/agencyscheme?format=sdmx-json"
DATASET_ID = "brrolletype:ADOS"

CATALOG = {
    "_embedded": {
        "rolletyper": [
            {
                "kode": "ADOS",
                "beskrivelse": "Administrativ enhet - offentlig sektor",
                "_links": {"self": {"href": AUTORISERT_URL}},
            },
            {
                "kode": "DAGL",
                "beskrivelse": "Daglig leder",
                "_links": {
                    "self": {
                        "href": "https://data.brreg.no/enhetsregisteret/autorisert-api/roller/rolletyper/DAGL"
                    }
                },
            },
            {
                "beskrivelse": "missing kode is skipped",
                "_links": {"self": {"href": "https://data.brreg.no/enhetsregisteret/api/roller/rolletyper/x"}},
            },
        ]
    }
}
ITEM_BODY = {
    "kode": "ADOS",
    "beskrivelse": "Administrativ enhet - offentlig sektor",
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
        if url == ADOS_URL:
            return JsonResponse(status=200, url=url, body=ITEM_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"brrolletype fetch must GET, not POST {url}")


def test_printed_refs_copy_rolletype_kodes() -> None:
    source = BrrolletypeSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["ADOS", "DAGL"]
    assert [ref.source_native_uri for ref in refs] == [ADOS_URL, DAGL_URL]
    assert all("/autorisert-api/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/organisasjonsformer" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/kommuner" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_joins_printed_kode_onto_public_path() -> None:
    assert printed_item_url({"kode": "ADOS", "_links": {"self": {"href": AUTORISERT_URL}}}, LIST_URL) == ADOS_URL
    assert printed_item_url({"kode": "ADOS"}, LIST_URL) == ADOS_URL


def test_brrolletype_is_a_registered_source() -> None:
    assert "brrolletype" in SOURCE_IDS
    assert "brroller" in SOURCE_IDS
    assert "brreg" in SOURCE_IDS
    assert "brorgform" in SOURCE_IDS
    assert "nbagency" in SOURCE_IDS
    assert "kvtopo" in SOURCE_IDS
    assert "nbdps" in SOURCE_IDS
    assert "vegwms" in SOURCE_IDS
    assert "fdkorg" in SOURCE_IDS
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
    assert SOURCE_IDS[SOURCE_IDS.index("dsbgis") + 1] == "nibiogard"
    assert SOURCE_IDS[SOURCE_IDS.index("nibiogard") + 1] == "stskrift"
    assert SOURCE_IDS[SOURCE_IDS.index("stskrift") + 1] == "ssbtett"
    assert SOURCE_IDS[-1] == "ssbtett"
    source = build_source("brrolletype")
    assert isinstance(source, BrrolletypeSource)
    assert source.source_id == "brrolletype"


def test_harvest_writes_printed_kode_and_null_license(tmp_path: Path) -> None:
    source = BrrolletypeSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "brrolletype"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == ADOS_URL
    assert row["title"] == "Administrativ enhet - offentlig sektor"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("brroller:")
    assert not str(row["id"]).startswith("brreg:")
    dagl = registry.get_dataset("brrolletype:DAGL")
    assert dagl is not None
    assert dagl["title"] == "Daglig leder"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "ADOS"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["brrolletype_rolletype"]["kode"] == "ADOS"
    assert "_links" not in payload["brrolletype_rolletype"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_beskrivelse(tmp_path: Path) -> None:
    source = BrrolletypeSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == ADOS_URL
    assert result.table_id == "ADOS"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["Administrativ enhet - offentlig sektor"]
    assert all(row["measure"] == "beskrivelse" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["kode"] == "ADOS"
    assert "_links" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == ADOS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_rolletype() -> None:
    cells = cells_from_brrolletype(ITEM_BODY)
    assert cells == [("beskrivelse", "Administrativ enhet - offentlig sektor", {"kode": "ADOS"})]
    fallback = cells_from_brrolletype({"kode": "ADOS"})
    assert fallback == [("kode", "ADOS", {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_brrolletype(["ADOS"])
    with pytest.raises(ValueError, match="rolletype members"):
        cells_from_brrolletype({"_links": {"self": {"href": AUTORISERT_URL}}})


def test_is_brrolletype_url_accepts_only_rolletype_item_paths() -> None:
    assert is_brrolletype_url(ADOS_URL)
    assert not is_brrolletype_url(LIST_URL)
    assert not is_brrolletype_url(AUTORISERT_URL)
    assert brrolletype_table_id(ADOS_URL) == "ADOS"
    assert not is_brrolletype_url(ENHETER_URL)
    assert not is_brrolletype_url(ORGFORM_URL)
    assert not is_brrolletype_url(KOMMUNER_URL)
    assert not is_brrolletype_url(REPRESENTANTER_URL)
    assert not is_brrolletype_url(ROOT_URL)
    assert not is_brrolletype_url(FRIVILLIG_URL)
    assert not is_brrolletype_url(NORGES_BANK_URL)
    assert not is_brrolletype_url("https://data.norge.no/datasets/x")
    assert not is_brrolletype_url(None)


def test_limit_and_offset_slice_printed_rolletyper() -> None:
    source = BrrolletypeSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["ADOS"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["DAGL"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
