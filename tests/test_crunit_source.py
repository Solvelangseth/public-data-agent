from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.crunit import (
    LIST_URL,
    CrunitSource,
    cells_from_crunit,
    crunit_table_id,
    is_crunit_url,
    printed_item_url,
)

UNKNOWN_URL = "https://api.cristin.no/v2/units/0.0.0.0"
HAUG_URL = "https://api.cristin.no/v2/units/1000.0.0.0"
INST_URL = "https://api.cristin.no/v2/institutions/1000"
DOCS_URL = "https://api.cristin.no/v2/"
UNDERENHET_URL = "https://data.brreg.no/enhetsregisteret/api/underenheter/933489272"
DATASET_ID = "crunit:1000.0.0.0"

CATALOG = [
    {
        "cristin_unit_id": "0.0.0.0",
        "unit_name": {"en": "Unknown"},
        "acronym": "UNKNOWN",
        "url": UNKNOWN_URL,
    },
    {
        "cristin_unit_id": "1000.0.0.0",
        "unit_name": {"nb": "AOF Haugaland"},
        "acronym": "AOFHAUGALA",
        "url": HAUG_URL,
    },
    {
        "unit_name": {"nb": "missing id is skipped"},
        "url": "https://api.cristin.no/v2/units/x",
    },
]
ITEM_BODY = {
    "cristin_unit_id": "1000.0.0.0",
    "unit_name": {"nb": "AOF Haugaland"},
    "acronym": "AOFHAUGALA",
    "country": "NO",
    "url": HAUG_URL,
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
        if url == HAUG_URL:
            return JsonResponse(status=200, url=url, body=ITEM_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"crunit fetch must GET, not POST {url}")


def test_printed_refs_copy_unit_ids() -> None:
    source = CrunitSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["0.0.0.0", "1000.0.0.0"]
    assert [ref.source_native_uri for ref in refs] == [UNKNOWN_URL, HAUG_URL]
    assert all("/v2/units/" in (ref.source_native_uri or "") for ref in refs)
    assert all("/v2/institutions/" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_copies_printed_url() -> None:
    assert printed_item_url({"cristin_unit_id": "1000.0.0.0", "url": HAUG_URL}, LIST_URL) == HAUG_URL
    assert printed_item_url({"cristin_unit_id": "1000.0.0.0"}, LIST_URL) == HAUG_URL


def test_crunit_is_a_registered_source() -> None:
    assert "crunit" in SOURCE_IDS
    assert "crinst" in SOURCE_IDS
    assert "cristin" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("brorgformen") + 1] == "crinst"
    assert SOURCE_IDS[SOURCE_IDS.index("crinst") + 1] == "stsaker"
    assert SOURCE_IDS[SOURCE_IDS.index("stsaker") + 1] == "ssbsubj"
    assert SOURCE_IDS[SOURCE_IDS.index("ssbsubj") + 1] == "stkomiteer"
    assert SOURCE_IDS[SOURCE_IDS.index("stkomiteer") + 1] == "crunit"
    assert SOURCE_IDS[SOURCE_IDS.index("crunit") + 1] == "barmark"
<<<<<<< HEAD
    assert SOURCE_IDS[SOURCE_IDS.index("barmark") + 1] == "crproj"
    assert SOURCE_IDS[-1] == "crproj"
=======
    assert SOURCE_IDS[SOURCE_IDS.index("barmark") + 1] == "ssbgis"
    assert SOURCE_IDS[-1] == "ssbgis"
>>>>>>> 159e6d4 (fix(ssbgis): restore crunit last-id chain after rebase docs replay)
    source = build_source("crunit")
    assert isinstance(source, CrunitSource)
    assert source.source_id == "crunit"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = CrunitSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "crunit"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == HAUG_URL
    assert row["title"] == "AOF Haugaland"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("crinst:")
    assert not str(row["id"]).startswith("cristin:")
    nxt = registry.get_dataset("crunit:0.0.0.0")
    assert nxt is not None
    assert nxt["title"] == "Unknown"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "1000.0.0.0"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["crunit_unit"]["cristin_unit_id"] == "1000.0.0.0"
    assert "url" not in payload["crunit_unit"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_unit_name(tmp_path: Path) -> None:
    source = CrunitSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == HAUG_URL
    assert result.table_id == "1000.0.0.0"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["AOF Haugaland"]
    assert all(row["measure"] == "unit_name" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["cristin_unit_id"] == "1000.0.0.0"
    assert dims["acronym"] == "AOFHAUGALA"
    assert "url" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == HAUG_URL for row in rows)
    registry.close()


def test_cells_copy_printed_unit() -> None:
    cells = cells_from_crunit(ITEM_BODY)
    assert cells == [
        (
            "unit_name",
            "AOF Haugaland",
            {
                "cristin_unit_id": "1000.0.0.0",
                "acronym": "AOFHAUGALA",
                "country": "NO",
            },
        )
    ]
    fallback = cells_from_crunit({"cristin_unit_id": "1000.0.0.0"})
    assert fallback == [("cristin_unit_id", "1000.0.0.0", {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_crunit(["1000.0.0.0"])
    with pytest.raises(ValueError, match="unit members"):
        cells_from_crunit({"url": HAUG_URL})


def test_is_crunit_url_accepts_only_unit_item_paths() -> None:
    assert is_crunit_url(HAUG_URL)
    assert is_crunit_url(UNKNOWN_URL)
    assert not is_crunit_url(LIST_URL)
    assert crunit_table_id(HAUG_URL) == "1000.0.0.0"
    assert not is_crunit_url(INST_URL)
    assert not is_crunit_url(DOCS_URL)
    assert not is_crunit_url(UNDERENHET_URL)
    assert not is_crunit_url("https://data.norge.no/datasets/x")
    assert not is_crunit_url(None)


def test_limit_and_offset_slice_printed_units() -> None:
    source = CrunitSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["0.0.0.0"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["1000.0.0.0"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
