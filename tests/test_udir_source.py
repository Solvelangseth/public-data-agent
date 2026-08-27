from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.udir import (
    UdirNsrSource,
    cells_from_udir,
    is_udir_nsr_url,
    printed_endpoint_url,
    printed_license_url,
    udir_table_id,
)

OPENAPI_URL = "https://data-nsr.udir.no/swagger/v1/swagger.json"
ENHETER_URL = "https://data-nsr.udir.no/enheter"
FYLKER_URL = "https://data-nsr.udir.no/fylker"
SKOLETYPER_URL = "https://data-nsr.udir.no/skoletyper"
NLOD_URL = "https://data.norge.no/nlod/no"
DATASET_ID = "udir:skoletyper"

OPENAPI = {
    "info": {
        "title": "Nasjonalt skoleregister API",
        "description": "Data fra Nasjonalt skoleregister (NSR).",
        "license": {"name": "Lisens: Norsk lisens for offentlige data (NLOD)", "url": NLOD_URL},
        "version": "1.0",
    },
    "paths": {
        "/enheter": {"get": {"summary": "Alle enheter"}},
        "/enhet/{id}": {"get": {"summary": "Get enhet"}},
        "/fylker": {"get": {"summary": "Alle fylker"}},
        "/skoletyper": {"get": {"summary": "Alle skoletyper"}},
    },
}
SKOLETYPER_BODY = [
    {
        "Navn": "Grunnskole",
        "NavnTekst": None,
        "Id": "1",
        "ErSystemType": True,
        "nested": {"skip": "dict"},
    },
    {
        "Navn": "Videregående skole",
        "NavnTekst": None,
        "Id": "2",
        "ErSystemType": True,
    },
]


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == OPENAPI_URL:
            return OPENAPI
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == SKOLETYPER_URL:
            return JsonResponse(status=200, url=url, body=SKOLETYPER_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"udir fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_paths() -> None:
    source = UdirNsrSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["enheter", "fylker", "skoletyper"]
    assert [ref.source_native_uri for ref in refs] == [
        ENHETER_URL,
        FYLKER_URL,
        SKOLETYPER_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_uses_openapi_origin_when_servers_absent() -> None:
    url = printed_endpoint_url(OPENAPI, "/skoletyper", OPENAPI_URL)
    assert url == SKOLETYPER_URL
    assert "/swagger/" not in url
    with_server = printed_endpoint_url(
        {"servers": [{"url": "https://data-nsr.udir.no/"}]},
        "/skoletyper",
        OPENAPI_URL,
    )
    assert with_server == SKOLETYPER_URL


def test_udir_is_a_registered_source() -> None:
    assert "udir" in SOURCE_IDS
    source = build_source("udir")
    assert isinstance(source, UdirNsrSource)
    assert source.source_id == "udir"


def test_harvest_writes_printed_id_license_and_null_publisher(tmp_path: Path) -> None:
    source = UdirNsrSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "udir"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == SKOLETYPER_URL
    assert row["title"] == "Alle skoletyper"
    assert row["publisher_name"] is None
    assert row["license"] == NLOD_URL
    assert not str(row["id"]).startswith("datanorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["udir_openapi_path"] == "/skoletyper"
    assert payload["license"] == NLOD_URL
    assert payload["publisher"] is None
    registry.close()


def test_fetch_gets_printed_skoletyper(tmp_path: Path) -> None:
    source = UdirNsrSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == SKOLETYPER_URL
    assert result.table_id == "skoletyper"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    assert [json.loads(row["value_json"]) for row in rows] == [
        "Grunnskole",
        "Videregående skole",
    ]
    assert all(row["measure"] == "Navn" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["Id"] == "1"
    assert dims["ErSystemType"] == "True"
    assert dims["NavnTekst"] == ""
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == NLOD_URL for row in rows)
    assert all(row["access_path"] == SKOLETYPER_URL for row in rows)
    registry.close()


def test_cells_copy_printed_navn() -> None:
    cells = cells_from_udir(SKOLETYPER_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "Navn"
    assert value == "Grunnskole"
    assert dims["Id"] == "1"
    fallback = cells_from_udir([{"Kode": "85.201", "Versjon": "2025"}])
    assert fallback == [("Kode", "85.201", {"Versjon": "2025"})]
    with pytest.raises(ValueError, match="JSON array"):
        cells_from_udir({"Navn": "Grunnskole"})


def test_is_udir_url_accepts_only_nsr_host() -> None:
    assert is_udir_nsr_url(SKOLETYPER_URL)
    assert is_udir_nsr_url(OPENAPI_URL)
    assert udir_table_id(SKOLETYPER_URL) == "skoletyper"
    assert printed_license_url(OPENAPI["info"]) == NLOD_URL
    assert printed_license_url({}) is None
    assert not is_udir_nsr_url("https://data.norge.no/datasets/x")
    assert not is_udir_nsr_url("https://www.udir.no/skoletyper")
    assert not is_udir_nsr_url("https://nsr.udir.no/skoletyper")
    assert not is_udir_nsr_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = UdirNsrSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=2)] == [
        "enheter",
        "fylker",
    ]
    nxt = source.list_dataset_refs(limit=1, offset=2)
    assert [ref.source_native_id for ref in nxt] == ["skoletyper"]
