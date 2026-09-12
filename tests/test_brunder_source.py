from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import SelectionTooLarge, classify_access_path, fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.brunder import (
    LIST_URL,
    ORGNR_SCHEME,
    BrunderSource,
    brunder_table_id,
    cells_from_brunder,
    entity_from_brunder,
    is_brunder_collection_url,
    is_brunder_url,
    printed_item_url,
    shape_from_brunder,
)

ZOTKO_URL = "https://data.brreg.no/enhetsregisteret/api/underenheter/933489272"
MYHRE_URL = "https://data.brreg.no/enhetsregisteret/api/underenheter/934551524"
LASTNED_URL = "https://data.brreg.no/enhetsregisteret/api/underenheter/lastned"
ENHETER_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/933489272"
OPPDATER_URL = "https://data.brreg.no/enhetsregisteret/api/oppdateringer/underenheter"
ORGFORM_URL = "https://data.brreg.no/enhetsregisteret/api/organisasjonsformer/AS"
KOMMUNER_URL = "https://data.brreg.no/enhetsregisteret/api/kommuner/0301"
ROOT_URL = "https://data.brreg.no/enhetsregisteret/api"
DATASET_ID = "brunder:933489272"

CATALOG = {
    "_embedded": {
        "underenheter": [
            {
                "organisasjonsnummer": "933489272",
                "navn": "- ZOTKO .NO",
                "_links": {"self": {"href": ZOTKO_URL}},
            },
            {
                "organisasjonsnummer": "934551524",
                "navn": "----ADVOKATFIRMAET CATO MYHRE",
                "_links": {"self": {"href": MYHRE_URL}},
            },
            {
                "navn": "missing organisasjonsnummer is skipped",
                "_links": {"self": {"href": ZOTKO_URL}},
            },
            {
                "organisasjonsnummer": "123456789",
                "navn": "invalid check digit is skipped",
            },
        ]
    }
}
ITEM_BODY = {
    "organisasjonsnummer": "933489272",
    "navn": "- ZOTKO .NO",
    "organisasjonsform": {"kode": "BEDR", "beskrivelse": "Underenhet"},
    "registrertIMvaregisteret": False,
    "overordnetEnhet": "933365573",
    "beliggenhetsadresse": {
        "adresse": ["Testgata 1"],
        "kommune": "OSLO",
        "kommunenummer": "0301",
        "land": "Norge",
        "_links": {"kommune": {"href": KOMMUNER_URL}},
    },
    "_links": {"self": {"href": ZOTKO_URL}},
}
MYHRE_BODY = {
    "organisasjonsnummer": "934551524",
    "navn": "----ADVOKATFIRMAET CATO MYHRE",
    "overordnetEnhet": "934551435",
    "_links": {"self": {"href": MYHRE_URL}},
}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == LIST_URL:
            return CATALOG
        if url == ZOTKO_URL:
            return ITEM_BODY
        if url == MYHRE_URL:
            return MYHRE_BODY
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        self.gets.append(url)
        if url == ZOTKO_URL:
            return JsonResponse(status=200, url=url, body=ITEM_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"brunder fetch must GET, not POST {url}")


def test_printed_refs_copy_organisasjonsnummer() -> None:
    source = BrunderSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["933489272", "934551524"]
    assert [ref.source_native_uri for ref in refs] == [ZOTKO_URL, MYHRE_URL]
    assert all("/enheter/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/oppdateringer/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/organisasjonsformer" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/kommuner" not in (ref.source_native_uri or "") for ref in refs)
    assert all("lastned" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_copies_printed_public_self_href() -> None:
    assert printed_item_url(
        {"organisasjonsnummer": "933489272", "_links": {"self": {"href": ZOTKO_URL}}},
        LIST_URL,
    ) == ZOTKO_URL
    assert printed_item_url({"organisasjonsnummer": "933489272"}, LIST_URL) == ZOTKO_URL
    assert printed_item_url(
        {"organisasjonsnummer": "933489272", "_links": {"self": {"href": LASTNED_URL}}},
        LIST_URL,
    ) == ZOTKO_URL


def test_brunder_is_a_registered_source() -> None:
    assert "brunder" in SOURCE_IDS
    assert "brreg" in SOURCE_IDS
    assert "brorgform" in SOURCE_IDS
    assert "brkommuner" in SOURCE_IDS
    assert "brroller" in SOURCE_IDS
    assert "broppdater" in SOURCE_IDS
    assert "kifylker" in SOURCE_IDS
    assert "brrepresent" in SOURCE_IDS
    assert "brenheter" in SOURCE_IDS
    assert "ssbvar" in SOURCE_IDS
    assert "nordatlas" in SOURCE_IDS
    assert "ssbcorr" in SOURCE_IDS
    assert "fdkorg" in SOURCE_IDS
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
    source = build_source("brunder")
    assert isinstance(source, BrunderSource)
    assert source.source_id == "brunder"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = BrunderSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "brunder"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == ZOTKO_URL
    assert row["title"] == "- ZOTKO .NO"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("brreg:")
    assert not str(row["id"]).startswith("broppdater:")
    assert not str(row["id"]).startswith("brorgform:")
    assert not str(row["id"]).startswith("brenheter:")
    assert not str(row["id"]).startswith("brrepresent:")
    nxt = registry.get_dataset("brunder:934551524")
    assert nxt is not None
    assert nxt["title"] == "----ADVOKATFIRMAET CATO MYHRE"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "933489272"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["brunder_underenhet"]["organisasjonsnummer"] == "933489272"
    assert payload["brunder_underenhet"]["navn"] == "- ZOTKO .NO"
    assert "_links" not in payload["brunder_underenhet"]
    assert payload["brunder_self_href"] == ZOTKO_URL
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_stores_entity_record_and_fills_resource_index(tmp_path: Path) -> None:
    source = BrunderSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == ZOTKO_URL
    assert result.table_id == "933489272"
    assert result.http_status == 200
    assert result.counts.listed == 1
    assert result.counts.inserted == 1
    rows = registry.list_records(DATASET_ID)
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "entity"
    assert row["subject_scheme"] == ORGNR_SCHEME
    assert row["subject_code"] == "933489272"
    assert row["subject_label"] == "- ZOTKO .NO"
    assert row["measure"] is None
    assert row["value_num"] is None
    assert row["license"] is None
    attrs = json.loads(row["attributes_json"])
    assert attrs["overordnetEnhet"] == "933365573"
    assert attrs["organisasjonsform"] == "BEDR"
    assert attrs["beliggenhetsadresse"] == {
        "adresse": ["Testgata 1"],
        "kommune": "OSLO",
        "kommunenummer": "0301",
        "land": "Norge",
    }
    assert registry.list_observations(DATASET_ID) == []
    cap = registry.get_capability(DATASET_ID)
    assert cap is not None
    assert cap["capability"] == "entities"
    assert cap["record_kind"] == "entity"
    assert cap["endpoint"] == ZOTKO_URL
    assert cap["request_method"] == "GET"
    assert cap["verified_sample_count"] == 1
    fields = {field["field_code"]: field for field in registry.resource_fields(DATASET_ID)}
    assert fields["organisasjonsnummer"]["field_role"] == "key"
    assert fields["overordnetEnhet"]["field_role"] == "attribute"
    assert fields["beliggenhetsadresse.kommunenummer"]["field_role"] == "attribute"
    assert registry.datasets_containing_value("933365573", field_code="overordnetEnhet")
    keys = registry.datasets_with_key(ORGNR_SCHEME)
    assert [key["dataset_id"] for key in keys] == [DATASET_ID]
    assert classify_access_path(ZOTKO_URL)["kind"] == "entities"
    registry.close()


def test_cells_copy_printed_underenhet() -> None:
    cells = cells_from_brunder(ITEM_BODY)
    assert cells[0][0] == "navn"
    assert cells[0][1] == "- ZOTKO .NO"
    assert cells[0][2]["organisasjonsnummer"] == "933489272"
    assert cells[0][2]["overordnetEnhet"] == "933365573"
    fallback = cells_from_brunder({"organisasjonsnummer": "933489272"})
    assert fallback == [("organisasjonsnummer", "933489272", {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_brunder(["- ZOTKO .NO"])
    with pytest.raises(ValueError, match="underenhet members"):
        cells_from_brunder({"_links": {"self": {"href": ZOTKO_URL}}})


def test_entity_and_shape_validate_subject_and_parent_orgnrs() -> None:
    entity = entity_from_brunder(ITEM_BODY)
    assert entity["subject_scheme"] == ORGNR_SCHEME
    assert entity["subject_code"] == "933489272"
    assert entity["attributes"]["overordnetEnhet"] == "933365573"
    fields, keys = shape_from_brunder(ITEM_BODY)
    assert keys == [
        {"scheme": ORGNR_SCHEME, "field_code": "organisasjonsnummer", "coverage_count": 1}
    ]
    assert any(field["field_code"] == "overordnetEnhet" for field in fields)
    with pytest.raises(ValueError, match="mod-11"):
        entity_from_brunder({"organisasjonsnummer": "123456789"})
    with pytest.raises(ValueError, match="parent organisation"):
        entity_from_brunder(
            {"organisasjonsnummer": "933489272", "overordnetEnhet": "123456789"}
        )


def test_is_brunder_url_accepts_only_underenhet_item_paths() -> None:
    assert is_brunder_url(ZOTKO_URL)
    assert is_brunder_url(MYHRE_URL)
    assert brunder_table_id(ZOTKO_URL) == "933489272"
    assert not is_brunder_url(LIST_URL)
    assert is_brunder_collection_url(LIST_URL)
    assert not is_brunder_url(LASTNED_URL)
    assert is_brunder_collection_url(LASTNED_URL)
    assert not is_brunder_url(ENHETER_URL)
    assert not is_brunder_url(OPPDATER_URL)
    assert not is_brunder_url(ORGFORM_URL)
    assert not is_brunder_url(KOMMUNER_URL)
    assert not is_brunder_url(ROOT_URL)
    assert not is_brunder_url(
        "https://data.brreg.no/enhetsregisteret/api/underenheter/123456789"
    )
    assert not is_brunder_url("https://data.norge.no/datasets/x")
    assert not is_brunder_url(None)
    assert classify_access_path(ZOTKO_URL)["kind"] == "entities"
    assert classify_access_path(LIST_URL)["kind"] == "none"
    assert classify_access_path(LASTNED_URL)["kind"] == "none"


def test_limit_and_offset_slice_printed_underenheter() -> None:
    source = BrunderSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["933489272"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["934551524"]
    assert source.list_dataset_refs(limit=1, offset=2) == []


def test_fetch_refuses_oversized_orgnr_select(tmp_path: Path) -> None:
    source = BrunderSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    http = FetchHttp()
    with pytest.raises(SelectionTooLarge) as excinfo:
        fetch_observations(
            registry,
            DATASET_ID,
            table_id="ignored",
            http=http,
            select={"organisasjonsnummer": ["933489272", "934551524"]},
        )
    assert excinfo.value.limit == 1
    assert http.gets == []
    registry.close()


def test_fetch_refuses_mismatched_and_unknown_selects(tmp_path: Path) -> None:
    source = BrunderSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    http = FetchHttp()
    with pytest.raises(ValueError, match="does not match"):
        fetch_observations(
            registry,
            DATASET_ID,
            table_id="ignored",
            http=http,
            select={"organisasjonsnummer": ["934551524"]},
        )
    with pytest.raises(ValueError, match="does not filter"):
        fetch_observations(
            registry,
            DATASET_ID,
            table_id="ignored",
            http=http,
            select={"overordnetEnhet": ["933365573"]},
        )
    assert http.gets == []
    registry.close()


def test_fetch_refuses_a_different_printed_orgnr(tmp_path: Path) -> None:
    class WrongEntityHttp(FetchHttp):
        def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
            if url == ZOTKO_URL:
                return JsonResponse(status=200, url=url, body=MYHRE_BODY)
            return super().get_json_response(url, headers=headers)

    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, BrunderSource(http=CatalogHttp()))
    with pytest.raises(ValueError, match="not the requested"):
        fetch_observations(
            registry,
            DATASET_ID,
            table_id="ignored",
            http=WrongEntityHttp(),
        )
    assert registry.list_records(DATASET_ID) == []
    registry.close()
