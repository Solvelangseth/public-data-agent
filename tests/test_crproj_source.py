from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.crproj import (
    LIST_URL,
    CrprojSource,
    cells_from_crproj,
    crproj_table_id,
    is_crproj_url,
    printed_item_url,
)

FDI_URL = "https://api.cristin.no/v2/projects/113"
VINJE_URL = "https://api.cristin.no/v2/projects/1234981"
UNIT_URL = "https://api.cristin.no/v2/units/1000.0.0.0"
INST_URL = "https://api.cristin.no/v2/institutions/1000"
DOCS_URL = "https://api.cristin.no/v2/"
UNDERENHET_URL = "https://data.brreg.no/enhetsregisteret/api/underenheter/933489272"
DATASET_ID = "crproj:1234981"

CATALOG = [
    {
        "cristin_project_id": "113",
        "title": {"en": "The Spatial Embeddedness of Foreign Direct Investment"},
        "url": FDI_URL,
    },
    {
        "cristin_project_id": "1234981",
        "title": {"nb": "Life and Death at Vinjefjorden"},
        "url": VINJE_URL,
    },
    {
        "title": {"nb": "missing id is skipped"},
        "url": "https://api.cristin.no/v2/projects/x",
    },
]
ITEM_BODY = {
    "cristin_project_id": "1234981",
    "title": {"nb": "Life and Death at Vinjefjorden"},
    "main_language": "nb",
    "status": "ACTIVE",
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
        if url == VINJE_URL:
            return JsonResponse(status=200, url=url, body=ITEM_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"crproj fetch must GET, not POST {url}")


def test_printed_refs_copy_project_ids() -> None:
    source = CrprojSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["113", "1234981"]
    assert [ref.source_native_uri for ref in refs] == [FDI_URL, VINJE_URL]
    assert all("/v2/projects/" in (ref.source_native_uri or "") for ref in refs)
    assert all("/v2/units/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/v2/institutions/" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_copies_printed_url() -> None:
    assert printed_item_url({"cristin_project_id": "1234981", "url": VINJE_URL}, LIST_URL) == VINJE_URL
    assert printed_item_url({"cristin_project_id": "1234981"}, LIST_URL) == VINJE_URL


def test_crproj_is_a_registered_source() -> None:
    assert "crproj" in SOURCE_IDS
    assert "crunit" in SOURCE_IDS
    assert "crinst" in SOURCE_IDS
    assert "cristin" in SOURCE_IDS
    assert "stsaker" in SOURCE_IDS
    assert "ssbsubj" in SOURCE_IDS
    assert "stkomiteer" in SOURCE_IDS
    assert "datanorge" in SOURCE_IDS
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
    assert SOURCE_IDS[-1] == "crperson"
    source = build_source("crproj")
    assert isinstance(source, CrprojSource)
    assert source.source_id == "crproj"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = CrprojSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "crproj"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == VINJE_URL
    assert row["title"] == "Life and Death at Vinjefjorden"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("cristin:")
    assert not str(row["id"]).startswith("crinst:")
    assert not str(row["id"]).startswith("crunit:")
    nxt = registry.get_dataset("crproj:113")
    assert nxt is not None
    assert nxt["title"] == "The Spatial Embeddedness of Foreign Direct Investment"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "1234981"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["crproj_project"]["cristin_project_id"] == "1234981"
    assert "url" not in payload["crproj_project"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_title(tmp_path: Path) -> None:
    source = CrprojSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == VINJE_URL
    assert result.table_id == "1234981"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["Life and Death at Vinjefjorden"]
    assert all(row["measure"] == "title" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["cristin_project_id"] == "1234981"
    assert dims["main_language"] == "nb"
    assert "url" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == VINJE_URL for row in rows)
    registry.close()


def test_cells_copy_printed_project() -> None:
    cells = cells_from_crproj(ITEM_BODY)
    assert cells == [
        (
            "title",
            "Life and Death at Vinjefjorden",
            {
                "cristin_project_id": "1234981",
                "main_language": "nb",
                "status": "ACTIVE",
            },
        )
    ]
    fallback = cells_from_crproj({"cristin_project_id": "1234981"})
    assert fallback == [("cristin_project_id", "1234981", {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_crproj(["1234981"])
    with pytest.raises(ValueError, match="project members"):
        cells_from_crproj({"url": VINJE_URL})


def test_is_crproj_url_accepts_only_project_item_paths() -> None:
    assert is_crproj_url(VINJE_URL)
    assert is_crproj_url(FDI_URL)
    assert not is_crproj_url(LIST_URL)
    assert crproj_table_id(VINJE_URL) == "1234981"
    assert not is_crproj_url(UNIT_URL)
    assert not is_crproj_url(INST_URL)
    assert not is_crproj_url(DOCS_URL)
    assert not is_crproj_url(UNDERENHET_URL)
    assert not is_crproj_url("https://data.norge.no/datasets/x")
    assert not is_crproj_url(None)


def test_limit_and_offset_slice_printed_projects() -> None:
    source = CrprojSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["113"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["1234981"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
