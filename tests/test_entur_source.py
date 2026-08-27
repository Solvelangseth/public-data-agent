from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.entur import (
    EnturGbfsSource,
    cells_from_entur,
    entur_table_id,
    is_entur_gbfs_url,
    printed_feed_url,
    printed_systems,
)

LIST_URL = "https://api.entur.io/mobility/v2/gbfs"
STAVANGER_URL = "https://api.entur.io/mobility/v2/gbfs/v2/voistavanger/gbfs"
KRISTIANSAND_URL = "https://api.entur.io/mobility/v2/gbfs/v2/voikristiansand/gbfs"
OSLO_URL = "https://api.entur.io/mobility/v2/gbfs/v2/voioslo/gbfs"
VEHICLE_TYPES_URL = "https://api.entur.io/mobility/v2/gbfs/v2/voistavanger/vehicle_types"
DATASET_ID = "entur:voistavanger"

SYSTEM_LIST = {
    "systems": [
        {"id": "voistavanger", "url": STAVANGER_URL},
        {"id": "voikristiansand", "url": KRISTIANSAND_URL},
        {"id": "voioslo", "url": OSLO_URL},
        {"id": "skip-me"},
        {"url": "https://api.entur.io/mobility/v2/gbfs/v2/missing-id/gbfs"},
    ]
}
DISCOVERY = {
    "last_updated": 1,
    "ttl": 3600,
    "version": "2.3",
    "data": {
        "en": {
            "feeds": [
                {
                    "name": "system_information",
                    "url": "https://api.entur.io/mobility/v2/gbfs/v2/voistavanger/system_information",
                },
                {"name": "vehicle_types", "url": VEHICLE_TYPES_URL},
            ]
        }
    },
}
VEHICLE_TYPES = {
    "last_updated": 2,
    "ttl": 30,
    "version": "2.3",
    "data": {
        "vehicle_types": [
            {
                "vehicle_type_id": "YVO:VehicleType:172ef7a6-ee84-4320-9337-86235f2f67ac",
                "name": "Voiager_5",
                "make": "Ninebot",
                "model": "Voiager_5",
                "nested": {"skip": "dict"},
            },
            {
                "vehicle_type_id": "YVO:VehicleType:5da7c980-05b1-4a03-873a-d3d45a2f7e69",
                "name": "Voiager_4",
                "make": "Ninebot",
                "model": "Voiager_4",
            },
        ]
    },
}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == LIST_URL:
            return SYSTEM_LIST
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        self.gets.append(url)
        if url == STAVANGER_URL:
            return JsonResponse(status=200, url=url, body=DISCOVERY)
        if url == VEHICLE_TYPES_URL:
            return JsonResponse(status=200, url=url, body=VEHICLE_TYPES)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"entur fetch must GET, not POST {url}")


def test_printed_refs_copy_system_id_and_url() -> None:
    source = EnturGbfsSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "voistavanger",
        "voikristiansand",
        "voioslo",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        STAVANGER_URL,
        KRISTIANSAND_URL,
        OSLO_URL,
    ]
    assert all(ref.source_native_uri.startswith("https://api.entur.io/") for ref in refs)


def test_entur_is_a_registered_source() -> None:
    assert "entur" in SOURCE_IDS
    source = build_source("entur")
    assert isinstance(source, EnturGbfsSource)
    assert source.source_id == "entur"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = EnturGbfsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "entur"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == STAVANGER_URL
    assert row["title"] == "voistavanger"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["entur_system"] == {"id": "voistavanger", "url": STAVANGER_URL}
    assert payload["license"] is None
    assert payload["publisher"] is None
    registry.close()


def test_fetch_follows_printed_vehicle_types_feed(tmp_path: Path) -> None:
    source = EnturGbfsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    http = FetchHttp()
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=http,
    )
    assert http.gets == [STAVANGER_URL, VEHICLE_TYPES_URL]
    assert result.request_url == VEHICLE_TYPES_URL
    assert result.table_id == "voistavanger"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_name = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_name) == {"Voiager_5", "Voiager_4"}
    assert all(row["measure"] == "name" for row in rows)
    dims = json.loads(by_name["Voiager_5"]["dimensions_json"])
    assert dims["make"] == "Ninebot"
    assert dims["model"] == "Voiager_5"
    assert dims["vehicle_type_id"] == "YVO:VehicleType:172ef7a6-ee84-4320-9337-86235f2f67ac"
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == STAVANGER_URL for row in rows)
    registry.close()


def test_cells_copy_printed_vehicle_type_name() -> None:
    cells = cells_from_entur(VEHICLE_TYPES)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "Voiager_5"
    assert dims["make"] == "Ninebot"
    feeds = cells_from_entur(DISCOVERY)
    assert feeds[0] == (
        "name",
        "system_information",
        {"url": "https://api.entur.io/mobility/v2/gbfs/v2/voistavanger/system_information"},
    )
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_entur([{"name": "Voiager_5"}])


def test_is_entur_url_accepts_only_mobility_gbfs_host() -> None:
    assert is_entur_gbfs_url(STAVANGER_URL)
    assert is_entur_gbfs_url(LIST_URL)
    assert is_entur_gbfs_url(VEHICLE_TYPES_URL)
    assert entur_table_id(STAVANGER_URL) == "voistavanger"
    assert printed_feed_url(DISCOVERY, "vehicle_types") == VEHICLE_TYPES_URL
    assert printed_systems(SYSTEM_LIST)[0]["id"] == "voistavanger"
    assert not is_entur_gbfs_url("https://data.norge.no/datasets/x")
    assert not is_entur_gbfs_url("https://api.entur.io/geocoder/v1/autocomplete")
    assert not is_entur_gbfs_url("https://developer.entur.org/mobility/v2/gbfs")
    assert not is_entur_gbfs_url(None)


def test_limit_and_offset_slice_printed_systems() -> None:
    source = EnturGbfsSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=2)] == [
        "voistavanger",
        "voikristiansand",
    ]
    nxt = source.list_dataset_refs(limit=1, offset=2)
    assert [ref.source_native_id for ref in nxt] == ["voioslo"]
