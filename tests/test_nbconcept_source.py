from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.nbconcept import (
    LIST_URL,
    NbconceptSource,
    cells_from_nbconcept,
    is_nbconcept_url,
    nbconcept_table_id,
    printed_item_url,
)

CS_URL = "https://data.norges-bank.no/api/conceptscheme/NB/CS_NB?format=sdmx-json"
DATAFLOW_URL = "https://data.norges-bank.no/api/data/ANN_KPRA?format=sdmx-json"
CODELIST_URL = "https://data.norges-bank.no/api/codelist/NB/CL_FREQ?format=sdmx-json"
DSD_URL = "https://data.norges-bank.no/api/datastructure/NB/DSD_EXR?format=sdmx-json"
DATASET_ID = "nbconcept:CS_NB"

CATALOG = {
    "meta": {"sender": {"id": "Unknown"}},
    "data": {
        "conceptSchemes": [
            {
                "id": "CS_NB",
                "agencyID": "NB",
                "name": "Norges Bank common concepts",
                "names": {
                    "en": "Norges Bank common concepts",
                    "no": "Norges Bank konsepter",
                },
                "description": "Shared SDMX concepts",
                "descriptions": {
                    "en": "Shared SDMX concepts",
                    "no": "Felles SDMX-konsepter",
                },
                "version": "1.0",
                "concepts": [{"id": "FREQ", "name": "Frequency"}],
            }
        ]
    },
}
CS_BODY = {
    "meta": {"sender": {"id": "Unknown"}},
    "data": {
        "conceptSchemes": [
            {
                "id": "CS_NB",
                "agencyID": "NB",
                "name": "Norges Bank common concepts",
                "concepts": [
                    {
                        "id": "TIME_PERIOD",
                        "name": "Time Period",
                        "names": {"en": "Time Period", "no": "Tidsperiode"},
                        "description": "Reference period",
                    },
                    {
                        "id": "FREQ",
                        "name": "Frequency",
                        "names": {"en": "Frequency", "no": "Frekvens"},
                    },
                ],
            }
        ]
    },
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
        if url == CS_URL:
            return JsonResponse(status=200, url=url, body=CS_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nbconcept fetch must GET, not POST {url}")


def test_printed_refs_copy_conceptscheme_ids() -> None:
    source = NbconceptSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["CS_NB"]
    assert [ref.source_native_uri for ref in refs] == [CS_URL]
    assert all("/api/data/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/api/codelist" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/api/datastructure" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_joins_printed_agency_and_id() -> None:
    assert printed_item_url({"id": "CS_NB", "agencyID": "NB"}, LIST_URL) == CS_URL


def test_nbconcept_is_a_registered_source() -> None:
    assert "nbconcept" in SOURCE_IDS
    assert "norgesbank" in SOURCE_IDS
    source = build_source("nbconcept")
    assert isinstance(source, NbconceptSource)
    assert source.source_id == "nbconcept"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = NbconceptSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nbconcept"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == CS_URL
    assert row["title"] == "Norges Bank konsepter"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("norgesbank:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "CS_NB"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["nbconcept_conceptscheme"]["id"] == "CS_NB"
    assert "concepts" not in payload["nbconcept_conceptscheme"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_concept_names(tmp_path: Path) -> None:
    source = NbconceptSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == CS_URL
    assert result.table_id == "CS_NB"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert set(values) == {"Time Period", "Frequency"}
    assert all(row["measure"] == "name" for row in rows)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    dims = json.loads(by_value["Time Period"]["dimensions_json"])
    assert dims["id"] == "TIME_PERIOD"
    assert dims["description"] == "Reference period"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == CS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_concepts() -> None:
    cells = cells_from_nbconcept(CS_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "Time Period"
    assert dims["id"] == "TIME_PERIOD"
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_nbconcept(["Time Period"])


def test_is_nbconcept_url_accepts_only_conceptscheme_paths() -> None:
    assert is_nbconcept_url(CS_URL)
    assert nbconcept_table_id(CS_URL) == "CS_NB"
    assert is_nbconcept_url(LIST_URL)
    assert not is_nbconcept_url(DATAFLOW_URL)
    assert not is_nbconcept_url(CODELIST_URL)
    assert not is_nbconcept_url(DSD_URL)
    assert not is_nbconcept_url("https://data.norges-bank.no/api")
    assert not is_nbconcept_url("https://www.norges-bank.no/api/conceptscheme/NB/CS_NB")
    assert not is_nbconcept_url(None)


def test_limit_and_offset_slice_printed_schemes() -> None:
    source = NbconceptSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["CS_NB"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert nxt == []
