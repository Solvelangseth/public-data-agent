from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.crpers import (
    LIST_URL,
    CrpersSource,
    cells_from_crpers,
    crpers_table_id,
    is_crpers_url,
    printed_item_url,
)

ABABIO_URL = "https://api.cristin.no/v2/persons/1765108"
ABABRI_URL = "https://api.cristin.no/v2/persons/1805404"
UNIT_URL = "https://api.cristin.no/v2/units/1000.0.0.0"
INST_URL = "https://api.cristin.no/v2/institutions/1000"
BIO_URL = "https://api.cristin.no/v2/biobanks/2052825"
PROJ_URL = "https://api.cristin.no/v2/projects/113"
DOCS_URL = "https://api.cristin.no/v2/"
DATASET_ID = "crpers:1765108"

CATALOG = [
    {
        "cristin_person_id": "1765108",
        "first_name": "Paul Nti",
        "surname": "Ababio",
        "url": ABABIO_URL,
    },
    {
        "cristin_person_id": "1805404",
        "first_name": "Yassine",
        "surname": "Ababri",
        "url": ABABRI_URL,
    },
    {
        "first_name": "missing id is skipped",
        "url": "https://api.cristin.no/v2/persons/x",
    },
]
ITEM_BODY = {
    "cristin_person_id": "1765108",
    "first_name": "Paul Nti",
    "surname": "Ababio",
    "identified_cristin_person": True,
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
        if url == ABABIO_URL:
            return JsonResponse(status=200, url=url, body=ITEM_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"crpers fetch must GET, not POST {url}")


def test_printed_refs_copy_person_ids() -> None:
    source = CrpersSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["1765108", "1805404"]
    assert [ref.source_native_uri for ref in refs] == [ABABIO_URL, ABABRI_URL]
    assert all("/v2/persons/" in (ref.source_native_uri or "") for ref in refs)
    assert all("/v2/units/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/v2/institutions/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/v2/biobanks/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/v2/projects/" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_copies_printed_url() -> None:
    assert printed_item_url({"cristin_person_id": "1765108", "url": ABABIO_URL}, LIST_URL) == ABABIO_URL
    assert printed_item_url({"cristin_person_id": "1765108"}, LIST_URL) == ABABIO_URL


def test_crpers_is_a_registered_source() -> None:
    assert "crpers" in SOURCE_IDS
    assert "crbio" in SOURCE_IDS
    assert "crproj" in SOURCE_IDS
    assert "crunit" in SOURCE_IDS
    assert "crinst" in SOURCE_IDS
    assert "cristin" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("stpartier") + 1] == "crbio"
    assert SOURCE_IDS[SOURCE_IDS.index("crbio") + 1] == "nibioar5f"
    assert SOURCE_IDS[SOURCE_IDS.index("nibioar5f") + 1] == "crpers"
    assert SOURCE_IDS[-1] == "crpers"
    source = build_source("crpers")
    assert isinstance(source, CrpersSource)
    assert source.source_id == "crpers"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = CrpersSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "crpers"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == ABABIO_URL
    assert row["title"] == "Paul Nti Ababio"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("crbio:")
    assert not str(row["id"]).startswith("crunit:")
    assert not str(row["id"]).startswith("crinst:")
    assert not str(row["id"]).startswith("crproj:")
    assert not str(row["id"]).startswith("cristin:")
    nxt = registry.get_dataset("crpers:1805404")
    assert nxt is not None
    assert nxt["title"] == "Yassine Ababri"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "1765108"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["crpers_person"]["cristin_person_id"] == "1765108"
    assert "url" not in payload["crpers_person"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_person_name(tmp_path: Path) -> None:
    source = CrpersSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == ABABIO_URL
    assert result.table_id == "1765108"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["Paul Nti"]
    assert all(row["measure"] == "first_name" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["cristin_person_id"] == "1765108"
    assert dims["surname"] == "Ababio"
    assert "url" not in dims
    assert "affiliations" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == ABABIO_URL for row in rows)
    registry.close()


def test_cells_copy_printed_person() -> None:
    cells = cells_from_crpers(ITEM_BODY)
    assert cells == [
        (
            "first_name",
            "Paul Nti",
            {
                "cristin_person_id": "1765108",
                "surname": "Ababio",
                "identified_cristin_person": "True",
            },
        )
    ]
    fallback = cells_from_crpers({"cristin_person_id": "1765108"})
    assert fallback == [("cristin_person_id", "1765108", {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_crpers(["1765108"])
    with pytest.raises(ValueError, match="person members"):
        cells_from_crpers({"url": ABABIO_URL})


def test_is_crpers_url_accepts_only_person_item_paths() -> None:
    assert is_crpers_url(ABABIO_URL)
    assert is_crpers_url(ABABRI_URL)
    assert not is_crpers_url(LIST_URL)
    assert crpers_table_id(ABABIO_URL) == "1765108"
    assert not is_crpers_url(UNIT_URL)
    assert not is_crpers_url(INST_URL)
    assert not is_crpers_url(BIO_URL)
    assert not is_crpers_url(PROJ_URL)
    assert not is_crpers_url(DOCS_URL)
    assert not is_crpers_url("https://data.norge.no/datasets/x")
    assert not is_crpers_url(None)


def test_limit_and_offset_slice_printed_persons() -> None:
    source = CrpersSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["1765108"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["1805404"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
