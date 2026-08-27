from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.norskelos import (
    NorskelosSource,
    cells_from_norskelos,
    is_norskelos_url,
    norskelos_table_id,
    printed_collection_id,
    printed_items_url,
    printed_license_url,
)

OPENAPI_URL = "https://dnl.kartverket.no/api/ogc/v1/openapi"
COLLECTIONS_URL = "https://dnl.kartverket.no/api/ogc/v1/collections"
PLACE_ITEMS_URL = (
    "https://dnl.kartverket.no/api/ogc/v1/collections/dennorskelos/place/items?f=json"
)
SAILING_ITEMS_URL = (
    "https://dnl.kartverket.no/api/ogc/v1/collections/dennorskelos/sailingdirections/items?f=json"
)
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
DATASET_ID = "norskelos:place"

OPENAPI = {
    "openapi": "3.0.2",
    "info": {
        "title": "Den norske los",
        "description": "Beskrivelse av tjenesten.",
        "license": {"name": "CC-BY 4.0 license", "url": LICENSE_URL},
        "contact": {"name": "Kartverket", "url": "https://kartverket.no"},
        "version": "0.22.dev0",
    },
    "servers": [{"url": "https://dnl.kartverket.no/api/ogc/v1"}],
    "paths": {
        "/collections": {"get": {"summary": "Collections"}},
        "/collections/dennorskelos/place/items": {"get": {"summary": "Place items"}},
    },
}

COLLECTIONS = {
    "collections": [
        {
            "id": "dennorskelos/sailingdirections",
            "title": "Sailing directions",
            "description": "Collection of sailing description for the various fairways.",
            "links": [
                {
                    "rel": "self",
                    "type": "application/json",
                    "href": "https://dnl.kartverket.no/api/ogc/v1/collections/dennorskelos/sailingdirections?f=json",
                },
                {
                    "rel": "items",
                    "type": "application/geo+json",
                    "title": "Items as GeoJSON",
                    "href": SAILING_ITEMS_URL,
                },
            ],
        },
        {
            "id": "dennorskelos/place",
            "title": "Description of place",
            "description": "Contains a general description of a location or a port.",
            "links": [
                {
                    "rel": "items",
                    "type": "text/html",
                    "href": "https://dnl.kartverket.no/api/ogc/v1/collections/dennorskelos/place/items?f=html",
                },
                {
                    "rel": "items",
                    "type": "application/geo+json",
                    "title": "Items as GeoJSON",
                    "href": PLACE_ITEMS_URL,
                },
            ],
        },
        {
            "id": "missing-items",
            "title": "No items link",
            "links": [],
        },
        {
            "title": "missing-id",
            "links": [
                {
                    "rel": "items",
                    "type": "application/geo+json",
                    "href": "https://dnl.kartverket.no/api/ogc/v1/collections/blank/items?f=json",
                }
            ],
        },
    ]
}

PLACE_BODY = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "id": "01521c9a-209c-4a51-8546-05828fc6df54",
            "properties": {
                "id": "01521c9a-209c-4a51-8546-05828fc6df54",
                "title": "Fillan",
                "municipality": "Hitra",
                "county": "Trøndelag - Trööndelage",
                "objtype": "Tettsted",
            },
            "geometry": {"type": "Point", "coordinates": [8.97, 63.61]},
        },
        {
            "type": "Feature",
            "id": "other-id",
            "properties": {
                "title": "Askvoll",
                "municipality": "Askvoll",
                "county": "Vestland",
            },
            "geometry": {"type": "Point", "coordinates": [5.06, 61.34]},
        },
    ],
}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == COLLECTIONS_URL:
            return COLLECTIONS
        if url == OPENAPI_URL:
            return OPENAPI
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == PLACE_ITEMS_URL:
            return JsonResponse(status=200, url=url, body=PLACE_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"norskelos fetch must GET, not POST {url}")


def test_printed_refs_copy_collection_ids_and_items_hrefs() -> None:
    source = NorskelosSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["sailingdirections", "place"]
    assert [ref.source_native_uri for ref in refs] == [SAILING_ITEMS_URL, PLACE_ITEMS_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert "" not in [ref.source_native_id for ref in refs]


def test_printed_collection_id_is_last_segment() -> None:
    assert printed_collection_id({"id": "dennorskelos/place"}) == "place"
    assert (
        printed_collection_id({"id": "dennorskelos/sailingdirections"})
        == "sailingdirections"
    )


def test_printed_items_url_prefers_geojson() -> None:
    assert printed_items_url(COLLECTIONS["collections"][1]) == PLACE_ITEMS_URL
    assert printed_items_url(COLLECTIONS["collections"][0]) == SAILING_ITEMS_URL


def test_printed_license_url_copies_openapi_license() -> None:
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({"title": "Den norske los"}) is None


def test_norskelos_is_a_registered_source() -> None:
    assert "norskelos" in SOURCE_IDS
    assert "volcanicashforecast" in SOURCE_IDS
    assert "routeforecast" in SOURCE_IDS
    assert "sigcharts" in SOURCE_IDS
    assert "nlaroutes" in SOURCE_IDS
    source = build_source("norskelos")
    assert isinstance(source, NorskelosSource)
    assert source.source_id == "norskelos"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = NorskelosSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "norskelos"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == PLACE_ITEMS_URL
    assert row["title"] == "Description of place"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("met:")
    assert not str(row["id"]).startswith("volcanicashforecast:")
    assert not str(row["id"]).startswith("nlaroutes:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["norskelos_collection"]["id"] == "dennorskelos/place"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_place_items(tmp_path: Path) -> None:
    source = NorskelosSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == PLACE_ITEMS_URL
    assert result.table_id == "place"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["Fillan", "Askvoll"]
    assert all(row["measure"] == "title" for row in rows)
    assert [json.loads(row["dimensions_json"]) for row in rows] == [
        {
            "id": "01521c9a-209c-4a51-8546-05828fc6df54",
            "municipality": "Hitra",
            "county": "Trøndelag - Trööndelage",
            "objtype": "Tettsted",
        },
        {"id": "other-id", "municipality": "Askvoll", "county": "Vestland"},
    ]
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == PLACE_ITEMS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_titles() -> None:
    cells = cells_from_norskelos(PLACE_BODY)
    assert cells == [
        (
            "title",
            "Fillan",
            {
                "id": "01521c9a-209c-4a51-8546-05828fc6df54",
                "municipality": "Hitra",
                "county": "Trøndelag - Trööndelage",
                "objtype": "Tettsted",
            },
        ),
        ("title", "Askvoll", {"id": "other-id", "municipality": "Askvoll", "county": "Vestland"}),
    ]
    with pytest.raises(ValueError, match="FeatureCollection"):
        cells_from_norskelos({"reftimes": ["2026-06-09T11:00:00Z"]})
    with pytest.raises(ValueError, match="features array"):
        cells_from_norskelos({"type": "FeatureCollection"})


def test_is_norskelos_url_accepts_only_dnl_host_path() -> None:
    assert is_norskelos_url(PLACE_ITEMS_URL)
    assert is_norskelos_url(OPENAPI_URL)
    assert is_norskelos_url(COLLECTIONS_URL)
    assert norskelos_table_id(PLACE_ITEMS_URL) == "place"
    assert norskelos_table_id(SAILING_ITEMS_URL) == "sailingdirections"
    assert not is_norskelos_url(
        "https://api.met.no/weatherapi/volcanicashforecast/0.1/reftimes"
    )
    assert not is_norskelos_url(
        "https://api.met.no/weatherapi/routeforecast/2.0/locations"
    )
    assert not is_norskelos_url(
        "https://api.met.no/weatherapi/nlaroutes/1.0/locations"
    )
    assert not is_norskelos_url("https://ws.geonorge.no/hoydedata/v1/datakilder")
    assert not is_norskelos_url(
        "https://ws.geonorge.no/transformering/v1/projeksjoner"
    )
    assert not is_norskelos_url("https://api.kartverket.no/kommuneinfo/v1/fylker")
    assert not is_norskelos_url("https://data.norge.no/datasets/x")
    assert not is_norskelos_url(None)


def test_limit_and_offset_slice_printed_collections() -> None:
    source = NorskelosSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "sailingdirections"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["place"]
