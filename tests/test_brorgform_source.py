from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.brorgform import (
    LIST_URL,
    BrorgformSource,
    brorgform_table_id,
    cells_from_brorgform,
    is_brorgform_url,
    printed_item_url,
)

AAFY_URL = "https://data.brreg.no/enhetsregisteret/api/organisasjonsformer/AAFY"
AS_URL = "https://data.brreg.no/enhetsregisteret/api/organisasjonsformer/AS"
ENHETER_URL = "https://data.brreg.no/enhetsregisteret/api/enheter"
KOMMUNER_URL = "https://data.brreg.no/enhetsregisteret/api/kommuner"
UNDERENHETER_URL = "https://data.brreg.no/enhetsregisteret/api/underenheter"
ROOT_URL = "https://data.brreg.no/enhetsregisteret/api"
FRIVILLIG_URL = "https://data.brreg.no/frivillighetsregisteret/enheter"
NORGES_BANK_URL = "https://data.norges-bank.no/api/agencyscheme?format=sdmx-json"
DATASET_ID = "brorgform:AS"

CATALOG = {
    "_embedded": {
        "organisasjonsformer": [
            {
                "kode": "AAFY",
                "beskrivelse": "Underenhet til ikke-næringsdrivende",
                "_links": {"self": {"href": AAFY_URL}},
            },
            {
                "kode": "AS",
                "beskrivelse": "Aksjeselskap",
                "_links": {"self": {"href": AS_URL}},
            },
            {
                "beskrivelse": "missing kode is skipped",
                "_links": {"self": {"href": "https://data.brreg.no/enhetsregisteret/api/organisasjonsformer/x"}},
            },
        ]
    }
}
ITEM_BODY = {
    "kode": "AS",
    "beskrivelse": "Aksjeselskap",
    "_links": {"self": {"href": AS_URL}},
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
        if url == AS_URL:
            return JsonResponse(status=200, url=url, body=ITEM_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"brorgform fetch must GET, not POST {url}")


def test_printed_refs_copy_form_kodes() -> None:
    source = BrorgformSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["AAFY", "AS"]
    assert [ref.source_native_uri for ref in refs] == [AAFY_URL, AS_URL]
    assert all("/enheter" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/kommuner" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_copies_printed_self_href() -> None:
    assert printed_item_url({"kode": "AS", "_links": {"self": {"href": AS_URL}}}, LIST_URL) == AS_URL
    assert printed_item_url({"kode": "AS"}, LIST_URL) == AS_URL


def test_brorgform_is_a_registered_source() -> None:
    assert "brorgform" in SOURCE_IDS
    assert "brreg" in SOURCE_IDS
    assert "ssclass" in SOURCE_IDS
    assert "ssbsec" in SOURCE_IDS
    assert "ssbfam" in SOURCE_IDS
    assert "nbconcept" in SOURCE_IDS
    source = build_source("brorgform")
    assert isinstance(source, BrorgformSource)
    assert source.source_id == "brorgform"


def test_harvest_writes_printed_kode_and_null_license(tmp_path: Path) -> None:
    source = BrorgformSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "brorgform"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == AS_URL
    assert row["title"] == "Aksjeselskap"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("brreg:")
    aafy = registry.get_dataset("brorgform:AAFY")
    assert aafy is not None
    assert aafy["title"] == "Underenhet til ikke-næringsdrivende"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "AS"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["brorgform_organisasjonsform"]["kode"] == "AS"
    assert "_links" not in payload["brorgform_organisasjonsform"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_beskrivelse(tmp_path: Path) -> None:
    source = BrorgformSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == AS_URL
    assert result.table_id == "AS"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["Aksjeselskap"]
    assert all(row["measure"] == "beskrivelse" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["kode"] == "AS"
    assert "_links" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == AS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_form() -> None:
    cells = cells_from_brorgform(ITEM_BODY)
    assert cells == [("beskrivelse", "Aksjeselskap", {"kode": "AS"})]
    fallback = cells_from_brorgform({"kode": "AS"})
    assert fallback == [("kode", "AS", {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_brorgform(["Aksjeselskap"])
    with pytest.raises(ValueError, match="organisasjonsform members"):
        cells_from_brorgform({"_links": {"self": {"href": AS_URL}}})


def test_is_brorgform_url_accepts_only_organisasjonsformer_paths() -> None:
    assert is_brorgform_url(AS_URL)
    assert is_brorgform_url(LIST_URL)
    assert brorgform_table_id(AS_URL) == "AS"
    assert not is_brorgform_url(ENHETER_URL)
    assert not is_brorgform_url(KOMMUNER_URL)
    assert not is_brorgform_url(UNDERENHETER_URL)
    assert not is_brorgform_url(ROOT_URL)
    assert not is_brorgform_url(FRIVILLIG_URL)
    assert not is_brorgform_url(NORGES_BANK_URL)
    assert not is_brorgform_url("https://data.norge.no/datasets/x")
    assert not is_brorgform_url(None)


def test_limit_and_offset_slice_printed_forms() -> None:
    source = BrorgformSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["AAFY"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["AS"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
