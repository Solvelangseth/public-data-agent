from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.crresult import (
    LIST_URL,
    CrresultSource,
    cells_from_crresult,
    crresult_table_id,
    is_crresult_url,
    printed_item_url,
)

ACTS_URL = "https://api.cristin.no/v2/results/1903021"
LANDSTAD_URL = "https://api.cristin.no/v2/results/10001604"
UNIT_URL = "https://api.cristin.no/v2/units/1000.0.0.0"
INST_URL = "https://api.cristin.no/v2/institutions/1000"
BIO_URL = "https://api.cristin.no/v2/biobanks/2052825"
PROJ_URL = "https://api.cristin.no/v2/projects/113"
PERSON_URL = "https://api.cristin.no/v2/persons/1765108"
DOCS_URL = "https://api.cristin.no/v2/"
DATASET_ID = "crresult:1903021"

CATALOG = [
    {
        "cristin_result_id": "1903021",
        "title": {"en": "Considerations about the Theological Meaning of Migration in the Book of Acts"},
        "year_published": "2021",
        "url": ACTS_URL,
    },
    {
        "cristin_result_id": "10001604",
        "title": {"nb": "Eskatologien i Landstads salmer"},
        "year_published": "2013",
        "url": LANDSTAD_URL,
    },
    {
        "title": {"nb": "missing id is skipped"},
        "url": "https://api.cristin.no/v2/results/x",
    },
]
ITEM_BODY = {
    "cristin_result_id": "1903021",
    "title": {"en": "Considerations about the Theological Meaning of Migration in the Book of Acts"},
    "year_published": "2021",
    "original_language": "en",
    "url": ACTS_URL,
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
        if url == ACTS_URL:
            return JsonResponse(status=200, url=url, body=ITEM_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"crresult fetch must GET, not POST {url}")


def test_printed_refs_copy_result_ids() -> None:
    source = CrresultSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["1903021", "10001604"]
    assert [ref.source_native_uri for ref in refs] == [ACTS_URL, LANDSTAD_URL]
    assert all("/v2/results/" in (ref.source_native_uri or "") for ref in refs)
    assert all("/v2/units/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/v2/institutions/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/v2/biobanks/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/v2/projects/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/v2/persons/" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_copies_printed_url() -> None:
    assert printed_item_url({"cristin_result_id": "1903021", "url": ACTS_URL}, LIST_URL) == ACTS_URL
    assert printed_item_url({"cristin_result_id": "1903021"}, LIST_URL) == ACTS_URL


def test_crresult_is_a_registered_source() -> None:
    assert "crresult" in SOURCE_IDS
    assert "crbio" in SOURCE_IDS
    assert "crproj" in SOURCE_IDS
    assert "crunit" in SOURCE_IDS
    assert "crinst" in SOURCE_IDS
    assert "cristin" in SOURCE_IDS
    assert "kvfkb" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("crbio") + 1] == "nibioar5f"
    assert SOURCE_IDS[SOURCE_IDS.index("nibioar5f") + 1] == "kvfkb"
    assert SOURCE_IDS[SOURCE_IDS.index("kvfkb") + 1] == "crperson"
    assert SOURCE_IDS[SOURCE_IDS.index("crperson") + 1] == "stsporre"
    assert SOURCE_IDS[SOURCE_IDS.index("stsporre") + 1] == "crresult"
    assert SOURCE_IDS[SOURCE_IDS.index("crresult") + 1] == "stmoter"
    assert SOURCE_IDS[SOURCE_IDS.index("stmoter") + 1] == "ssbfritid"
    assert SOURCE_IDS[SOURCE_IDS.index("ssbfritid") + 1] == "kvadm"
    assert SOURCE_IDS[-1] == "kvadm"
    source = build_source("crresult")
    assert isinstance(source, CrresultSource)
    assert source.source_id == "crresult"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = CrresultSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "crresult"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == ACTS_URL
    assert row["title"] == "Considerations about the Theological Meaning of Migration in the Book of Acts"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("crbio:")
    assert not str(row["id"]).startswith("crunit:")
    assert not str(row["id"]).startswith("crinst:")
    assert not str(row["id"]).startswith("crproj:")
    assert not str(row["id"]).startswith("cristin:")
    nxt = registry.get_dataset("crresult:10001604")
    assert nxt is not None
    assert nxt["title"] == "Eskatologien i Landstads salmer"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "1903021"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["crresult_result"]["cristin_result_id"] == "1903021"
    assert "url" not in payload["crresult_result"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_result_title(tmp_path: Path) -> None:
    source = CrresultSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == ACTS_URL
    assert result.table_id == "1903021"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["Considerations about the Theological Meaning of Migration in the Book of Acts"]
    assert all(row["measure"] == "title" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["cristin_result_id"] == "1903021"
    assert dims["year_published"] == "2021"
    assert "url" not in dims
    assert "contributors" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == ACTS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_result() -> None:
    cells = cells_from_crresult(ITEM_BODY)
    assert cells == [
        (
            "title",
            "Considerations about the Theological Meaning of Migration in the Book of Acts",
            {
                "cristin_result_id": "1903021",
                "year_published": "2021",
                "original_language": "en",
            },
        )
    ]
    fallback = cells_from_crresult({"cristin_result_id": "1903021"})
    assert fallback == [("cristin_result_id", "1903021", {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_crresult(["1903021"])
    with pytest.raises(ValueError, match="result members"):
        cells_from_crresult({"url": ACTS_URL})


def test_is_crresult_url_accepts_only_result_item_paths() -> None:
    assert is_crresult_url(ACTS_URL)
    assert is_crresult_url(LANDSTAD_URL)
    assert not is_crresult_url(LIST_URL)
    assert crresult_table_id(ACTS_URL) == "1903021"
    assert not is_crresult_url(UNIT_URL)
    assert not is_crresult_url(INST_URL)
    assert not is_crresult_url(BIO_URL)
    assert not is_crresult_url(PROJ_URL)
    assert not is_crresult_url(PERSON_URL)
    assert not is_crresult_url(DOCS_URL)
    assert not is_crresult_url("https://data.norge.no/datasets/x")
    assert not is_crresult_url(None)


def test_limit_and_offset_slice_printed_results() -> None:
    source = CrresultSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["1903021"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["10001604"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
