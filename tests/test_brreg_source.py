from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.brreg_hal import brreg_table_id, cells_from_brreg, is_brreg_url
from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.brreg import BrregEnhetsregisterSource

LIST_URL = "https://data.brreg.no/enhetsregisteret/api"
ENHETER_URL = "https://data.brreg.no/enhetsregisteret/api/enheter"
UNDERENHETER_URL = "https://data.brreg.no/enhetsregisteret/api/underenheter"
ORGFORMER_URL = "https://data.brreg.no/enhetsregisteret/api/organisasjonsformer"
OPPDATERINGER_ENHETER_URL = "https://data.brreg.no/enhetsregisteret/api/oppdateringer/enheter"
OPPDATERINGER_UNDERENHETER_URL = "https://data.brreg.no/enhetsregisteret/api/oppdateringer/underenheter"
KOMMUNER_URL = "https://data.brreg.no/enhetsregisteret/api/kommuner"
DATASET_ID = "brreg:organisasjonsformer"

ROOT_BODY = {
    "_links": {
        "self": {"href": LIST_URL},
        "enheter": {"href": ENHETER_URL},
        "underenheter": {"href": UNDERENHETER_URL},
        "organisasjonsformer": {"href": ORGFORMER_URL},
        "oppdateringer/enheter": {"href": OPPDATERINGER_ENHETER_URL},
        "oppdateringer/underenheter": {"href": OPPDATERINGER_UNDERENHETER_URL},
        "kommuner": {"href": KOMMUNER_URL},
    }
}
ORGFORMER_ITEM = {
    "kode": "AAFY",
    "beskrivelse": "Underenhet til ikke-næringsdrivende",
    "_links": {
        "self": {"href": "https://data.brreg.no/enhetsregisteret/api/organisasjonsformer/AAFY"}
    },
}
ORGFORMER_BODY = {"_embedded": {"organisasjonsformer": [ORGFORMER_ITEM]}}
COLLECTION_HREFS = {
    ENHETER_URL,
    UNDERENHETER_URL,
    ORGFORMER_URL,
    OPPDATERINGER_ENHETER_URL,
    OPPDATERINGER_UNDERENHETER_URL,
    KOMMUNER_URL,
}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == LIST_URL:
            return ROOT_BODY
        if url == ORGFORMER_URL:
            return ORGFORMER_BODY
        if url in COLLECTION_HREFS:
            return {}
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == ORGFORMER_URL:
            return JsonResponse(status=200, url=url, body=ORGFORMER_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"brreg fetch must GET, not POST {url}")


def test_printed_links_become_refs_and_self_is_skipped() -> None:
    source = BrregEnhetsregisterSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "enheter",
        "underenheter",
        "organisasjonsformer",
        "oppdateringer/enheter",
        "oppdateringer/underenheter",
        "kommuner",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        ENHETER_URL,
        UNDERENHETER_URL,
        ORGFORMER_URL,
        OPPDATERINGER_ENHETER_URL,
        OPPDATERINGER_UNDERENHETER_URL,
        KOMMUNER_URL,
    ]
    assert "self" not in [ref.source_native_id for ref in refs]
    assert LIST_URL not in [ref.source_native_uri for ref in refs]


def test_brreg_is_a_registered_source() -> None:
    assert "brreg" in SOURCE_IDS
    source = build_source("brreg")
    assert isinstance(source, BrregEnhetsregisterSource)
    assert source.source_id == "brreg"


def test_harvest_writes_printed_href_without_license_or_publisher(tmp_path: Path) -> None:
    source = BrregEnhetsregisterSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 6
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "brreg"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == ORGFORMER_URL
    assert row["license"] is None
    assert row["publisher_name"] is None
    assert not str(row["id"]).startswith("datanorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["brreg_metadata"]["_embedded"]["organisasjonsformer"][0]["kode"] == "AAFY"
    registry.close()


def test_fetch_gets_printed_organisasjonsformer_url(tmp_path: Path) -> None:
    source = BrregEnhetsregisterSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == ORGFORMER_URL
    assert result.table_id == "organisasjonsformer"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    assert [json.loads(row["value_json"]) for row in rows] == ["AAFY"]
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["kode"] == "AAFY"
    assert dims["beskrivelse"] == "Underenhet til ikke-næringsdrivende"
    assert "_links" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == ORGFORMER_URL for row in rows)
    registry.close()


def test_cells_copy_printed_fields() -> None:
    cells = cells_from_brreg(ORGFORMER_BODY, measure="organisasjonsformer")
    assert len(cells) == 1
    measure, value, dims = cells[0]
    assert measure == "organisasjonsformer"
    assert value == "AAFY"
    assert dims["kode"] == "AAFY"
    assert dims["beskrivelse"] == "Underenhet til ikke-næringsdrivende"
    assert "_links" not in dims
    with pytest.raises(ValueError, match="_embedded"):
        cells_from_brreg({}, measure="organisasjonsformer")


def test_is_brreg_url_accepts_only_enhetsregisteret_api() -> None:
    assert is_brreg_url(LIST_URL)
    assert is_brreg_url(ORGFORMER_URL)
    assert brreg_table_id(ORGFORMER_URL) == "organisasjonsformer"
    assert not is_brreg_url("https://data.norge.no/datasets/x")
    assert not is_brreg_url("https://data.brreg.no/enhetsregisteret")
    assert not is_brreg_url("https://hotell.difi.no/api/json/brreg/enhetsregisteret")
    assert not is_brreg_url("https://example.com/enhetsregisteret/api")
