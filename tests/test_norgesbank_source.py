from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.norgesbank import (
    LIST_URL,
    NorgesBankSource,
    cells_from_norgesbank,
    is_norgesbank_url,
    norgesbank_table_id,
    printed_data_url,
)

ANN_KPRA_URL = "https://data.norges-bank.no/api/data/ANN_KPRA?format=sdmx-json"
EXR_URL = "https://data.norges-bank.no/api/data/EXR?format=sdmx-json"
DATASET_ID = "norgesbank:ANN_KPRA"

CATALOG = {
    "meta": {"sender": {"id": "Unknown"}},
    "data": {
        "dataflows": [
            {
                "id": "ANN_FX_SPU",
                "name": "Announcement of foreign exchange transactions on behalf of SPU",
                "names": {
                    "en": "Announcement of foreign exchange transactions on behalf of SPU",
                    "no": "Annonsering av valutatransaksjoner for SPU",
                },
            },
            {
                "id": "ANN_KPRA",
                "name": "Key policy rate announcement",
                "names": {
                    "en": "Key policy rate announcement",
                    "no": "Publisering av styringsrenten",
                },
                "description": "Norges Banks announcements of key policy rate decisions",
                "descriptions": {
                    "en": "Norges Banks announcements of key policy rate decisions",
                    "no": "Norges Banks annonseringer av rentebeslutninger",
                },
                "version": "1.0",
                "agencyID": "NB",
            },
            {
                "id": "EXR",
                "name": "Exchange rates",
                "names": {"en": "Exchange rates", "no": "Valutakurser"},
            },
        ]
    },
}
ANN_KPRA_BODY = {
    "meta": {
        "links": [
            {
                "rel": "self",
                "href": "/data/ANN_KPRA?format=sdmx-json",
            }
        ]
    },
    "data": {
        "dataSets": [
            {
                "series": {
                    "0": {
                        "observations": {
                            "0": ["13.00", 0],
                            "1": ["4.25", 1],
                        }
                    }
                }
            }
        ],
        "structure": {
            "name": "Key policy rate announcement",
            "names": {
                "en": "Key policy rate announcement",
                "no": "Publisering av styringsrenten",
            },
            "dimensions": {
                "series": [
                    {
                        "id": "INSTRUMENT_TYPE",
                        "name": "Instrument Type",
                        "values": [
                            {
                                "id": "KPRA",
                                "name": "Key policy rate",
                            }
                        ],
                    }
                ],
                "observation": [
                    {
                        "id": "TIME_PERIOD",
                        "name": "Announcement date",
                        "values": [
                            {"id": "1986-01-13", "name": "1986-01-13"},
                            {"id": "2026-08-13", "name": "2026-08-13"},
                        ],
                    }
                ],
            },
        },
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
        if url == ANN_KPRA_URL:
            return JsonResponse(status=200, url=url, body=ANN_KPRA_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"norgesbank fetch must GET, not POST {url}")


def test_printed_refs_copy_dataflow_ids() -> None:
    source = NorgesBankSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["ANN_FX_SPU", "ANN_KPRA", "EXR"]
    assert [ref.source_native_uri for ref in refs] == [
        "https://data.norges-bank.no/api/data/ANN_FX_SPU?format=sdmx-json",
        ANN_KPRA_URL,
        EXR_URL,
    ]
    assert all("dataflow" not in (ref.source_native_uri or "") for ref in refs)


def test_data_url_joins_printed_id_to_api_data() -> None:
    assert printed_data_url("ANN_KPRA", LIST_URL) == ANN_KPRA_URL


def test_norgesbank_is_a_registered_source() -> None:
    assert "norgesbank" in SOURCE_IDS
    source = build_source("norgesbank")
    assert isinstance(source, NorgesBankSource)
    assert source.source_id == "norgesbank"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = NorgesBankSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "norgesbank"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == ANN_KPRA_URL
    assert row["title"] == "Publisering av styringsrenten"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("nbr:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "ANN_KPRA"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["norgesbank_dataflow"]["id"] == "ANN_KPRA"
    registry.close()


def test_fetch_gets_printed_ann_kpra(tmp_path: Path) -> None:
    source = NorgesBankSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == ANN_KPRA_URL
    assert result.table_id == "ANN_KPRA"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["13.00", "4.25"] or values == ["4.25", "13.00"]
    assert all(row["measure"] == "Key policy rate" for row in rows)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    dims = json.loads(by_value["13.00"]["dimensions_json"])
    assert dims["TIME_PERIOD"] == "1986-01-13"
    assert "INSTRUMENT_TYPE" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == ANN_KPRA_URL for row in rows)
    registry.close()


def test_cells_copy_printed_sdmx_observations() -> None:
    cells = cells_from_norgesbank(ANN_KPRA_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "Key policy rate"
    assert value == "13.00"
    assert dims == {"TIME_PERIOD": "1986-01-13"}
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_norgesbank(["13.00"])


def test_is_norgesbank_url_accepts_only_data_paths() -> None:
    assert is_norgesbank_url(ANN_KPRA_URL)
    assert norgesbank_table_id(ANN_KPRA_URL) == "ANN_KPRA"
    assert not is_norgesbank_url(LIST_URL)
    assert not is_norgesbank_url("https://data.norges-bank.no/api")
    assert not is_norgesbank_url("https://www.norges-bank.no/api/data/ANN_KPRA")
    assert not is_norgesbank_url("https://data-nbr.udir.no/v3/barnehagekategorier")
    assert not is_norgesbank_url(None)


def test_limit_and_offset_slice_printed_dataflows() -> None:
    source = NorgesBankSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=2)] == [
        "ANN_FX_SPU",
        "ANN_KPRA",
    ]
    nxt = source.list_dataset_refs(limit=1, offset=2)
    assert [ref.source_native_id for ref in nxt] == ["EXR"]
