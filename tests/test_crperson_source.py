from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.crperson import (
    LIST_URL,
    CrpersonSource,
    cells_from_crperson,
    crperson_table_id,
    is_crperson_url,
    printed_item_url,
)

ABABIO_URL = "https://api.cristin.no/v2/persons/1765108"
ABABRI_URL = "https://api.cristin.no/v2/persons/1805404"
UNIT_URL = "https://api.cristin.no/v2/units/1000.0.0.0"
INST_URL = "https://api.cristin.no/v2/institutions/1000"
PROJ_URL = "https://api.cristin.no/v2/projects/1234981"
DOCS_URL = "https://api.cristin.no/v2/"
UNDERENHET_URL = "https://data.brreg.no/enhetsregisteret/api/underenheter/933489272"
DATASET_ID = "crperson:1805404"

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
    "cristin_person_id": "1805404",
    "first_name": "Yassine",
    "surname": "Ababri",
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
        if url == ABABRI_URL:
            return JsonResponse(status=200, url=url, body=ITEM_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"crperson fetch must GET, not POST {url}")


def test_printed_refs_copy_person_ids() -> None:
    source = CrpersonSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["1765108", "1805404"]
    assert [ref.source_native_uri for ref in refs] == [ABABIO_URL, ABABRI_URL]
    assert all("/v2/persons/" in (ref.source_native_uri or "") for ref in refs)
    assert all("/v2/units/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/v2/institutions/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/v2/projects/" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_copies_printed_url() -> None:
    assert printed_item_url({"cristin_person_id": "1805404", "url": ABABRI_URL}, LIST_URL) == ABABRI_URL
    assert printed_item_url({"cristin_person_id": "1805404"}, LIST_URL) == ABABRI_URL


def test_crperson_is_a_registered_source() -> None:
    assert "crperson" in SOURCE_IDS
    assert "crproj" in SOURCE_IDS
    assert "crunit" in SOURCE_IDS
    assert "crinst" in SOURCE_IDS
    assert "cristin" in SOURCE_IDS
    assert "datanorge" in SOURCE_IDS
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
    assert SOURCE_IDS[SOURCE_IDS.index("dsbgis") + 1] == "nibiogard"
    assert SOURCE_IDS[SOURCE_IDS.index("nibiogard") + 1] == "stskrift"
    assert SOURCE_IDS[SOURCE_IDS.index("stskrift") + 1] == "stinterp"
    assert SOURCE_IDS[-1] == "stinterp"
    source = build_source("crperson")
    assert isinstance(source, CrpersonSource)
    assert source.source_id == "crperson"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = CrpersonSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "crperson"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == ABABRI_URL
    assert row["title"] == "Yassine Ababri"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("cristin:")
    assert not str(row["id"]).startswith("crinst:")
    assert not str(row["id"]).startswith("crunit:")
    assert not str(row["id"]).startswith("crproj:")
    nxt = registry.get_dataset("crperson:1765108")
    assert nxt is not None
    assert nxt["title"] == "Paul Nti Ababio"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "1805404"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["crperson_person"]["cristin_person_id"] == "1805404"
    assert "url" not in payload["crperson_person"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_first_name(tmp_path: Path) -> None:
    source = CrpersonSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == ABABRI_URL
    assert result.table_id == "1805404"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["Yassine"]
    assert all(row["measure"] == "first_name" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["cristin_person_id"] == "1805404"
    assert dims["surname"] == "Ababri"
    assert "url" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == ABABRI_URL for row in rows)
    registry.close()


def test_cells_copy_printed_person() -> None:
    cells = cells_from_crperson(ITEM_BODY)
    assert cells == [
        (
            "first_name",
            "Yassine",
            {
                "cristin_person_id": "1805404",
                "surname": "Ababri",
                "identified_cristin_person": "True",
            },
        )
    ]
    fallback = cells_from_crperson({"cristin_person_id": "1805404"})
    assert fallback == [("cristin_person_id", "1805404", {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_crperson(["1805404"])
    with pytest.raises(ValueError, match="person members"):
        cells_from_crperson({"url": ABABRI_URL})


def test_is_crperson_url_accepts_only_person_item_paths() -> None:
    assert is_crperson_url(ABABRI_URL)
    assert is_crperson_url(ABABIO_URL)
    assert not is_crperson_url(LIST_URL)
    assert crperson_table_id(ABABRI_URL) == "1805404"
    assert not is_crperson_url(UNIT_URL)
    assert not is_crperson_url(INST_URL)
    assert not is_crperson_url(PROJ_URL)
    assert not is_crperson_url(DOCS_URL)
    assert not is_crperson_url(UNDERENHET_URL)
    assert not is_crperson_url("https://data.norge.no/datasets/x")
    assert not is_crperson_url(None)


def test_limit_and_offset_slice_printed_persons() -> None:
    source = CrpersonSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["1765108"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["1805404"]
    assert source.list_dataset_refs(limit=1, offset=2) == []
