from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.sikt import (
    SiktSource,
    cells_from_sikt,
    is_sikt_url,
    printed_collection_url,
    sikt_table_id,
)

LIST_URL = "https://dataverse.no/api/dataverses/:root/contents"
TROLLING_URL = "https://dataverse.no/api/dataverses/3/contents"
AGDER_URL = "https://dataverse.no/api/dataverses/1533/contents"
DATASET_ID = "sikt:3"

CATALOG = {
    "status": "OK",
    "data": [
        {"type": "dataverse", "id": 3, "title": "TROLLing"},
        {"type": "dataverse", "id": 1533, "title": "University of Agder"},
        {"type": "dataverse", "id": 5622, "title": "NTNU – Norwegian University of Science and Technology"},
        {
            "id": 5685,
            "identifier": "WNRIXH",
            "publisher": "DataverseNO",
            "type": "dataset",
        },
    ],
}
TROLLING_BODY = {
    "status": "OK",
    "data": [
        {"type": "dataverse", "id": 117531, "title": "AcqVA Aurora"},
        {
            "id": 4,
            "identifier": "S5SXRG",
            "publisher": "DataverseNO",
            "type": "dataset",
            "nested": {"skip": "dict"},
        },
    ],
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
        if url == TROLLING_URL:
            return JsonResponse(status=200, url=url, body=TROLLING_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"sikt fetch must GET, not POST {url}")


def test_printed_refs_copy_titled_dataverse_ids() -> None:
    source = SiktSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["3", "1533", "5622"]
    assert [ref.source_native_uri for ref in refs] == [
        TROLLING_URL,
        AGDER_URL,
        "https://dataverse.no/api/dataverses/5622/contents",
    ]
    assert all(":root" not in (ref.source_native_uri or "") for ref in refs)


def test_collection_url_keeps_catalog_path_and_printed_id() -> None:
    url = printed_collection_url("3", LIST_URL)
    assert url == TROLLING_URL
    assert url.startswith("https://dataverse.no/api/dataverses/3/")
    assert url.endswith("/contents")
    assert ":root" not in url


def test_sikt_is_a_registered_source() -> None:
    assert "sikt" in SOURCE_IDS
    source = build_source("sikt")
    assert isinstance(source, SiktSource)
    assert source.source_id == "sikt"


def test_harvest_writes_printed_id_and_null_license_publisher(tmp_path: Path) -> None:
    source = SiktSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "sikt"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == TROLLING_URL
    assert row["title"] == "TROLLing"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["sikt_dataverse"]["id"] == 3
    assert payload["license"] is None
    assert payload["publisher"] is None
    registry.close()


def test_fetch_gets_printed_trolling_contents(tmp_path: Path) -> None:
    source = SiktSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == TROLLING_URL
    assert result.table_id == "3"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert set(values) == {"AcqVA Aurora", "S5SXRG"}
    by_name = {json.loads(row["value_json"]): row for row in rows}
    assert by_name["AcqVA Aurora"]["measure"] == "title"
    assert by_name["S5SXRG"]["measure"] == "identifier"
    dims = json.loads(by_name["AcqVA Aurora"]["dimensions_json"])
    assert dims["id"] == "117531"
    assert dims["type"] == "dataverse"
    dataset_dims = json.loads(by_name["S5SXRG"]["dimensions_json"])
    assert dataset_dims["publisher"] == "DataverseNO"
    assert "nested" not in dataset_dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == TROLLING_URL for row in rows)
    registry.close()


def test_cells_copy_printed_title() -> None:
    cells = cells_from_sikt(TROLLING_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "title"
    assert value == "AcqVA Aurora"
    assert dims["id"] == "117531"
    fallback = cells_from_sikt({"data": [{"identifier": "WNRIXH", "id": 1}]})
    assert fallback == [("identifier", "WNRIXH", {"id": "1"})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_sikt([{"title": "TROLLing"}])
    with pytest.raises(ValueError, match="data array"):
        cells_from_sikt({"data": "nope"})


def test_is_sikt_url_accepts_only_dataverse_host() -> None:
    assert is_sikt_url(TROLLING_URL)
    assert is_sikt_url(LIST_URL)
    assert sikt_table_id(TROLLING_URL) == "3"
    assert sikt_table_id("https://dataverse.no/api/dataverses/1533/contents") == "1533"
    assert not is_sikt_url("https://api.nva.sikt.no/openapi.json")
    assert not is_sikt_url("https://data.norge.no/datasets/x")
    assert not is_sikt_url("https://www.sikt.no/dataverse")
    assert not is_sikt_url(None)


def test_limit_and_offset_slice_printed_dataverses() -> None:
    source = SiktSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=2)] == [
        "3",
        "1533",
    ]
    nxt = source.list_dataset_refs(limit=1, offset=2)
    assert [ref.source_native_id for ref in nxt] == ["5622"]
