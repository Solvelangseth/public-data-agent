from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.sodir import (
    SodirSource,
    cells_from_sodir,
    is_sodir_url,
    printed_layer_url,
    printed_publisher,
    sodir_table_id,
)

LIST_URL = (
    "https://factmaps.sodir.no/api/rest/services/DataService/Data/FeatureServer?f=json"
)
BLOCK_URL = (
    "https://factmaps.sodir.no/api/rest/services/DataService/Data/FeatureServer/1001?f=json"
)
QUADRANT_URL = (
    "https://factmaps.sodir.no/api/rest/services/DataService/Data/FeatureServer/1002?f=json"
)
DATASET_ID = "sodir:block"
PUBLISHER = "Norwegian Offshore Directorate"

LIST_BODY = {
    "copyrightText": PUBLISHER,
    "serviceDescription": "The DataService contains all our available data in a single api.",
    "layers": [
        {"id": 1001, "name": "block", "type": "Feature Layer"},
        {"id": 1002, "name": "quadrant", "type": "Feature Layer"},
        {"id": 1003, "name": "", "type": "Feature Layer"},
        {"name": "missing-id", "type": "Feature Layer"},
    ],
}

BLOCK_BODY = {
    "id": 1001,
    "name": "block",
    "copyrightText": PUBLISHER,
    "fields": [
        {
            "name": "OBJECTID",
            "alias": "OBJECTID",
            "type": "esriFieldTypeOID",
            "nested": {"skip": True},
        },
        {
            "name": "blcName",
            "alias": "Block name",
            "type": "esriFieldTypeString",
            "length": 40,
        },
        {
            "name": "",
            "alias": "NPDID block",
            "type": "esriFieldTypeInteger",
        },
    ],
}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == LIST_URL:
            return LIST_BODY
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == BLOCK_URL:
            return JsonResponse(status=200, url=url, body=BLOCK_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"sodir fetch must GET, not POST {url}")


def test_printed_refs_skip_blank_names() -> None:
    source = SodirSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["block", "quadrant"]
    assert [ref.source_native_uri for ref in refs] == [BLOCK_URL, QUADRANT_URL]
    assert LIST_URL not in [ref.source_native_uri for ref in refs]


def test_layer_url_joins_printed_origin_and_id() -> None:
    url = printed_layer_url(1001, LIST_URL)
    assert url == BLOCK_URL
    assert "layers" not in url


def test_printed_publisher_copies_only_copyright_text() -> None:
    assert printed_publisher(LIST_BODY) == {"title": {"en": PUBLISHER}}
    assert printed_publisher({}) is None
    assert printed_publisher({"copyrightText": "  "}) is None


def test_sodir_is_a_registered_source() -> None:
    assert "sodir" in SOURCE_IDS
    source = build_source("sodir")
    assert isinstance(source, SodirSource)
    assert source.source_id == "sodir"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = SodirSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "sodir"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == BLOCK_URL
    assert row["title"] == "block"
    assert row["publisher_name"] == PUBLISHER
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("geonorge:")
    assert not str(row["id"]).startswith("opencom:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["sodir_layer"]["id"] == 1001
    assert payload["license"] is None
    assert payload["publisher"]["title"]["en"] == PUBLISHER
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_block_fields(tmp_path: Path) -> None:
    source = SodirSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == BLOCK_URL
    assert result.table_id == "1001"
    assert result.http_status == 200
    assert result.counts.listed == 3
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"OBJECTID", "blcName", "NPDID block"}
    assert by_value["OBJECTID"]["measure"] == "name"
    assert by_value["blcName"]["measure"] == "name"
    assert by_value["NPDID block"]["measure"] == "alias"
    dims = json.loads(by_value["blcName"]["dimensions_json"])
    assert dims["alias"] == "Block name"
    assert dims["type"] == "esriFieldTypeString"
    assert "nested" not in dims
    assert all(row["publisher_name"] == PUBLISHER for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == BLOCK_URL for row in rows)
    registry.close()


def test_cells_copy_printed_field_names() -> None:
    cells = cells_from_sodir(BLOCK_BODY)
    assert len(cells) == 3
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "OBJECTID"
    assert dims["alias"] == "OBJECTID"
    assert "nested" not in dims
    assert cells[2] == (
        "alias",
        "NPDID block",
        {"name": "", "type": "esriFieldTypeInteger"},
    )
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_sodir([{"name": "block"}])
    with pytest.raises(ValueError, match="fields array"):
        cells_from_sodir({"name": "block"})
    with pytest.raises(ValueError, match="printed no fields"):
        cells_from_sodir({"fields": []})


def test_is_sodir_url_accepts_only_dataservice_layer() -> None:
    assert is_sodir_url(BLOCK_URL)
    assert is_sodir_url(QUADRANT_URL)
    assert sodir_table_id(BLOCK_URL) == "1001"
    assert printed_layer_url(1001, LIST_URL) == BLOCK_URL
    assert not is_sodir_url(LIST_URL)
    assert not is_sodir_url(
        "https://factmaps.sodir.no/api/rest/services/Factmaps/FactMapsWGS84/FeatureServer/201?f=json"
    )
    assert not is_sodir_url("https://data.norge.no/datasets/x")
    assert not is_sodir_url("https://opencom.no/api/3/action/package_list")
    assert not is_sodir_url("https://dataut.vegvesen.no/api/3/action/package_show?id=x")
    assert not is_sodir_url(None)


def test_limit_and_offset_slice_printed_layers() -> None:
    source = SodirSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "block"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["quadrant"]
