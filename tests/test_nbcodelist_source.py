from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.nbcodelist import (
    LIST_URL,
    NbcodelistSource,
    cells_from_nbcodelist,
    is_nbcodelist_url,
    nbcodelist_table_id,
    printed_item_url,
)

FREQ_URL = "https://data.norges-bank.no/api/codelist/NB/CL_FREQ?format=sdmx-json"
CURRENCY_URL = "https://data.norges-bank.no/api/codelist/NB/CL_CURRENCY?format=sdmx-json"
DATAFLOW_URL = "https://data.norges-bank.no/api/data/ANN_KPRA?format=sdmx-json"
DATASET_ID = "nbcodelist:CL_FREQ"

CATALOG = {
    "meta": {"sender": {"id": "Unknown"}},
    "data": {
        "codelists": [
            {
                "id": "CALC_METHOD",
                "agencyID": "NB",
                "name": "Calculation Method",
                "names": {"en": "Calculation Method"},
            },
            {
                "id": "CL_FREQ",
                "agencyID": "NB",
                "name": "Frequency",
                "names": {"en": "Frequency", "no": "Frekvens"},
                "description": "Time frequency codes",
                "descriptions": {
                    "en": "Time frequency codes",
                    "no": "Koder for tidsfrekvens",
                },
                "version": "1.0",
                "codes": [
                    {"id": "A", "name": "Annual"},
                ],
            },
            {
                "id": "CL_CURRENCY",
                "agencyID": "NB",
                "name": "Currency",
                "names": {"en": "Currency", "no": "Valuta"},
            },
        ]
    },
}
FREQ_BODY = {
    "meta": {"sender": {"id": "Unknown"}},
    "data": {
        "codelists": [
            {
                "id": "CL_FREQ",
                "agencyID": "NB",
                "name": "Frequency",
                "codes": [
                    {
                        "id": "A",
                        "name": "Annual",
                        "names": {"en": "Annual", "no": "Årlig"},
                        "description": "Annual frequency",
                    },
                    {
                        "id": "Q",
                        "name": "Quarterly",
                        "names": {"en": "Quarterly", "no": "Kvartal"},
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
        if url == FREQ_URL:
            return JsonResponse(status=200, url=url, body=FREQ_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nbcodelist fetch must GET, not POST {url}")


def test_printed_refs_copy_codelist_ids() -> None:
    source = NbcodelistSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "CALC_METHOD",
        "CL_FREQ",
        "CL_CURRENCY",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        "https://data.norges-bank.no/api/codelist/NB/CALC_METHOD?format=sdmx-json",
        FREQ_URL,
        CURRENCY_URL,
    ]
    assert all("/api/data/" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_joins_printed_agency_and_id() -> None:
    assert (
        printed_item_url({"id": "CL_FREQ", "agencyID": "NB"}, LIST_URL) == FREQ_URL
    )


def test_nbcodelist_is_a_registered_source() -> None:
    assert "nbcodelist" in SOURCE_IDS
    assert "norgesbank" in SOURCE_IDS
    source = build_source("nbcodelist")
    assert isinstance(source, NbcodelistSource)
    assert source.source_id == "nbcodelist"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = NbcodelistSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nbcodelist"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == FREQ_URL
    assert row["title"] == "Frekvens"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("norgesbank:")
    nxt = registry.get_dataset("nbcodelist:CL_CURRENCY")
    assert nxt is not None
    assert nxt["access_path"] == CURRENCY_URL
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "CL_FREQ"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["nbcodelist_codelist"]["id"] == "CL_FREQ"
    assert "codes" not in payload["nbcodelist_codelist"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_code_names(tmp_path: Path) -> None:
    source = NbcodelistSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == FREQ_URL
    assert result.table_id == "CL_FREQ"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert set(values) == {"Annual", "Quarterly"}
    assert all(row["measure"] == "name" for row in rows)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    dims = json.loads(by_value["Annual"]["dimensions_json"])
    assert dims["id"] == "A"
    assert dims["description"] == "Annual frequency"
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == FREQ_URL for row in rows)
    registry.close()


def test_cells_copy_printed_codes() -> None:
    cells = cells_from_nbcodelist(FREQ_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "Annual"
    assert dims["id"] == "A"
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_nbcodelist(["Annual"])


def test_is_nbcodelist_url_accepts_only_codelist_paths() -> None:
    assert is_nbcodelist_url(FREQ_URL)
    assert nbcodelist_table_id(FREQ_URL) == "CL_FREQ"
    assert is_nbcodelist_url(LIST_URL)
    assert not is_nbcodelist_url(DATAFLOW_URL)
    assert not is_nbcodelist_url("https://data.norges-bank.no/api")
    assert not is_nbcodelist_url("https://www.norges-bank.no/api/codelist/NB/CL_FREQ")
    assert not is_nbcodelist_url(None)


def test_limit_and_offset_slice_printed_codelists() -> None:
    source = NbcodelistSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=2)] == [
        "CALC_METHOD",
        "CL_FREQ",
    ]
    nxt = source.list_dataset_refs(limit=1, offset=2)
    assert [ref.source_native_id for ref in nxt] == ["CL_CURRENCY"]
