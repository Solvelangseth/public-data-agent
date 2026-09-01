from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.crinst import (
    LIST_URL,
    CrinstSource,
    cells_from_crinst,
    crinst_table_id,
    is_crinst_url,
    printed_item_url,
)

HAUG_URL = "https://api.cristin.no/v2/institutions/1000"
NEXT_URL = "https://api.cristin.no/v2/institutions/1010"
UNITS_URL = "https://api.cristin.no/v2/units/0.0.0.0"
DOCS_URL = "https://api.cristin.no/v2/"
UNDERENHET_URL = "https://data.brreg.no/enhetsregisteret/api/underenheter/933489272"
DATASET_ID = "crinst:1000"

CATALOG = [
    {
        "cristin_institution_id": "1000",
        "institution_name": {"nb": "AOF Haugaland"},
        "acronym": "AOFHAUGALA",
        "country": "NO",
        "url": HAUG_URL,
    },
    {
        "cristin_institution_id": "1010",
        "institution_name": {"nb": "ANDRE INSTITUSJON"},
        "acronym": "ANDRE",
        "country": "NO",
        "url": NEXT_URL,
    },
    {
        "institution_name": {"nb": "missing id is skipped"},
        "url": "https://api.cristin.no/v2/institutions/x",
    },
]
ITEM_BODY = {
    "cristin_institution_id": "1000",
    "institution_name": {"nb": "AOF Haugaland"},
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
        raise AssertionError(f"crinst fetch must GET, not POST {url}")


def test_printed_refs_copy_institution_ids() -> None:
    source = CrinstSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["1000", "1010"]
    assert [ref.source_native_uri for ref in refs] == [HAUG_URL, NEXT_URL]
    assert all("/v2/institutions/" in (ref.source_native_uri or "") for ref in refs)
    assert all("/v2/units/" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_copies_printed_url() -> None:
    assert printed_item_url({"cristin_institution_id": "1000", "url": HAUG_URL}, LIST_URL) == HAUG_URL
    assert printed_item_url({"cristin_institution_id": "1000"}, LIST_URL) == HAUG_URL


def test_crinst_is_a_registered_source() -> None:
    assert "crinst" in SOURCE_IDS
    assert "cristin" in SOURCE_IDS
    assert "brunder" in SOURCE_IDS
    assert "brenheter" in SOURCE_IDS
    assert "ssbvar" in SOURCE_IDS
    assert "nordatlas" in SOURCE_IDS
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
    assert SOURCE_IDS[-1] == "dsbgis"
    source = build_source("crinst")
    assert isinstance(source, CrinstSource)
    assert source.source_id == "crinst"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = CrinstSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "crinst"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == HAUG_URL
    assert row["title"] == "AOF Haugaland"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("cristin:")
    nxt = registry.get_dataset("crinst:1010")
    assert nxt is not None
    assert nxt["title"] == "ANDRE INSTITUSJON"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "1000"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["crinst_institution"]["cristin_institution_id"] == "1000"
    assert "url" not in payload["crinst_institution"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_institution_name(tmp_path: Path) -> None:
    source = CrinstSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == HAUG_URL
    assert result.table_id == "1000"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["AOF Haugaland"]
    assert all(row["measure"] == "institution_name" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["cristin_institution_id"] == "1000"
    assert dims["acronym"] == "AOFHAUGALA"
    assert "url" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == HAUG_URL for row in rows)
    registry.close()


def test_cells_copy_printed_institution() -> None:
    cells = cells_from_crinst(ITEM_BODY)
    assert cells == [
        (
            "institution_name",
            "AOF Haugaland",
            {
                "cristin_institution_id": "1000",
                "acronym": "AOFHAUGALA",
                "country": "NO",
            },
        )
    ]
    fallback = cells_from_crinst({"cristin_institution_id": "1000"})
    assert fallback == [("cristin_institution_id", "1000", {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_crinst(["1000"])
    with pytest.raises(ValueError, match="institution members"):
        cells_from_crinst({"url": HAUG_URL})


def test_is_crinst_url_accepts_only_institution_item_paths() -> None:
    assert is_crinst_url(HAUG_URL)
    assert not is_crinst_url(LIST_URL)
    assert crinst_table_id(HAUG_URL) == "1000"
    assert not is_crinst_url(UNITS_URL)
    assert not is_crinst_url(DOCS_URL)
    assert not is_crinst_url(UNDERENHET_URL)
    assert not is_crinst_url("https://data.norge.no/datasets/x")
    assert not is_crinst_url(None)


def test_limit_and_offset_slice_printed_institutions() -> None:
    source = CrinstSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["1000"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["1010"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
