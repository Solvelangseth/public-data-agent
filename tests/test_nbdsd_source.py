from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.nbdsd import (
    LIST_URL,
    NbdsdSource,
    cells_from_nbdsd,
    is_nbdsd_url,
    nbdsd_table_id,
    printed_structure_url,
)

EXR_URL = "https://data.norges-bank.no/api/datastructure/NB/DSD_EXR?format=sdmx-json"
KPRA_URL = "https://data.norges-bank.no/api/datastructure/NB/DSD_ANN_KPRA?format=sdmx-json"
DATAFLOW_URL = "https://data.norges-bank.no/api/data/EXR?format=sdmx-json"
CODELIST_URL = "https://data.norges-bank.no/api/codelist/NB/CL_FREQ?format=sdmx-json"
DATASET_ID = "nbdsd:DSD_EXR"

CATALOG = {
    "meta": {"sender": {"id": "NB"}},
    "data": {
        "dataStructures": [
            {
                "id": "DSD_ANN_KPRA",
                "agencyID": "NB",
                "name": "Key policy rate announcement",
                "names": {
                    "en": "Key policy rate announcement",
                    "no": "Publisering av styringsrenten",
                },
            },
            {
                "id": "DSD_EXR",
                "agencyID": "NB",
                "name": "Exchange rates",
                "names": {"en": "Exchange rates", "no": "Valutakurser"},
                "description": "Exchange rate structure",
                "descriptions": {
                    "en": "Exchange rate structure",
                    "no": "Struktur for valutakurser",
                },
            },
            {
                "id": "DSD_FAUCTION",
                "agencyID": "NB",
                "name": "Announcements and results of F-auctions",
                "names": {
                    "en": "Announcements and results of F-auctions",
                    "no": "Kunngjøringer og resultater av F-auksjoner",
                },
            },
        ]
    },
}

EXR_BODY = {
    "data": {
        "dataStructures": [
            {
                "id": "DSD_EXR",
                "agencyID": "NB",
                "dataStructureComponents": {
                    "dimensionList": {
                        "dimensions": [
                            {
                                "id": "FREQ",
                                "position": 1,
                                "type": "Dimension",
                                "conceptIdentity": "urn:sdmx:org.sdmx.infomodel.conceptscheme.Concept=NB:CS_NB(1.0).FREQ",
                                "localRepresentation": {"skip": True},
                            }
                        ],
                        "timeDimensions": [
                            {
                                "id": "TIME_PERIOD",
                                "position": 2,
                                "type": "TimeDimension",
                            }
                        ],
                    },
                    "attributeList": {
                        "attributes": [
                            {
                                "id": "DECIMALS",
                                "assignmentStatus": "Mandatory",
                            }
                        ]
                    },
                    "measureList": {
                        "primaryMeasure": {"id": "OBS_VALUE"}
                    },
                },
            }
        ]
    }
}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None) -> dict:
        self.gets.append(url)
        if url == LIST_URL:
            return CATALOG
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == EXR_URL:
            return JsonResponse(status=200, url=url, body=EXR_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nbdsd fetch must GET, not POST {url}")


def test_printed_refs_copy_structure_ids() -> None:
    source = NbdsdSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "DSD_ANN_KPRA",
        "DSD_EXR",
        "DSD_FAUCTION",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        KPRA_URL,
        EXR_URL,
        "https://data.norges-bank.no/api/datastructure/NB/DSD_FAUCTION?format=sdmx-json",
    ]


def test_printed_url_joins_agency_and_id() -> None:
    item = CATALOG["data"]["dataStructures"][1]
    assert printed_structure_url(item, LIST_URL) == EXR_URL


def test_nbdsd_is_a_registered_source() -> None:
    assert "nbdsd" in SOURCE_IDS
    assert "norgesbank" in SOURCE_IDS
    assert "elcert" in SOURCE_IDS
    assert "frivillig" in SOURCE_IDS
    assert "sandnes" in SOURCE_IDS
    source = build_source("nbdsd")
    assert isinstance(source, NbdsdSource)
    assert source.source_id == "nbdsd"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = NbdsdSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nbdsd"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == EXR_URL
    assert row["title"] == "Valutakurser"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("norgesbank:")
    nxt = registry.get_dataset("nbdsd:DSD_ANN_KPRA")
    assert nxt is not None
    assert nxt["access_path"] == KPRA_URL
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["nbdsd_datastructure"]["id"] == "DSD_EXR"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_component_ids(tmp_path: Path) -> None:
    source = NbdsdSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == EXR_URL
    assert result.table_id == "DSD_EXR"
    assert result.http_status == 200
    assert result.counts.listed == 4
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"FREQ", "TIME_PERIOD", "DECIMALS", "OBS_VALUE"}
    assert all(row["measure"] == "id" for row in rows)
    dims = json.loads(by_value["FREQ"]["dimensions_json"])
    assert dims["position"] == "1"
    assert dims["type"] == "Dimension"
    assert "localRepresentation" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == EXR_URL for row in rows)
    registry.close()


def test_cells_copy_printed_component_ids() -> None:
    cells = cells_from_nbdsd(EXR_BODY)
    assert [value for _measure, value, _dims in cells] == [
        "FREQ",
        "TIME_PERIOD",
        "DECIMALS",
        "OBS_VALUE",
    ]
    measure, value, dims = cells[0]
    assert measure == "id"
    assert value == "FREQ"
    assert dims["type"] == "Dimension"
    assert "localRepresentation" not in dims
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_nbdsd([])
    with pytest.raises(ValueError, match="printed no structure components"):
        cells_from_nbdsd({"data": {"dataStructures": [{"dataStructureComponents": {}}]}})


def test_is_nbdsd_url_accepts_only_datastructure_path() -> None:
    assert is_nbdsd_url(EXR_URL)
    assert is_nbdsd_url(KPRA_URL)
    assert nbdsd_table_id(EXR_URL) == "DSD_EXR"
    assert nbdsd_table_id(KPRA_URL) == "DSD_ANN_KPRA"
    assert not is_nbdsd_url(DATAFLOW_URL)
    assert not is_nbdsd_url(CODELIST_URL)
    assert not is_nbdsd_url(LIST_URL)
    assert not is_nbdsd_url("https://data.norge.no/datasets/x")
    assert not is_nbdsd_url(None)


def test_limit_and_offset_slice_printed_structures() -> None:
    source = NbdsdSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "DSD_ANN_KPRA"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["DSD_EXR"]
