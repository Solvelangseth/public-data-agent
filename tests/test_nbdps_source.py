from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.nbdps import (
    LIST_URL,
    NbdpsSource,
    cells_from_nbdps,
    is_nbdps_url,
    nbdps_table_id,
    printed_item_url,
)

SCHEME_URL = (
    "https://data.norges-bank.no/api/dataproviderscheme/NB/DATA_PROVIDERS?format=sdmx-json"
)
DATAFLOW_URL = "https://data.norges-bank.no/api/data/EXR?format=sdmx-json"
CODELIST_URL = "https://data.norges-bank.no/api/codelist/NB/CL_FREQ?format=sdmx-json"
DSD_URL = "https://data.norges-bank.no/api/datastructure/NB/DSD_EXR?format=sdmx-json"
CONCEPT_URL = "https://data.norges-bank.no/api/conceptscheme/NB/CS_NB?format=sdmx-json"
AGENCY_URL = "https://data.norges-bank.no/api/agencyscheme/SDMX/AGENCIES?format=sdmx-json"
PROV_URL = "https://data.norges-bank.no/api/provisionagreement/NB/EXR_NB_NB?format=sdmx-json"
DATASET_ID = "nbdps:DATA_PROVIDERS"

CATALOG = {
    "meta": {"sender": {"id": "Unknown"}},
    "data": {
        "dataProviderSchemes": [
            {
                "id": "DATA_PROVIDERS",
                "agencyID": "NB",
                "name": "DATA_PROVIDERS",
                "names": {"en": "DATA_PROVIDERS"},
                "version": "1.0",
                "dataProviders": [{"id": "SSB", "name": "SSB"}],
            }
        ]
    },
}
SCHEME_BODY = {
    "meta": {"sender": {"id": "Unknown"}},
    "data": {
        "dataProviderSchemes": [
            {
                "id": "DATA_PROVIDERS",
                "agencyID": "NB",
                "name": "DATA_PROVIDERS",
                "dataProviders": [
                    {
                        "id": "SSB",
                        "name": "SSB",
                        "names": {"en": "SSB"},
                    },
                    {
                        "id": "NB",
                        "name": "Norges Bank",
                        "names": {"en": "Norges Bank"},
                    },
                    {
                        "id": "TR",
                        "name": "Thomson Reuters",
                        "names": {"en": "Thomson Reuters"},
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
        raise AssertionError(f"nbdps fetch must GET, not POST {url}")


def test_printed_refs_copy_dataproviderscheme_ids() -> None:
    source = NbdpsSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["DATA_PROVIDERS"]
    assert [ref.source_native_uri for ref in refs] == [SCHEME_URL]
    assert all("/api/data/" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/api/codelist" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/api/datastructure" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/api/conceptscheme" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/api/agencyscheme" not in (ref.source_native_uri or "") for ref in refs)
    assert all("/api/provisionagreement" not in (ref.source_native_uri or "") for ref in refs)


def test_item_url_joins_printed_agency_and_id() -> None:
    assert (
        printed_item_url({"id": "DATA_PROVIDERS", "agencyID": "NB"}, LIST_URL) == SCHEME_URL
    )


def test_nbdps_is_a_registered_source() -> None:
    assert "nbdps" in SOURCE_IDS
    assert "norgesbank" in SOURCE_IDS
    assert "nbcodelist" in SOURCE_IDS
    assert "nbdsd" in SOURCE_IDS
    assert "nbconcept" in SOURCE_IDS
    assert "nbprov" in SOURCE_IDS
    assert "ssbver" in SOURCE_IDS
    assert "hiwms" in SOURCE_IDS
    assert "nbagency" in SOURCE_IDS
    assert "kvtopo" in SOURCE_IDS
    assert SOURCE_IDS[SOURCE_IDS.index("hiwms") + 1] == "nbagency"
    assert SOURCE_IDS[SOURCE_IDS.index("nbagency") + 1] == "kvtopo"
    assert SOURCE_IDS[SOURCE_IDS.index("kvtopo") + 1] == "nbdps"
    assert SOURCE_IDS[SOURCE_IDS.index("nbdps") + 1] == "vegwms"
    assert SOURCE_IDS[SOURCE_IDS.index("vegwms") + 1] == "fdkorg"
    assert SOURCE_IDS[SOURCE_IDS.index("fdkorg") + 1] == "brrolletype"
    assert SOURCE_IDS[SOURCE_IDS.index("brrolletype") + 1] == "brkommuner"
    assert SOURCE_IDS[SOURCE_IDS.index("brkommuner") + 1] == "nguminer"
    assert SOURCE_IDS[SOURCE_IDS.index("nguminer") + 1] == "brrollegruppe"
    assert SOURCE_IDS[SOURCE_IDS.index("brrollegruppe") + 1] == "mdirgis"
    assert SOURCE_IDS[SOURCE_IDS.index("mdirgis") + 1] == "ssbcorr"
    assert SOURCE_IDS[SOURCE_IDS.index("ssbcorr") + 1] == "bwgis"
    assert SOURCE_IDS[SOURCE_IDS.index("bwgis") + 1] == "broppdater"
    assert SOURCE_IDS[SOURCE_IDS.index("broppdater") + 1] == "kifylker"
    assert SOURCE_IDS[SOURCE_IDS.index("kifylker") + 1] == "brrepresent"
    assert SOURCE_IDS[SOURCE_IDS.index("brrepresent") + 1] == "brenheter"
    assert SOURCE_IDS[SOURCE_IDS.index("brenheter") + 1] == "ssbvar"
    assert SOURCE_IDS[SOURCE_IDS.index("ssbvar") + 1] == "nordatlas"
    assert SOURCE_IDS[SOURCE_IDS.index("nordatlas") + 1] == "brunder"
    assert SOURCE_IDS[SOURCE_IDS.index("brunder") + 1] == "kikommuner"
    assert SOURCE_IDS[SOURCE_IDS.index("kikommuner") + 1] == "fbgis"
    assert SOURCE_IDS[SOURCE_IDS.index("fbgis") + 1] == "stperioder"
    assert SOURCE_IDS[SOURCE_IDS.index("stperioder") + 1] == "nibioar50"
    assert SOURCE_IDS[SOURCE_IDS.index("nibioar50") + 1] == "brorgformen"
    assert SOURCE_IDS[SOURCE_IDS.index("brorgformen") + 1] == "crinst"
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
    assert SOURCE_IDS[SOURCE_IDS.index("crperson") + 1] == "stsporre"
    assert SOURCE_IDS[SOURCE_IDS.index("stsporre") + 1] == "crresult"
    assert SOURCE_IDS[SOURCE_IDS.index("crresult") + 1] == "stmoter"
    assert SOURCE_IDS[-1] == "stmoter"
    source = build_source("nbdps")
    assert isinstance(source, NbdpsSource)
    assert source.source_id == "nbdps"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = NbdpsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nbdps"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == SCHEME_URL
    assert row["title"] == "DATA_PROVIDERS"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("norgesbank:")
    assert not str(row["id"]).startswith("nbprov:")
    assert not str(row["id"]).startswith("nbagency:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["id"] == "DATA_PROVIDERS"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["nbdps_dataproviderscheme"]["id"] == "DATA_PROVIDERS"
    assert "dataProviders" not in payload["nbdps_dataproviderscheme"]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_provider_names(tmp_path: Path) -> None:
    source = NbdpsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == SCHEME_URL
    assert result.table_id == "DATA_PROVIDERS"
    assert result.http_status == 200
    assert result.counts.listed == 3
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert set(values) == {"SSB", "Norges Bank", "Thomson Reuters"}
    assert all(row["measure"] == "name" for row in rows)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    dims = json.loads(by_value["Thomson Reuters"]["dimensions_json"])
    assert dims["id"] == "TR"
    assert "names" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == SCHEME_URL for row in rows)
    registry.close()


def test_cells_copy_printed_data_providers() -> None:
    cells = cells_from_nbdps(SCHEME_BODY)
    assert len(cells) == 3
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "SSB"
    assert dims["id"] == "SSB"
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_nbdps(["DATA_PROVIDERS"])
    with pytest.raises(ValueError, match="data providers"):
        cells_from_nbdps({"data": {"dataProviderSchemes": [{"id": "DATA_PROVIDERS"}]}})


def test_is_nbdps_url_accepts_only_dataproviderscheme_paths() -> None:
    assert is_nbdps_url(SCHEME_URL)
    assert nbdps_table_id(SCHEME_URL) == "DATA_PROVIDERS"
    assert is_nbdps_url(LIST_URL)
    assert not is_nbdps_url(DATAFLOW_URL)
    assert not is_nbdps_url(CODELIST_URL)
    assert not is_nbdps_url(DSD_URL)
    assert not is_nbdps_url(CONCEPT_URL)
    assert not is_nbdps_url(AGENCY_URL)
    assert not is_nbdps_url(PROV_URL)
    assert not is_nbdps_url("https://data.norges-bank.no/api")
    assert not is_nbdps_url(
        "https://www.norges-bank.no/api/dataproviderscheme/NB/DATA_PROVIDERS"
    )
    assert not is_nbdps_url(None)


def test_limit_and_offset_slice_printed_schemes() -> None:
    source = NbdpsSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "DATA_PROVIDERS"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert nxt == []
