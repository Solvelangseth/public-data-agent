from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.buyer import (
    BuyerSource,
    buyer_table_id,
    cells_from_buyer,
    is_buyer_url,
    printed_endpoint_url,
    printed_license_url,
)

OPENAPI_URL = "https://api.fiskeridir.no/buyer-api/openapi"
LOCATIONS_URL = "https://api.fiskeridir.no/buyer-api/v1/locations"
LICENSE_URL = "https://www.fiskeridir.no/Tall-og-analyse/Lisens-for-bruk-av-Fiskeridirektoratets-data"
DATASET_ID = "buyer:locations"

OPENAPI = {
    "info": {
        "title": "Kjøperregisteret",
        "description": "Et åpent API for uthenting av kjøpere/kjøpssteder",
        "license": {"name": "FDIR-lisens for databruk", "url": LICENSE_URL},
        "version": "1.0.0",
    },
    "servers": [{"url": "https://api.fiskeridir.no"}],
    "paths": {
        "/buyer-api/v1/locations": {"get": {"summary": "Utlisting og søk etter aktive kjøpssteder"}},
        "/buyer-api/v1/locations/{locationId}": {"get": {"summary": "Slå opp et kjøpssted"}},
        "/buyer-api/v1/buyers": {"get": {"summary": "Lister kjøpere"}},
    },
}
LOCATIONS_BODY = [
    {
        "locationId": 200092526,
        "parent": 200092518,
        "locationType": "DOCK_SALESPERSON_T",
        "mainLegalEntityId": "990264554",
        "name": None,
        "created": "2026-08-27T06:40:11.516484",
        "address": {"address": "Ekkilsøyveien 291", "postalCode": "6530"},
    },
    {
        "locationId": 200092518,
        "parent": 200092500,
        "locationType": "DOCK_SALESPERSON_T",
        "legalEntityId": "934729641",
        "name": "TOR GUNNAR EKKILSØY",
        "created": "2026-08-27T06:40:11.516484",
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
        if url == LOCATIONS_URL:
            return JsonResponse(status=200, url=url, body=LOCATIONS_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"buyer fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_paths() -> None:
    source = BuyerSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["locations", "buyers"]
    assert [ref.source_native_uri for ref in refs] == [
        LOCATIONS_URL,
        "https://api.fiskeridir.no/buyer-api/v1/buyers",
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_uses_printed_absolute_server() -> None:
    url = printed_endpoint_url(OPENAPI, "/buyer-api/v1/locations", OPENAPI_URL)
    assert url == LOCATIONS_URL
    assert "/openapi" not in url
    relative = printed_endpoint_url(
        {"servers": [{"url": "/"}]},
        "/buyer-api/v1/locations",
        OPENAPI_URL,
    )
    assert relative == LOCATIONS_URL


def test_buyer_is_a_registered_source() -> None:
    assert "buyer" in SOURCE_IDS
    source = build_source("buyer")
    assert isinstance(source, BuyerSource)
    assert source.source_id == "buyer"


def test_harvest_writes_printed_id_license_and_null_publisher(tmp_path: Path) -> None:
    source = BuyerSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "buyer"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == LOCATIONS_URL
    assert row["title"] == "Utlisting og søk etter aktive kjøpssteder"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("fiskeridir:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["buyer_openapi_path"] == "/buyer-api/v1/locations"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_locations(tmp_path: Path) -> None:
    source = BuyerSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == LOCATIONS_URL
    assert result.table_id == "locations"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {200092526, "TOR GUNNAR EKKILSØY"}
    assert by_value[200092526]["measure"] == "locationId"
    assert by_value["TOR GUNNAR EKKILSØY"]["measure"] == "name"
    dims = json.loads(by_value[200092526]["dimensions_json"])
    assert dims["parent"] == "200092518"
    assert dims["locationType"] == "DOCK_SALESPERSON_T"
    assert dims["mainLegalEntityId"] == "990264554"
    assert "address" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == LOCATIONS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_name_or_location_id() -> None:
    cells = cells_from_buyer(LOCATIONS_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[1]
    assert measure == "name"
    assert value == "TOR GUNNAR EKKILSØY"
    assert dims["locationId"] == "200092518"
    assert "address" not in dims
    fallback = cells_from_buyer([{"locationId": 9, "name": None}])
    assert fallback == [("locationId", 9, {"name": ""})]
    with pytest.raises(ValueError, match="JSON array"):
        cells_from_buyer({"name": "TOR GUNNAR EKKILSØY"})


def test_is_buyer_url_accepts_only_buyer_api_path() -> None:
    assert is_buyer_url(LOCATIONS_URL)
    assert is_buyer_url(OPENAPI_URL)
    assert buyer_table_id(LOCATIONS_URL) == "locations"
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({}) is None
    assert not is_buyer_url("https://api.fiskeridir.no/vessel-api/api/v1/vessels")
    assert not is_buyer_url("https://data.norge.no/datasets/x")
    assert not is_buyer_url("https://www.fiskeridir.no/buyer-api/v1/locations")
    assert not is_buyer_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = BuyerSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["locations"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["buyers"]
