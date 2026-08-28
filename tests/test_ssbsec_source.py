from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.ssbsec import (
    LIST_URL,
    SsbsecSource,
    cells_from_ssbsec,
    is_ssbsec_url,
    ssbsec_table_id,
)

SECTIONS_URL = "https://data.ssb.no/api/klass/v1/ssbsections"
FAMILIES_URL = "https://data.ssb.no/api/klass/v1/classificationfamilies"
KLASS_VERSION_URL = "https://data.ssb.no/api/klass/v1/versions/683.json"
TABLES_URL = "https://data.ssb.no/api/pxwebapi/v2/tables"
DATASET_ID = "ssbsec:ssbsections"

CATALOG = {
    "_embedded": {
        "ssbSections": [
            {"name": "120 - Seksjon for internasjonalt sekretariat", "id": None},
            {"name": "210 - Seksjon for nasjonalregnskap", "id": None},
            {"name": "211 - Seksjon for finansregnskap", "id": None},
        ]
    },
    "_links": {"self": {"href": SECTIONS_URL}},
}
FETCH_BODY = {
    "_embedded": {
        "ssbSections": [
            {"name": "120 - Seksjon for internasjonalt sekretariat", "id": None},
            {"name": "210 - Seksjon for nasjonalregnskap", "id": None},
        ]
    },
    "_links": {"self": {"href": SECTIONS_URL}},
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
        if url == SECTIONS_URL:
            return JsonResponse(status=200, url=url, body=FETCH_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"ssbsec fetch must GET, not POST {url}")


def test_printed_refs_copy_collection_path() -> None:
    source = SsbsecSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["ssbsections"]
    assert [ref.source_native_uri for ref in refs] == [SECTIONS_URL]


def test_ssbsec_is_a_registered_source() -> None:
    assert "ssbsec" in SOURCE_IDS
    assert "ssbv2" in SOURCE_IDS
    assert "ssb" in SOURCE_IDS
    assert "nbdsd" in SOURCE_IDS
    source = build_source("ssbsec")
    assert isinstance(source, SsbsecSource)
    assert source.source_id == "ssbsec"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = SsbsecSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "ssbsec"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == SECTIONS_URL
    assert row["title"] == "ssbsections"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("ssbv2:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "ssbsections"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["ssbsec_collection"] == "ssbsections"
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_section_names(tmp_path: Path) -> None:
    source = SsbsecSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == SECTIONS_URL
    assert result.table_id == "ssbsections"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert set(values) == {
        "120 - Seksjon for internasjonalt sekretariat",
        "210 - Seksjon for nasjonalregnskap",
    }
    assert all(row["measure"] == "name" for row in rows)
    by_value = {json.loads(row["value_json"]): json.loads(row["dimensions_json"]) for row in rows}
    assert by_value["210 - Seksjon for nasjonalregnskap"] == {
        "name": "210 - Seksjon for nasjonalregnskap"
    }
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == SECTIONS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_names_and_skip_null_id() -> None:
    cells = cells_from_ssbsec(FETCH_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[1]
    assert measure == "name"
    assert value == "210 - Seksjon for nasjonalregnskap"
    assert dims == {"name": "210 - Seksjon for nasjonalregnskap"}
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_ssbsec(["nasjonalregnskap"])


def test_is_ssbsec_url_accepts_only_ssbsections_path() -> None:
    assert is_ssbsec_url(SECTIONS_URL)
    assert ssbsec_table_id(SECTIONS_URL) == "ssbsections"
    assert not is_ssbsec_url(FAMILIES_URL)
    assert not is_ssbsec_url(KLASS_VERSION_URL)
    assert not is_ssbsec_url(TABLES_URL)
    assert not is_ssbsec_url("https://data.ssb.no/api/klass/v1/classifications")
    assert not is_ssbsec_url("https://www.ssb.no/api/klass/v1/ssbsections")
    assert not is_ssbsec_url(None)


def test_limit_and_offset_slice_printed_collection() -> None:
    source = SsbsecSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=10)] == [
        "ssbsections"
    ]
    assert source.list_dataset_refs(limit=1, offset=1) == []
