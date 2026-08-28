from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.nbprov import (
    LIST_URL,
    NbprovSource,
    cells_from_nbprov,
    is_nbprov_url,
    nbprov_table_id,
    printed_item_url,
)

EXR_URL = "https://data.norges-bank.no/api/provisionagreement/NB/EXR_NB_NB?format=sdmx-json"
KPRA_URL = (
    "https://data.norges-bank.no/api/provisionagreement/NB/ANN_KPRA_NB_NB?format=sdmx-json"
)
DATAFLOW_URL = "https://data.norges-bank.no/api/data/EXR?format=sdmx-json"
CODELIST_URL = "https://data.norges-bank.no/api/codelist/NB/CL_FREQ?format=sdmx-json"
DSD_URL = "https://data.norges-bank.no/api/datastructure/NB/DSD_EXR?format=sdmx-json"
CONCEPT_URL = "https://data.norges-bank.no/api/conceptscheme/NB/CS_NB?format=sdmx-json"
DATASET_ID = "nbprov:EXR_NB_NB"

CATALOG = {
    "meta": {"sender": {"id": "Unknown"}},
    "data": {
        "provisionAgreements": [
            {
                "id": "ANN_KPRA_NB_NB",
                "agencyID": "NB",
                "name": "Norges Bank for Key policy rate announcement",
                "names": {"en": "Norges Bank for Key policy rate announcement"},
            },
            {
                "id": "EXR_NB_NB",
                "agencyID": "NB",
                "name": "Norges Bank for Exchange rates",
                "names": {"en": "Norges Bank for Exchange rates"},
                "description": "Exchange rate provision agreement",
                "descriptions": {
                    "en": "Exchange rate provision agreement",
                },
                "version": "1.0",
            },
            {
                "id": "IR_NB_NB",
                "agencyID": "NB",
                "name": "Norges Bank for Interest rates",
                "names": {"en": "Norges Bank for Interest rates"},
            },
        ]
    },
}
EXR_BODY = {
    "meta": {"sender": {"id": "Unknown"}},
    "data": {
        "provisionAgreements": [
            {
                "id": "EXR_NB_NB",
                "agencyID": "NB",
                "name": "Norges Bank for Exchange rates",
                "names": {"en": "Norges Bank for Exchange rates"},
                "version": "1.0",
                "isFinal": False,
                "structureUsage": "urn:sdmx:org.sdmx.infomodel.datastructure.Dataflow=NB:EXR(1.0)",
                "dataProvider": "urn:sdmx:org.sdmx.infomodel.base.DataProvider=NB:DATA_PROVIDERS(1.0).NB",
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
        if url == EXR_URL:
            return JsonResponse(status=200, url=url, body=EXR_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nbprov fetch must GET, not POST {url}")


def test_printed_refs_copy_agreement_ids() -> None:
    source = NbprovSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "ANN_KPRA_NB_NB",
        "EXR_NB_NB",
        "IR_NB_NB",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        KPRA_URL,
        EXR_URL,
        "https://data.norges-bank.no/api/provisionagreement/NB/IR_NB_NB?format=sdmx-json",
    ]
    assert all("/api/data/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/api/codelist" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/api/datastructure" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_joins_printed_agency_and_id() -> None:
    assert (
        printed_item_url({"id": "EXR_NB_NB", "agencyID": "NB"}, LIST_URL) == EXR_URL
    )


def test_nbprov_is_a_registered_source() -> None:
    assert "nbprov" in SOURCE_IDS
    assert "norgesbank" in SOURCE_IDS
    assert "nbcodelist" in SOURCE_IDS
    assert "nbdsd" in SOURCE_IDS
    assert "kvgrunn" in SOURCE_IDS
    assert "nbconcept" in SOURCE_IDS
    assert "kystnav" in SOURCE_IDS
    assert "mdirwms" in SOURCE_IDS
    assert "ssbfam" in SOURCE_IDS
    assert "ssbsec" in SOURCE_IDS
    assert "ssclass" in SOURCE_IDS
    assert "nibiorest" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("nibiorest") + 1] == "nbprov"
    source = build_source("nbprov")
    assert isinstance(source, NbprovSource)
    assert source.source_id == "nbprov"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = NbprovSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nbprov"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == EXR_URL
    assert row["title"] == "Norges Bank for Exchange rates"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("norgesbank:")
    assert not str(row["id"]).startswith("nbcodelist:")
    assert not str(row["id"]).startswith("nbdsd:")
    nxt = registry.get_dataset("nbprov:ANN_KPRA_NB_NB")
    assert nxt is not None
    assert nxt["access_path"] == KPRA_URL
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "EXR_NB_NB"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["nbprov_provisionagreement"]["id"] == "EXR_NB_NB"
    assert "links" not in payload["nbprov_provisionagreement"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_agreement_names(tmp_path: Path) -> None:
    source = NbprovSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == EXR_URL
    assert result.table_id == "EXR_NB_NB"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["Norges Bank for Exchange rates"]
    assert all(row["measure"] == "name" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["id"] == "EXR_NB_NB"
    assert dims["agencyID"] == "NB"
    assert dims["version"] == "1.0"
    assert "names" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == EXR_URL for row in rows)
    registry.close()


def test_cells_copy_printed_agreement_names() -> None:
    cells = cells_from_nbprov(EXR_BODY)
    assert len(cells) == 1
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "Norges Bank for Exchange rates"
    assert dims["id"] == "EXR_NB_NB"
    assert dims["structureUsage"].startswith("urn:sdmx:")
    assert "names" not in dims
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_nbprov(["Exchange rates"])
    with pytest.raises(ValueError, match="printed no provision agreements"):
        cells_from_nbprov({"data": {"provisionAgreements": [{}]}})


def test_is_nbprov_url_accepts_only_provisionagreement_paths() -> None:
    assert is_nbprov_url(EXR_URL)
    assert nbprov_table_id(EXR_URL) == "EXR_NB_NB"
    assert not is_nbprov_url(LIST_URL)
    assert not is_nbprov_url(DATAFLOW_URL)
    assert not is_nbprov_url(CODELIST_URL)
    assert not is_nbprov_url(DSD_URL)
    assert not is_nbprov_url(CONCEPT_URL)
    assert not is_nbprov_url("https://data.norges-bank.no/api")
    assert not is_nbprov_url("https://www.norges-bank.no/api/provisionagreement/NB/EXR_NB_NB")
    assert not is_nbprov_url(None)


def test_limit_and_offset_slice_printed_agreements() -> None:
    source = NbprovSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=2)] == [
        "ANN_KPRA_NB_NB",
        "EXR_NB_NB",
    ]
    nxt = source.list_dataset_refs(limit=1, offset=2)
    assert [ref.source_native_id for ref in nxt] == ["IR_NB_NB"]
