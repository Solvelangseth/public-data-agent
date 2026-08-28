from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.regobs import (
    LIST_URL,
    SWAGGER_URL,
    RegobsSource,
    cells_from_regobs,
    is_regobs_url,
    printed_repositories,
    regobs_table_id,
)

DATASET_ID = "regobs:Dirt_DangerSignKDV"
ACTIVITY_ID = "regobs:Dirt_ActivityInfluencedKDV"
NVE_URL = "https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk/HentOffentligData"
SSBV2_URL = (
    "https://data.ssb.no/api/pxwebapi/v2/tables/13760/data?lang=no&outputFormat=json-stat2"
)
SSB_V0_URL = "https://data.ssb.no/api/v0/no/table/06683"
ACCOUNT_URL = "https://api.regobs.no/v5/Account/GetObserver"
NPIINTERN_URL = (
    "https://geodata.npolar.no/arcgis/rest/services/Basisdata_Intern/"
    "NP_Antarktis_WMTS_3031/MapServer?f=json"
)

CATALOG = {
    "KdvRepositories": {
        "Dirt_DangerSignKDV": [
            {"Id": 0, "Name": "Ikke gitt", "Description": ""},
            {"Id": 1, "Name": "Vannsig", "Description": "vann", "nested": {"skip": True}},
        ],
        "Dirt_ActivityInfluencedKDV": [
            {"Id": 0, "Name": "Ikke gitt"},
            {"Id": 2, "Name": "Vei"},
        ],
        "": [{"Id": 9, "Name": "skip empty key"}],
        "NotAList": {"Id": 1},
        "SkipEmpty": [],
    },
    "ViewRepositories": {
        "SomeView": [{"Id": 1, "Name": "unused"}],
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
        if url == LIST_URL:
            return JsonResponse(status=200, url=url, body=CATALOG)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"regobs fetch must GET, not POST {url}")


def test_printed_refs_skip_empty_key_and_non_lists() -> None:
    source = RegobsSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "Dirt_DangerSignKDV",
        "Dirt_ActivityInfluencedKDV",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        f"{LIST_URL}#Dirt_DangerSignKDV",
        f"{LIST_URL}#Dirt_ActivityInfluencedKDV",
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "NotAList" for ref in refs)


def test_printed_repositories_keep_document_order() -> None:
    listed = printed_repositories(CATALOG, LIST_URL)
    assert [ident for ident, _href in listed] == [
        "Dirt_DangerSignKDV",
        "Dirt_ActivityInfluencedKDV",
    ]
    assert [href for _ident, href in listed] == [
        f"{LIST_URL}#Dirt_DangerSignKDV",
        f"{LIST_URL}#Dirt_ActivityInfluencedKDV",
    ]


def test_regobs_is_a_registered_source() -> None:
    assert "regobs" in SOURCE_IDS
    assert "nve" in SOURCE_IDS
    assert "ssbv2" in SOURCE_IDS
    assert "ssb" in SOURCE_IDS
    assert "ragis" in SOURCE_IDS
    assert "fiskerigis" in SOURCE_IDS
    assert "npiintern" in SOURCE_IDS
    assert "nibiowms" in SOURCE_IDS
    source = build_source("regobs")
    assert isinstance(source, RegobsSource)
    assert source.source_id == "regobs"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = RegobsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "regobs"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == LIST_URL
    assert row["title"] == "Dirt_DangerSignKDV"
    activity = registry.get_dataset(ACTIVITY_ID)
    assert activity is not None
    assert activity["access_path"] == LIST_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("nve:")
    assert not str(row["id"]).startswith("ssbv2:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["regobs_repo_id"] == "Dirt_DangerSignKDV"
    assert payload["regobs_repo_href"] == LIST_URL
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["landingPage"] == [SWAGGER_URL]
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_names_for_one_repo(tmp_path: Path) -> None:
    source = RegobsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == LIST_URL
    assert result.table_id == "Dirt_DangerSignKDV"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"Ikke gitt", "Vannsig"}
    assert by_value["Vannsig"]["measure"] == "Name"
    dims = json.loads(by_value["Vannsig"]["dimensions_json"])
    assert dims["Id"] == "1"
    assert dims["Description"] == "vann"
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == LIST_URL for row in rows)
    activity_obs = registry.list_observations(ACTIVITY_ID)
    assert activity_obs == []
    registry.close()


def test_cells_copy_printed_name_or_id() -> None:
    cells = cells_from_regobs(CATALOG, table_id="Dirt_DangerSignKDV")
    assert len(cells) == 2
    measure, value, dims = cells[1]
    assert measure == "Name"
    assert value == "Vannsig"
    assert dims["Id"] == "1"
    assert "nested" not in dims
    assert cells_from_regobs(
        {"KdvRepositories": {"OnlyId": [{"Id": 7}]}},
        table_id="OnlyId",
    ) == [("Id", 7, {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_regobs(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_regobs({"KdvRepositories": {"Empty": []}}, table_id="Empty")


def test_is_regobs_url_accepts_only_kdvelements_path() -> None:
    assert is_regobs_url(LIST_URL)
    assert is_regobs_url(LIST_URL + "?lang=nb")
    assert is_regobs_url(f"{LIST_URL}#Dirt_DangerSignKDV")
    assert regobs_table_id(LIST_URL, "Dirt_DangerSignKDV") == "Dirt_DangerSignKDV"
    assert regobs_table_id(LIST_URL) == "KdvElements"
    assert not is_regobs_url(ACCOUNT_URL)
    assert not is_regobs_url(NVE_URL)
    assert not is_regobs_url(SSBV2_URL)
    assert not is_regobs_url(SSB_V0_URL)
    assert not is_regobs_url(NPIINTERN_URL)
    assert not is_regobs_url("https://data.norge.no/datasets/x")
    assert not is_regobs_url(None)


def test_limit_and_offset_slice_printed_repos() -> None:
    source = RegobsSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "Dirt_DangerSignKDV"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["Dirt_ActivityInfluencedKDV"]
