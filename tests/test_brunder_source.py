from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.brunder import (
    LIST_URL,
    BrunderSource,
    brunder_table_id,
    cells_from_brunder,
    is_brunder_url,
    printed_item_url,
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
        ]
    }
}
ITEM_BODY = {
    "organisasjonsnummer": "933489272",
    "navn": "- ZOTKO .NO",
    "registrertIMvaregisteret": False,
    "beliggenhetsadresse": {"land": "Norge"},
    "_links": {"self": {"href": ZOTKO_URL}},
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
    assert SOURCE_IDS[-1] == "stperioder"
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


def test_fetch_gets_printed_navn(tmp_path: Path) -> None:
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
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["- ZOTKO .NO"]
    assert all(row["measure"] == "navn" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["organisasjonsnummer"] == "933489272"
    assert "beliggenhetsadresse" not in dims
    assert "_links" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == ZOTKO_URL for row in rows)
    registry.close()


def test_cells_copy_printed_underenhet() -> None:
    cells = cells_from_brunder(ITEM_BODY)
    assert cells == [
        (
            "navn",
            "- ZOTKO .NO",
            {"organisasjonsnummer": "933489272", "registrertIMvaregisteret": "False"},
        )
    ]
    fallback = cells_from_brunder({"organisasjonsnummer": "933489272"})
    assert fallback == [("organisasjonsnummer", "933489272", {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_brunder(["- ZOTKO .NO"])
    with pytest.raises(ValueError, match="underenhet members"):
        cells_from_brunder({"_links": {"self": {"href": ZOTKO_URL}}})


def test_is_brunder_url_accepts_only_underenhet_item_paths() -> None:
    assert is_brunder_url(ZOTKO_URL)
    assert is_brunder_url(MYHRE_URL)
    assert brunder_table_id(ZOTKO_URL) == "933489272"
    assert not is_brunder_url(LIST_URL)
    assert not is_brunder_url(LASTNED_URL)
    assert not is_brunder_url(ENHETER_URL)
    assert not is_brunder_url(OPPDATER_URL)
    assert not is_brunder_url(ORGFORM_URL)
    assert not is_brunder_url(KOMMUNER_URL)
    assert not is_brunder_url(ROOT_URL)
    assert not is_brunder_url("https://data.norge.no/datasets/x")
    assert not is_brunder_url(None)


def test_limit_and_offset_slice_printed_underenheter() -> None:
    source = BrunderSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["933489272"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["934551524"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
