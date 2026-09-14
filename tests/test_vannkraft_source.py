from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import classify_access_path, fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.vannkraft import (
    VannkraftSource,
    cells_from_vannkraft,
    is_vannkraft_url,
    printed_base_url,
    printed_endpoint_url,
    printed_get_paths,
    vannkraft_table_id,
)

DOCS_URL = "https://api.nve.no/doc/vannkraftdatabase/"
BASE_URL = "https://api.nve.no/web/Powerplant"
IN_OPERATION_URL = f"{BASE_URL}/GetHydroPowerPlantsInOperation"
ALL_URL = f"{BASE_URL}/GetHydroPowerPlants"
MAGASIN_URL = "https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk"
DATASET_ID = "vannkraft:GetHydroPowerPlantsInOperation"

DOCS_HTML = """
<div>[ <b>Base url:</b> <span class="currentScheme">https://</span>api.nve.no/web/Powerplant ]</div>
<div class="opblock-summary opblock-summary-get">
    <div>
        <span class="opblock-summary-method">GET</span>
        <span class="opblock-summary-path"><span>/GetHydroPowerPlantsInOperation</span></span>
    </div>
    <div>
        <div class="opblock-summary-description">Henter vannkraftverk som er i drift</div>
    </div>
</div>
<div class="opblock-summary opblock-summary-get">
    <div>
        <span class="opblock-summary-method">GET</span>
        <span class="opblock-summary-path"><span>/GetHydroPowerPlants</span></span>
    </div>
    <div>
        <div class="opblock-summary-description">Henter alle vannkraftverk, ogs&#229; kraftverk som ikke lenger er i drift</div>
    </div>
</div>
<div class="opblock-summary opblock-summary-get">
    <div>
        <span class="opblock-summary-method">GET</span>
        <span class="opblock-summary-path"><span>/GetHydroPowerPlants/{id}</span></span>
    </div>
    <div>
        <div class="opblock-summary-description">skip templated</div>
    </div>
</div>
"""

IN_OPERATION_BODY = [
    {
        "VannKraftverkID": 2,
        "Navn": "Adamselv",
        "VannKVType": "Kraftverk",
        "Fylke": "Finnmark",
        "Eiere": [{"Navn": "skip nested"}],
        "Konsesjoner": [{"Tittel": "skip nested"}],
    },
    {
        "VannKraftverkID": 3,
        "Navn": "Alta",
        "VannKVType": "Kraftverk",
        "Fylke": "Finnmark",
    },
]


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_text(self, url: str, *, headers=None) -> str:
        self.gets.append(url)
        if url == DOCS_URL:
            return DOCS_HTML
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == IN_OPERATION_URL:
            return JsonResponse(status=200, url=url, body=IN_OPERATION_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"vannkraft fetch must GET, not POST {url}")


def test_printed_refs_copy_get_paths() -> None:
    source = VannkraftSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "GetHydroPowerPlantsInOperation",
        "GetHydroPowerPlants",
    ]
    assert [ref.source_native_uri for ref in refs] == [IN_OPERATION_URL, ALL_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)


def test_printed_paths_keep_document_order() -> None:
    listed = printed_get_paths(DOCS_HTML)
    assert [item[0] for item in listed] == [
        "/GetHydroPowerPlantsInOperation",
        "/GetHydroPowerPlants",
    ]
    assert printed_base_url(DOCS_HTML) == BASE_URL
    assert printed_endpoint_url("/GetHydroPowerPlantsInOperation", BASE_URL) == IN_OPERATION_URL


def test_vannkraft_is_a_registered_source() -> None:
    assert "vannkraft" in SOURCE_IDS
    assert "nve" in SOURCE_IDS
    source = build_source("vannkraft")
    assert isinstance(source, VannkraftSource)
    assert source.source_id == "vannkraft"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = VannkraftSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "vannkraft"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == IN_OPERATION_URL
    assert row["title"] == "Henter vannkraftverk som er i drift"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("nve:")
    nxt = registry.get_dataset("vannkraft:GetHydroPowerPlants")
    assert nxt is not None
    assert nxt["access_path"] == ALL_URL
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["vannkraft_docs_path"] == "/GetHydroPowerPlantsInOperation"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_refuses_plant_name_catalog(tmp_path: Path) -> None:
    source = VannkraftSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    with pytest.raises(ValueError, match="1863 plant names"):
        fetch_observations(
            registry,
            DATASET_ID,
            table_id="ignored",
            http=FetchHttp(),
        )
    registry.close()


def test_vannkraft_url_is_not_observations() -> None:
    assert is_vannkraft_url(IN_OPERATION_URL)
    assert classify_access_path(IN_OPERATION_URL)["kind"] == "none"
    assert classify_access_path(ALL_URL)["kind"] == "none"


def test_cells_copy_printed_navn() -> None:
    cells = cells_from_vannkraft(IN_OPERATION_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "Navn"
    assert value == "Adamselv"
    assert dims["VannKraftverkID"] == "2"
    assert "Eiere" not in dims
    fallback = cells_from_vannkraft([{"VannKraftverkID": 9, "VannKVType": "Pumpe"}])
    assert fallback == [("VannKraftverkID", 9, {"VannKVType": "Pumpe"})]
    with pytest.raises(ValueError, match="JSON array"):
        cells_from_vannkraft({"Navn": "Adamselv"})
    with pytest.raises(ValueError, match="printed no collection members"):
        cells_from_vannkraft([])


def test_is_vannkraft_url_accepts_only_powerplant_path() -> None:
    assert is_vannkraft_url(IN_OPERATION_URL)
    assert is_vannkraft_url(ALL_URL)
    assert vannkraft_table_id(IN_OPERATION_URL) == "GetHydroPowerPlantsInOperation"
    assert vannkraft_table_id(ALL_URL) == "GetHydroPowerPlants"
    assert not is_vannkraft_url(MAGASIN_URL)
    assert not is_vannkraft_url("https://api.nve.no/web/WindPowerplant/GetWindPowerPlants")
    assert not is_vannkraft_url("https://api.nve.no/web/ElCert/GetApplications")
    assert not is_vannkraft_url("https://api.nve.no/doc/vannkraftdatabase/")
    assert not is_vannkraft_url("https://data.norge.no/datasets/x")
    assert not is_vannkraft_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = VannkraftSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "GetHydroPowerPlantsInOperation"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["GetHydroPowerPlants"]
