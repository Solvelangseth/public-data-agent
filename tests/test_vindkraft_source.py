from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import classify_access_path, fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.vindkraft import (
    DOCS_URL,
    VindkraftSource,
    cells_from_vindkraft,
    cells_from_vindkraft_power,
    is_vindkraft_plants_url,
    is_vindkraft_url,
    plants_matching_id,
    printed_get_paths,
    selected_vindkraft_id,
    vindkraft_table_id,
)

PLANTS_URL = "https://api.nve.no/web/WindPowerplant/GetWindPowerPlants"
INOP_URL = "https://api.nve.no/web/WindPowerplant/GetWindPowerPlantsInOperation"
VANNKRAFT_URL = "https://api.nve.no/web/Powerplant/GetHydroPowerPlants"
NVE_URL = "https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk/HentOffentligData"
REGOBS_URL = "https://api.regobs.no/v5/KdvElements"
DATASET_ID = "vindkraft:GetWindPowerPlants"

DOCS_HTML = """
<b>Base url:</b> <span class="currentScheme">https://</span>api.nve.no/web/WindPowerplant
<span class="opblock-summary-method">GET</span>
<span class="opblock-summary-path"><span>/GetWindPowerPlantsInOperation</span></span>
</div>
<div>
<div class="opblock-summary-description">Henter vindkraftverk som er i drift</div>
<span class="opblock-summary-method">GET</span>
<span class="opblock-summary-path"><span>/GetWindPowerPlants</span></span>
</div>
<div>
<div class="opblock-summary-description">Henter alle vindkraftverk</div>
<span class="opblock-summary-method">GET</span>
<span class="opblock-summary-path"><span>/GetWindPowerPlants/{id}</span></span>
</div>
<div>
<div class="opblock-summary-description">skip templated</div>
"""

PLANTS = [
    {
        "VindkraftAnleggId": 20,
        "Navn": "Bessakerfjellet",
        "AnleggsNr": 10413,
        "InstallertEffekt_MW": 57.5,
        "NormalAArsproduksjon_GWh": 152.9,
        "nested": {"skip": True},
    },
    {"VindkraftAnleggId": 21, "Navn": "Ytre Vikna", "AnleggsNr": 10414},
]



class CatalogHttp:
    def get_text(self, url: str, *, headers=None) -> str:
        if url == DOCS_URL:
            return DOCS_HTML
        raise AssertionError(f"unexpected GET {url}")

    def get_json(self, url: str, *, headers=None):
        raise AssertionError(f"vindkraft list must GET text, not JSON {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == PLANTS_URL:
            return JsonResponse(status=200, url=url, body=PLANTS)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"vindkraft fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_paths() -> None:
    source = VindkraftSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "GetWindPowerPlantsInOperation",
        "GetWindPowerPlants",
    ]
    assert [ref.source_native_uri for ref in refs] == [INOP_URL, PLANTS_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)


def test_printed_get_paths_keep_document_order() -> None:
    listed = printed_get_paths(DOCS_HTML)
    assert [path for path, _title, _base in listed] == [
        "/GetWindPowerPlantsInOperation",
        "/GetWindPowerPlants",
    ]


def test_vindkraft_is_a_registered_source() -> None:
    assert "vindkraft" in SOURCE_IDS
    assert "nve" in SOURCE_IDS
    assert "regobs" in SOURCE_IDS
    assert "sigmets" in SOURCE_IDS
    assert "kvwms" in SOURCE_IDS
    assert "grep" in SOURCE_IDS
    assert "aviationforecast" in SOURCE_IDS
    assert "vannkraft" in SOURCE_IDS
    source = build_source("vindkraft")
    assert isinstance(source, VindkraftSource)
    assert source.source_id == "vindkraft"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = VindkraftSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "vindkraft"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == PLANTS_URL
    assert row["title"] == "Henter alle vindkraftverk"
    inop = registry.get_dataset("vindkraft:GetWindPowerPlantsInOperation")
    assert inop is not None
    assert inop["access_path"] == INOP_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("nve:")
    assert not str(row["id"]).startswith("vannkraft:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["vindkraft_docs_path"] == "/GetWindPowerPlants"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_refuses_plant_name_catalog(tmp_path: Path) -> None:
    source = VindkraftSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    with pytest.raises(ValueError, match="65 plant names"):
        fetch_observations(
            registry,
            "vindkraft:GetWindPowerPlantsInOperation",
            table_id="ignored",
            http=FetchHttp(),
        )
    registry.close()


def test_fetch_refuses_unfiltered_plants(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_observation_dataset(
        dataset_id=DATASET_ID,
        title="Henter alle vindkraftverk",
        publisher_name=None,
        access_path=PLANTS_URL,
        license=None,
    )
    registry.conn.commit()
    with pytest.raises(ValueError, match="printed VindkraftAnleggId"):
        fetch_observations(
            registry,
            DATASET_ID,
            table_id="ignored",
            http=FetchHttp(),
        )
    registry.close()


def test_vindkraft_plants_url_is_observations() -> None:
    assert is_vindkraft_plants_url(PLANTS_URL)
    assert not is_vindkraft_plants_url(INOP_URL)
    assert classify_access_path(PLANTS_URL)["kind"] == "observations"
    assert classify_access_path(INOP_URL)["kind"] == "none"


def test_fetch_gets_printed_plant_floats(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_observation_dataset(
        dataset_id=DATASET_ID,
        title="Henter alle vindkraftverk",
        publisher_name=None,
        access_path=PLANTS_URL,
        license=None,
    )
    registry.conn.commit()
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
        select={"VindkraftAnleggId": ["20"]},
    )
    assert result.request_url == PLANTS_URL
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_measure = {row["measure"]: json.loads(row["value_json"]) for row in rows}
    assert by_measure["InstallertEffekt_MW"] == 57.5
    assert by_measure["NormalAArsproduksjon_GWh"] == 152.9
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["VindkraftAnleggId"] == "20"
    assert dims["Navn"] == "Bessakerfjellet"
    assert "nested" not in dims
    assert all(row["license"] is None for row in rows)
    cap = registry.get_capability(DATASET_ID)
    assert cap["capability"] == "observations"
    registry.close()


def test_fetch_refuses_unknown_plant_id(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_observation_dataset(
        dataset_id=DATASET_ID,
        title="Henter alle vindkraftverk",
        publisher_name=None,
        access_path=PLANTS_URL,
        license=None,
    )
    registry.conn.commit()
    with pytest.raises(ValueError, match="printed plant id"):
        fetch_observations(
            registry,
            DATASET_ID,
            table_id="ignored",
            http=FetchHttp(),
            select={"VindkraftAnleggId": ["missing"]},
        )
    registry.close()


def test_selected_vindkraft_id_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError, match="Navn"):
        selected_vindkraft_id({"Navn": ["Bessakerfjellet"]})
    assert selected_vindkraft_id({"VindkraftAnleggId": ["20"]}) == "20"
    assert plants_matching_id(PLANTS, "20") == [PLANTS[0]]
    with pytest.raises(ValueError, match="printed plant id"):
        plants_matching_id(PLANTS, "missing")


def test_cells_copy_printed_name() -> None:
    cells = cells_from_vindkraft(PLANTS)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "Navn"
    assert value == "Bessakerfjellet"
    assert dims["VindkraftAnleggId"] == "20"
    assert "nested" not in dims


def test_cells_copy_printed_floats() -> None:
    cells = cells_from_vindkraft_power([PLANTS[0]])
    by_measure = {measure: value for measure, value, _dims in cells}
    assert by_measure == {
        "InstallertEffekt_MW": 57.5,
        "NormalAArsproduksjon_GWh": 152.9,
    }
    assert all("nested" not in dims for _measure, _value, dims in cells)


def test_is_vindkraft_url_accepts_only_windpowerplant_path() -> None:
    assert is_vindkraft_url(PLANTS_URL)
    assert is_vindkraft_url(INOP_URL)
    assert vindkraft_table_id(PLANTS_URL) == "GetWindPowerPlants"
    assert not is_vindkraft_url(VANNKRAFT_URL)
    assert not is_vindkraft_url(NVE_URL)
    assert not is_vindkraft_url(REGOBS_URL)
    assert not is_vindkraft_url("https://data.norge.no/datasets/x")
    assert not is_vindkraft_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = VindkraftSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "GetWindPowerPlantsInOperation"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["GetWindPowerPlants"]
