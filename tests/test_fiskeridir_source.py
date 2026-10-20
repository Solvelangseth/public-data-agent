from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.fiskeridir import (
    FiskeridirVesselSource,
    cells_from_fiskeridir,
    fiskeridir_table_id,
    is_fiskeridir_vessel_url,
    printed_endpoint_url,
    printed_license_url,
)

OPENAPI_URL = "https://api.fiskeridir.no/vessel-api/api/openapi"
VESSELS_URL = "https://api.fiskeridir.no/vessel-api/api/v1/vessels"
LICENSE_URL = "https://www.fiskeridir.no/Tall-og-analyse/Lisens-for-bruk-av-Fiskeridirektoratets-data"
DATASET_ID = "fiskeridir:vessels"

OPENAPI = {
    "info": {
        "title": "Fartøyregisteret",
        "description": "Et åpent API for uthenting av fartøy- og eieropplysninger.",
        "license": {"name": "FDIR-lisens for databruk", "url": LICENSE_URL},
        "version": "1.0.0",
    },
    "servers": [{"url": "/"}],
    "paths": {
        "/vessel-api/api/v1/vessels": {"get": {"summary": "Lister aktive fartøy"}},
        "/vessel-api/api/v1/vessels/{id}": {"get": {"summary": "Returnerer et spesifikt fartøy"}},
        "/vessel-api/api/v1/ports": {"get": {"summary": "Lister havner"}},
    },
}
VESSELS_BODY = [
    {
        "id": "2026127799",
        "name": "KVALVIK",
        "registrationMark": "N 0063Ø",
        "radioCallSign": "LI6221",
        "municipalityCode": "1868",
        "tonnage": 0,
        "owners": [{"id": "837905052", "name": "HERMANSEN KYSTFISKE"}],
    },
    {
        "id": "2026127800",
        "name": "SVANHILD",
        "registrationMark": "N 0001A",
        "radioCallSign": None,
        "municipalityCode": "1804",
        "tonnage": 12,
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
        if url == VESSELS_URL:
            return JsonResponse(status=200, url=url, body=VESSELS_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"fiskeridir fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_paths() -> None:
    source = FiskeridirVesselSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["vessels", "ports"]
    assert [ref.source_native_uri for ref in refs] == [
        VESSELS_URL,
        "https://api.fiskeridir.no/vessel-api/api/v1/ports",
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_uses_origin_when_server_is_relative() -> None:
    url = printed_endpoint_url(OPENAPI, "/vessel-api/api/v1/vessels", OPENAPI_URL)
    assert url == VESSELS_URL
    assert "/openapi" not in url
    with_server = printed_endpoint_url(
        {"servers": [{"url": "https://api.fiskeridir.no/"}]},
        "/vessel-api/api/v1/vessels",
        OPENAPI_URL,
    )
    assert with_server == VESSELS_URL


def test_fiskeridir_is_a_registered_source() -> None:
    assert "fiskeridir" in SOURCE_IDS
    source = build_source("fiskeridir")
    assert isinstance(source, FiskeridirVesselSource)
    assert source.source_id == "fiskeridir"


def test_harvest_writes_printed_id_license_and_null_publisher(tmp_path: Path) -> None:
    source = FiskeridirVesselSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "fiskeridir"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == VESSELS_URL
    assert row["title"] == "Lister aktive fartøy"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["fiskeridir_openapi_path"] == "/vessel-api/api/v1/vessels"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    registry.close()


def test_fetch_gets_printed_vessels(tmp_path: Path) -> None:
    source = FiskeridirVesselSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == VESSELS_URL
    assert result.table_id == "vessels"
    assert result.http_status == 200
    assert result.counts.listed == 2
    # A vessel register. Build year and engine power describe a boat; they
    # are not a published statistic about boats.
    assert registry.observation_count() == 0
    rows = registry.list_records(DATASET_ID, kind="entity")
    assert [row["subject_label"] for row in rows] == ["KVALVIK", "SVANHILD"]
    assert rows[0]["subject_code"] == "2026127799"
    assert all(row["measure"] is None and row["value_json"] is None for row in rows)
    attributes = json.loads(rows[0]["attributes_json"])
    assert attributes["registrationMark"] == "N 0063Ø"
    assert attributes["radioCallSign"] == "LI6221"
    assert attributes["municipalityCode"] == "1868"
    assert attributes["tonnage"] == "0"
    assert "id" not in attributes
    assert "owners" not in attributes
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["request_url"] == VESSELS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_vessel_name() -> None:
    cells = cells_from_fiskeridir(VESSELS_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "KVALVIK"
    assert dims["id"] == "2026127799"
    assert "owners" not in dims
    fallback = cells_from_fiskeridir([{"id": "9", "registrationMark": "N 1"}])
    assert fallback == [("id", "9", {"registrationMark": "N 1"})]
    with pytest.raises(ValueError, match="JSON array"):
        cells_from_fiskeridir({"name": "KVALVIK"})


def test_is_fiskeridir_url_accepts_only_vessel_api_host() -> None:
    assert is_fiskeridir_vessel_url(VESSELS_URL)
    assert is_fiskeridir_vessel_url(OPENAPI_URL)
    assert fiskeridir_table_id(VESSELS_URL) == "vessels"
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({}) is None
    assert not is_fiskeridir_vessel_url("https://data.norge.no/datasets/x")
    assert not is_fiskeridir_vessel_url("https://www.fiskeridir.no/vessel-api/api/v1/vessels")
    assert not is_fiskeridir_vessel_url("https://api.fiskeridir.no/nytek-public/api/v3/certificates")
    assert not is_fiskeridir_vessel_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = FiskeridirVesselSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["vessels"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["ports"]
