from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.nbagency import (
    LIST_URL,
    NbagencySource,
    cells_from_nbagency,
    is_nbagency_url,
    nbagency_table_id,
    printed_item_url,
)

SCHEME_URL = "https://data.norges-bank.no/api/agencyscheme/SDMX/AGENCIES?format=sdmx-json"
DATAFLOW_URL = "https://data.norges-bank.no/api/data/ANN_KPRA?format=sdmx-json"
CODELIST_URL = "https://data.norges-bank.no/api/codelist/NB/CL_FREQ?format=sdmx-json"
DSD_URL = "https://data.norges-bank.no/api/datastructure/NB/DSD_EXR?format=sdmx-json"
CONCEPT_URL = "https://data.norges-bank.no/api/conceptscheme/NB/CS_NB?format=sdmx-json"
DATASET_ID = "nbagency:AGENCIES"

CATALOG = {
    "meta": {"sender": {"id": "Unknown"}},
    "data": {
        "agencySchemes": [
            {
                "id": "AGENCIES",
                "agencyID": "SDMX",
                "name": "SDMX Agency Scheme",
                "names": {"en": "SDMX Agency Scheme"},
                "version": "1.0",
                "agencies": [{"id": "SDMX", "name": "SDMX"}],
            }
        ]
    },
}
SCHEME_BODY = {
    "meta": {"sender": {"id": "Unknown"}},
    "data": {
        "agencySchemes": [
            {
                "id": "AGENCIES",
                "agencyID": "SDMX",
                "name": "SDMX Agency Scheme",
                "agencies": [
                    {
                        "id": "SDMX",
                        "name": "SDMX",
                        "names": {"en": "SDMX"},
                    },
                    {
                        "id": "NB",
                        "name": "Norges Bank",
                        "names": {"en": "Norges Bank"},
                        "description": "Central Bank of Norway",
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
        if url == SCHEME_URL:
            return JsonResponse(status=200, url=url, body=SCHEME_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nbagency fetch must GET, not POST {url}")


def test_printed_refs_copy_agencyscheme_ids() -> None:
    source = NbagencySource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["AGENCIES"]
    assert [ref.source_native_uri for ref in refs] == [SCHEME_URL]
    assert all("/api/data/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/api/codelist" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/api/datastructure" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/api/conceptscheme" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_joins_printed_agency_and_id() -> None:
    assert printed_item_url({"id": "AGENCIES", "agencyID": "SDMX"}, LIST_URL) == SCHEME_URL


def test_nbagency_is_a_registered_source() -> None:
    assert "nbagency" in SOURCE_IDS
    assert "norgesbank" in SOURCE_IDS
    assert "nbcodelist" in SOURCE_IDS
    assert "nbdsd" in SOURCE_IDS
    assert "nbconcept" in SOURCE_IDS
    assert "ssbfam" in SOURCE_IDS
    assert "ssbsec" in SOURCE_IDS
    assert "ssclass" in SOURCE_IDS
    assert "banegis" in SOURCE_IDS
    assert "mattilsyn" in SOURCE_IDS
    assert "nibiorest" in SOURCE_IDS
    assert "nbprov" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("nbprov") + 1] == "nbagency"
    source = build_source("nbagency")
    assert isinstance(source, NbagencySource)
    assert source.source_id == "nbagency"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = NbagencySource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nbagency"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == SCHEME_URL
    assert row["title"] == "SDMX Agency Scheme"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("norgesbank:")
    assert not str(row["id"]).startswith("nbconcept:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "AGENCIES"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["nbagency_agencyscheme"]["id"] == "AGENCIES"
    assert "agencies" not in payload["nbagency_agencyscheme"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_agency_names(tmp_path: Path) -> None:
    source = NbagencySource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == SCHEME_URL
    assert result.table_id == "AGENCIES"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert set(values) == {"SDMX", "Norges Bank"}
    assert all(row["measure"] == "name" for row in rows)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    dims = json.loads(by_value["Norges Bank"]["dimensions_json"])
    assert dims["id"] == "NB"
    assert dims["description"] == "Central Bank of Norway"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == SCHEME_URL for row in rows)
    registry.close()


def test_cells_copy_printed_agencies() -> None:
    cells = cells_from_nbagency(SCHEME_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "SDMX"
    assert dims["id"] == "SDMX"
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_nbagency(["SDMX"])
    with pytest.raises(ValueError, match="agencies"):
        cells_from_nbagency({"data": {"agencySchemes": [{"id": "AGENCIES"}]}})


def test_is_nbagency_url_accepts_only_agencyscheme_paths() -> None:
    assert is_nbagency_url(SCHEME_URL)
    assert nbagency_table_id(SCHEME_URL) == "AGENCIES"
    assert is_nbagency_url(LIST_URL)
    assert not is_nbagency_url(DATAFLOW_URL)
    assert not is_nbagency_url(CODELIST_URL)
    assert not is_nbagency_url(DSD_URL)
    assert not is_nbagency_url(CONCEPT_URL)
    assert not is_nbagency_url("https://data.norges-bank.no/api")
    assert not is_nbagency_url("https://www.norges-bank.no/api/agencyscheme/SDMX/AGENCIES")
    assert not is_nbagency_url(None)


def test_limit_and_offset_slice_printed_schemes() -> None:
    source = NbagencySource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["AGENCIES"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert nxt == []
