from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.crbio import (
    LIST_URL,
    CrbioSource,
    cells_from_crbio,
    crbio_table_id,
    is_crbio_url,
    printed_item_url,
)

DART_URL = "https://api.cristin.no/v2/biobanks/2052825"
EWOG_URL = "https://api.cristin.no/v2/biobanks/2052832"
UNIT_URL = "https://api.cristin.no/v2/units/1000.0.0.0"
INST_URL = "https://api.cristin.no/v2/institutions/1000"
DOCS_URL = "https://api.cristin.no/v2/"
DATASET_ID = "crbio:2052825"

CATALOG = [
    {
        "cristin_biobank_id": 2052825,
        "name": {"nb": "Daratumumab for behandling av immunologisk trombocytopeni (ITP) -DART-studien"},
        "biobank_id": "BBR-3429",
        "url": DART_URL,
    },
    {
        "cristin_biobank_id": 2052832,
        "name": {"nb": "EWOG-SAA-2010"},
        "biobank_id": "BBR-3431",
        "url": EWOG_URL,
    },
    {
        "name": {"nb": "missing id is skipped"},
        "url": "https://api.cristin.no/v2/biobanks/x",
    },
]
ITEM_BODY = {
    "cristin_biobank_id": 2052825,
    "name": {"nb": "Daratumumab for behandling av immunologisk trombocytopeni (ITP) -DART-studien"},
    "biobank_id": "BBR-3429",
    "main_language": "nb",
    "url": DART_URL,
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
        if url == DART_URL:
            return JsonResponse(status=200, url=url, body=ITEM_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"crbio fetch must GET, not POST {url}")


def test_printed_refs_copy_biobank_ids() -> None:
    source = CrbioSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["2052825", "2052832"]
    assert [ref.source_native_uri for ref in refs] == [DART_URL, EWOG_URL]
    assert all("/v2/biobanks/" in (ref.source_native_uri or "") for ref in refs)
    assert all("/v2/units/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/v2/institutions/" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_copies_printed_url() -> None:
    assert printed_item_url({"cristin_biobank_id": 2052825, "url": DART_URL}, LIST_URL) == DART_URL
    assert printed_item_url({"cristin_biobank_id": 2052825}, LIST_URL) == DART_URL


def test_crbio_is_a_registered_source() -> None:
    assert "crbio" in SOURCE_IDS
    assert "crunit" in SOURCE_IDS
    assert "crinst" in SOURCE_IDS
    assert "cristin" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("stkomiteer") + 1] == "crunit"
    assert SOURCE_IDS[SOURCE_IDS.index("crunit") + 1] == "barmark"
    assert SOURCE_IDS[SOURCE_IDS.index("barmark") + 1] == "crproj"
    assert SOURCE_IDS[SOURCE_IDS.index("crproj") + 1] == "ssbgis"
    assert SOURCE_IDS[SOURCE_IDS.index("ssbgis") + 1] == "stpartier"
    assert SOURCE_IDS[SOURCE_IDS.index("stpartier") + 1] == "crbio"
    assert SOURCE_IDS[-1] == "crbio"
    source = build_source("crbio")
    assert isinstance(source, CrbioSource)
    assert source.source_id == "crbio"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = CrbioSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "crbio"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == DART_URL
    assert row["title"] == "Daratumumab for behandling av immunologisk trombocytopeni (ITP) -DART-studien"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("crunit:")
    assert not str(row["id"]).startswith("crinst:")
    assert not str(row["id"]).startswith("cristin:")
    nxt = registry.get_dataset("crbio:2052832")
    assert nxt is not None
    assert nxt["title"] == "EWOG-SAA-2010"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "2052825"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["crbio_biobank"]["cristin_biobank_id"] == 2052825
    assert "url" not in payload["crbio_biobank"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_biobank_name(tmp_path: Path) -> None:
    source = CrbioSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == DART_URL
    assert result.table_id == "2052825"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["Daratumumab for behandling av immunologisk trombocytopeni (ITP) -DART-studien"]
    assert all(row["measure"] == "name" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["cristin_biobank_id"] == "2052825"
    assert dims["biobank_id"] == "BBR-3429"
    assert "url" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == DART_URL for row in rows)
    registry.close()


def test_cells_copy_printed_biobank() -> None:
    cells = cells_from_crbio(ITEM_BODY)
    assert cells == [
        (
            "name",
            "Daratumumab for behandling av immunologisk trombocytopeni (ITP) -DART-studien",
            {
                "cristin_biobank_id": "2052825",
                "biobank_id": "BBR-3429",
                "main_language": "nb",
            },
        )
    ]
    fallback = cells_from_crbio({"cristin_biobank_id": 2052825})
    assert fallback == [("cristin_biobank_id", 2052825, {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_crbio(["2052825"])
    with pytest.raises(ValueError, match="biobank members"):
        cells_from_crbio({"url": DART_URL})


def test_is_crbio_url_accepts_only_biobank_item_paths() -> None:
    assert is_crbio_url(DART_URL)
    assert is_crbio_url(EWOG_URL)
    assert not is_crbio_url(LIST_URL)
    assert crbio_table_id(DART_URL) == "2052825"
    assert not is_crbio_url(UNIT_URL)
    assert not is_crbio_url(INST_URL)
    assert not is_crbio_url(DOCS_URL)
    assert not is_crbio_url("https://data.norge.no/datasets/x")
    assert not is_crbio_url(None)


def test_limit_and_offset_slice_printed_biobanks() -> None:
    source = CrbioSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["2052825"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["2052832"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
