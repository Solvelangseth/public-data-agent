from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import SelectionTooLarge, classify_access_path, fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.brenheter import (
    LIST_URL,
    ORGNR_SCHEME,
    BrenheterSource,
    brenheter_table_id,
    cells_from_brenheter,
    entity_from_enhet,
    is_brenheter_collection_url,
    is_brenheter_url,
    printed_item_url,
    shape_from_brenheter,
    valid_orgnr,
)

PALMERA_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/916627939"
ZOTKO_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/933365573"
EQUINOR_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/923609016"
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
    "organisasjonsform": {"kode": "FLI", "beskrivelse": "Forening/lag/innretning"},
    "registreringsdatoEnhetsregisteret": "2016-01-02",
    "konkurs": False,
    "_links": {"self": {"href": PALMERA_URL}},
}
ZOTKO_BODY = {
    "organisasjonsnummer": "933365573",
    "navn": "- ZOTKO .NO",
    "_links": {"self": {"href": ZOTKO_URL}},
}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == LIST_URL:
            return CATALOG
        if url == PALMERA_URL:
            return ITEM_BODY
        if url == ZOTKO_URL:
            return ZOTKO_BODY
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        self.gets.append(url)
        if url == PALMERA_URL:
            return JsonResponse(status=200, url=url, body=ITEM_BODY)
        if url == EQUINOR_URL:
            return JsonResponse(
                status=200,
                url=url,
                body={
                    "organisasjonsnummer": "923609016",
                    "navn": "EQUINOR ASA",
                    "organisasjonsform": {"kode": "ASA", "beskrivelse": "Allmennaksjeselskap"},
                    "antallAnsatte": 21000,
                },
            )
        if url.endswith("/123456789"):
            return JsonResponse(status=404, url=url, body={"error": "not found"})
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
    assert SOURCE_IDS[-1] == "stskrift"
    source = build_source("brenheter")
    assert isinstance(source, BrenheterSource)
    assert source.source_id == "brenheter"


def test_harvest_gets_printed_enhet_by_orgnr_and_null_license(tmp_path: Path) -> None:
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
    assert payload["brenheter_enhet"]["organisasjonsform"]["kode"] == "FLI"
    assert "_links" not in payload["brenheter_enhet"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_stores_entity_record_and_fills_resource_index(tmp_path: Path) -> None:
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
    assert result.counts.inserted == 1
    rows = registry.list_records(DATASET_ID)
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "entity"
    assert row["subject_scheme"] == ORGNR_SCHEME
    assert row["subject_code"] == "916627939"
    assert row["subject_label"] == "- P A L M E R A -"
    assert row["measure"] is None
    assert row["value_num"] is None
    assert row["license"] is None
    attrs = json.loads(row["attributes_json"])
    assert attrs["organisasjonsform"] == "FLI"
    assert attrs["organisasjonsform_beskrivelse"] == "Forening/lag/innretning"
    assert attrs["konkurs"] is False
    assert "_links" not in attrs
    # Observations stay empty: companies are not measures.
    assert registry.list_observations(DATASET_ID) == []
    cap = registry.get_capability(DATASET_ID)
    assert cap is not None
    assert cap["capability"] == "entities"
    assert cap["record_kind"] == "entity"
    assert cap["endpoint"] == PALMERA_URL
    assert cap["request_method"] == "GET"
    assert cap["verified_sample_count"] == 1
    assert cap["verified_at"]
    fields = {f["field_code"]: f for f in registry.resource_fields(DATASET_ID)}
    assert fields["organisasjonsnummer"]["field_role"] == "key"
    keys = registry.datasets_with_key(ORGNR_SCHEME)
    assert any(k["dataset_id"] == DATASET_ID for k in keys)
    assert classify_access_path(PALMERA_URL)["kind"] == "entities"
    registry.close()


def test_cells_copy_printed_enhet() -> None:
    cells = cells_from_brenheter(ITEM_BODY)
    assert cells[0][0] == "navn"
    assert cells[0][1] == "- P A L M E R A -"
    assert cells[0][2]["organisasjonsnummer"] == "916627939"
    fallback = cells_from_brenheter({"organisasjonsnummer": "916627939"})
    assert fallback == [("organisasjonsnummer", "916627939", {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_brenheter(["- P A L M E R A -"])
    with pytest.raises(ValueError, match="enhet members"):
        cells_from_brenheter({"_links": {"self": {"href": PALMERA_URL}}})


def test_entity_and_shape_claim_brreg_orgnr_only_after_mod11() -> None:
    entity = entity_from_enhet(ITEM_BODY)
    assert entity["subject_scheme"] == ORGNR_SCHEME
    assert entity["subject_code"] == "916627939"
    fields, keys = shape_from_brenheter(ITEM_BODY)
    assert keys == [
        {"scheme": ORGNR_SCHEME, "field_code": "organisasjonsnummer", "coverage_count": 1}
    ]
    assert fields[0]["field_code"] == "organisasjonsnummer"
    with pytest.raises(ValueError, match="mod-11"):
        entity_from_enhet({"organisasjonsnummer": "123456789", "navn": "nope"})
    assert valid_orgnr("916627939")
    assert valid_orgnr("923609016")
    assert not valid_orgnr("123456789")
    assert not valid_orgnr("91662793")  # too short
    assert not valid_orgnr("abcdefgh i")


def test_is_brenheter_url_accepts_only_enhet_item_paths() -> None:
    assert is_brenheter_url(PALMERA_URL)
    assert is_brenheter_url(ZOTKO_URL)
    assert not is_brenheter_url(LIST_URL)
    assert is_brenheter_collection_url(LIST_URL)
    assert is_brenheter_collection_url(LASTNED_URL)
    assert not is_brenheter_collection_url(PALMERA_URL)
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
    assert classify_access_path(PALMERA_URL)["kind"] == "entities"
    assert classify_access_path(LIST_URL)["kind"] == "none"
    assert classify_access_path(LASTNED_URL)["kind"] == "none"


def test_limit_and_offset_slice_printed_enheter() -> None:
    source = BrenheterSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["916627939"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["933365573"]
    assert source.list_dataset_refs(limit=1, offset=2) == []


def test_known_orgnrs_list_refuses_invalid_check_digit() -> None:
    with pytest.raises(Exception, match="mod-11"):
        BrenheterSource(orgnrs=["123456789"]).list_dataset_refs()


def test_fetch_refuses_oversized_orgnr_select(tmp_path: Path) -> None:
    source = BrenheterSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    with pytest.raises(SelectionTooLarge) as excinfo:
        fetch_observations(
            registry,
            DATASET_ID,
            table_id="ignored",
            http=FetchHttp(),
            select={"organisasjonsnummer": ["916627939", "933365573"]},
        )
    assert excinfo.value.limit == 1
    registry.close()


def test_fetch_refuses_mismatched_orgnr_select(tmp_path: Path) -> None:
    source = BrenheterSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    with pytest.raises(ValueError, match="does not match"):
        fetch_observations(
            registry,
            DATASET_ID,
            table_id="ignored",
            http=FetchHttp(),
            select={"organisasjonsnummer": ["933365573"]},
        )
    registry.close()


def test_fetch_refuses_unknown_select_field(tmp_path: Path) -> None:
    source = BrenheterSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    with pytest.raises(ValueError, match="does not filter"):
        fetch_observations(
            registry,
            DATASET_ID,
            table_id="ignored",
            http=FetchHttp(),
            select={"naeringskode": ["62.01"]},
        )
    registry.close()
