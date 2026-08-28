from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.havnedata import (
    HavnedataSource,
    cells_from_havnedata,
    havnedata_table_id,
    is_havnedata_url,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://ogcapitest.kartverket.no/rest/services/havnedata3_0/api?f=json"
COLLECTIONS_URL = "https://ogcapitest.kartverket.no/rest/services/havnedata3_0/collections"
AVFALL_URL = (
    "https://ogcapitest.kartverket.no/rest/services/havnedata3_0/collections/avfallspunkt"
)
CONFORMANCE_URL = "https://ogcapitest.kartverket.no/rest/services/havnedata3_0/conformance"
TEMPLATED_URL = (
    "https://ogcapitest.kartverket.no/rest/services/havnedata3_0/collections/{collectionId}"
)
OGCCOVERAGES_URL = "https://kartverket-ogc-api.azurewebsites.net/collections"
NORSKELOS_URL = "https://dnl.kartverket.no/api/ogc/v1/collections"
MILJORAPPORTER_URL = "https://api.fiskeridir.no/miljorapporter-api/api/v1/env-reports"
DATASET_ID = "havnedata:collections"

OPENAPI = {
    "openapi": "3.0.3",
    "info": {
        "title": "Havnedata 3.0",
        "description": "OGC API Features for Kartverket Havnedata",
        "version": "3.0",
    },
    "servers": [
        {
            "url": "https://ogcapitest.kartverket.no/rest/services/havnedata3_0",
        }
    ],
    "paths": {
        "/": {"get": {"summary": "landing page", "operationId": "getLandingPage"}},
        "/conformance": {
            "get": {
                "summary": "conformance declaration",
                "operationId": "getConformanceDeclaration",
            }
        },
        "/collections": {
            "get": {
                "summary": "feature collections in the dataset 'Havnedata 3.0'",
                "operationId": "getCollections",
            }
        },
        "/collections/{collectionId}": {
            "get": {
                "operationId": "getCollection",
                "parameters": [
                    {"name": "collectionId", "in": "path", "required": True},
                ],
            }
        },
        "/collections/avfallspunkt": {
            "get": {
                "summary": "feature collection 'avfallspunkt'",
                "operationId": "avfallspunkt.getCollection",
            }
        },
        "/collections/avfallspunkt/items": {
            "get": {
                "summary": "retrieve features in the feature collection 'avfallspunkt'",
                "operationId": "avfallspunkt.getItems",
                "parameters": [
                    {"name": "limit", "in": "query", "required": False},
                ],
            }
        },
        "/collections/required-filter": {
            "get": {
                "operationId": "requiredFilter",
                "parameters": [
                    {"name": "bbox", "in": "query", "required": True},
                ],
            }
        },
    },
}
COLLECTIONS_BODY = {
    "title": "Havnedata 3.0",
    "collections": [
        {
            "id": "administrativthavneomrade",
            "title": "administrativthavneområde",
            "itemType": "feature",
            "nested": {"skip": True},
        },
        {
            "id": "avfallspunkt",
            "title": "avfallspunkt",
            "itemType": "feature",
        },
    ],
}
ITEMS_BODY = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "id": "avfallspunkt.1",
            "geometry": {"type": "Point", "coordinates": [5.0, 60.0]},
            "properties": {
                "havnNavn": "Bergen",
                "kainavn": "Festningskaien",
                "datafangstdato": "1900-01-01",
                "identifikasjon": {"lokalId": "skip"},
            },
        },
        {
            "type": "Feature",
            "id": "avfallspunkt.2",
            "properties": {
                "havnNavn": "Oslo",
                "UNLOCODE": "NOOSL",
            },
        },
    ],
}


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
        if url == COLLECTIONS_URL:
            return JsonResponse(status=200, url=url, body=COLLECTIONS_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"havnedata fetch must GET, not POST {url}")


def test_printed_refs_skip_root_templated_and_required() -> None:
    source = HavnedataSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "conformance",
        "collections",
        "collections/avfallspunkt",
        "collections/avfallspunkt/items",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        CONFORMANCE_URL,
        COLLECTIONS_URL,
        AVFALL_URL,
        f"{AVFALL_URL}/items",
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]
    assert TEMPLATED_URL not in [ref.source_native_uri for ref in refs]
    assert all(ref.source_native_id != "collections/required-filter" for ref in refs)
    assert "" not in [ref.source_native_id for ref in refs]


def test_endpoint_url_uses_printed_server() -> None:
    url = printed_endpoint_url(OPENAPI, "/collections", OPENAPI_URL)
    assert url == COLLECTIONS_URL
    assert "api" not in urlsplit_path_only(url)
    origin_only = printed_endpoint_url({}, "/collections", OPENAPI_URL)
    assert origin_only == "https://ogcapitest.kartverket.no/collections"


def urlsplit_path_only(url: str) -> str:
    from urllib.parse import urlsplit

    return urlsplit(url).path


def test_printed_operation_id_keeps_collection_path() -> None:
    assert printed_operation_id("/collections") == "collections"
    assert printed_operation_id("/collections/avfallspunkt") == "collections/avfallspunkt"
    assert printed_operation_id("/conformance") == "conformance"


def test_printed_license_url_stays_null_without_printed_url() -> None:
    assert printed_license_url(OPENAPI["info"]) is None
    assert printed_license_url({"license": {"name": "NLOD"}}) is None
    assert (
        printed_license_url({"license": {"url": "https://creativecommons.org/licenses/by/4.0/"}})
        == "https://creativecommons.org/licenses/by/4.0/"
    )


def test_havnedata_is_a_registered_source() -> None:
    assert "havnedata" in SOURCE_IDS
    assert "ogccoverages" in SOURCE_IDS
    assert "norskelos" in SOURCE_IDS
    assert "georegister" in SOURCE_IDS
    assert "miljorapporter" in SOURCE_IDS
    source = build_source("havnedata")
    assert isinstance(source, HavnedataSource)
    assert source.source_id == "havnedata"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = HavnedataSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 4
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "havnedata"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == COLLECTIONS_URL
    assert row["title"] == "feature collections in the dataset 'Havnedata 3.0'"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("ogccoverages:")
    assert not str(row["id"]).startswith("norskelos:")
    assert not str(row["id"]).startswith("miljorapporter:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["havnedata_openapi_path"] == "/collections"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_collections(tmp_path: Path) -> None:
    source = HavnedataSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == COLLECTIONS_URL
    assert result.table_id == "collections"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"administrativthavneområde", "avfallspunkt"}
    assert by_value["avfallspunkt"]["measure"] == "title"
    dims = json.loads(by_value["avfallspunkt"]["dimensions_json"])
    assert dims["id"] == "avfallspunkt"
    assert dims["itemType"] == "feature"
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == COLLECTIONS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_collection_title_or_feature_name() -> None:
    cells = cells_from_havnedata(COLLECTIONS_BODY)
    assert cells[0][0] == "title"
    assert cells[0][1] == "administrativthavneområde"
    assert cells[0][2]["id"] == "administrativthavneomrade"
    assert "nested" not in cells[0][2]
    features = cells_from_havnedata(ITEMS_BODY)
    assert features[0][0] == "havnNavn"
    assert features[0][1] == "Bergen"
    assert features[0][2]["kainavn"] == "Festningskaien"
    assert "identifikasjon" not in features[0][2]
    assert features[1][1] == "Oslo"
    assert cells_from_havnedata({"conformsTo": ["http://example.test/conf"]}) == [
        ("value", "http://example.test/conf", {"value": "http://example.test/conf"})
    ]
    assert cells_from_havnedata("avfallspunkt") == [
        ("value", "avfallspunkt", {"value": "avfallspunkt"})
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_havnedata(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_havnedata([])


def test_is_havnedata_url_accepts_only_havnedata_path() -> None:
    assert is_havnedata_url(COLLECTIONS_URL)
    assert is_havnedata_url(OPENAPI_URL)
    assert havnedata_table_id(COLLECTIONS_URL) == "collections"
    assert havnedata_table_id(AVFALL_URL) == "collections/avfallspunkt"
    assert printed_endpoint_url(OPENAPI, "/collections", OPENAPI_URL) == COLLECTIONS_URL
    assert not is_havnedata_url(OGCCOVERAGES_URL)
    assert not is_havnedata_url(NORSKELOS_URL)
    assert not is_havnedata_url(MILJORAPPORTER_URL)
    assert not is_havnedata_url("https://kart.hi.no/data/ogc/tiles/v1")
    assert not is_havnedata_url("https://data.norge.no/datasets/x")
    assert not is_havnedata_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = HavnedataSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "conformance"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["collections"]
    assert source.list_dataset_refs(limit=1, offset=4) == []
