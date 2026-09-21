from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.ogccoverages import (
    OgccoveragesSource,
    cells_from_ogccoverages,
    is_ogccoverages_url,
    ogccoverages_table_id,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://kartverket-ogc-api.azurewebsites.net/openapi?f=json"
COLLECTIONS_URL = "https://kartverket-ogc-api.azurewebsites.net/collections"
DTM_URL = "https://kartverket-ogc-api.azurewebsites.net/collections/dtm-10-terrengmodell"
COVERAGE_URL = "https://kartverket-ogc-api.azurewebsites.net/collections/dtm-10-terrengmodell/coverage"
CONFORMANCE_URL = "https://kartverket-ogc-api.azurewebsites.net/conformance"
PROCESSES_URL = "https://kartverket-ogc-api.azurewebsites.net/processes"
DATASET_ID = "ogccoverages:collections"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"

OPENAPI = {
    "openapi": "3.0.2",
    "info": {
        "title": "OGC API-tjenester - Kartverket",
        "description": "OGC API Coverages and Processes",
        "license": {"name": "CC-BY 4.0 license", "url": LICENSE_URL},
        "contact": {"name": "Kartverket", "email": "tjenestedrift@kartverket.no"},
        "version": "0.13.dev0",
    },
    "servers": [{"url": "https://kartverket-ogc-api.azurewebsites.net/"}],
    "paths": {
        "/": {"get": {"summary": "Landing page"}},
        "/collections": {"get": {"summary": "Collections"}},
        "/collections/dtm-10-terrengmodell": {
            "get": {"summary": "Get DTM 10 Terrengmodell (UTM32) metadata"},
        },
        "/collections/dtm-10-terrengmodell/coverage": {
            "get": {"summary": "Get DTM 10 Terrengmodell (UTM32) coverage"},
        },
        "/collections/{collectionId}": {
            "get": {
                "summary": "templated",
                "parameters": [
                    {"name": "collectionId", "in": "path", "required": True},
                ],
            }
        },
        "/conformance": {"get": {"summary": "API conformance definition"}},
        "/processes": {
            "get": {
                "summary": "Processes",
                "parameters": [
                    {"name": "limit", "in": "query", "required": True, "schema": {"type": "integer"}},
                ],
            }
        },
        "/processes/fullstendighetsdekning/execution": {
            "post": {"summary": "Process execution"},
        },
    },
}
COLLECTIONS_BODY = {
    "collections": [
        {"id": "dtm-10-terrengmodell", "title": "DTM 10 Terrengmodell (UTM32)"},
        {
            "id": "dybdedata-terrengmodell-50-meters-grid-rogaland",
            "title": "Dybdedata - terrengmodell 50 meters grid for Rogaland",
            "nested": {"skip": True},
        },
    ],
    "links": [{"rel": "self", "href": COLLECTIONS_URL}],
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
        raise AssertionError(f"ogccoverages fetch must GET, not POST {url}")


def test_printed_refs_skip_root_templated_required_and_post_paths() -> None:
    source = OgccoveragesSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "collections",
        "collections/dtm-10-terrengmodell",
        "collections/dtm-10-terrengmodell/coverage",
        "conformance",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        COLLECTIONS_URL,
        DTM_URL,
        COVERAGE_URL,
        CONFORMANCE_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]
    assert PROCESSES_URL not in [ref.source_native_uri for ref in refs]
    assert "" not in [ref.source_native_id for ref in refs]
    assert all(ref.source_native_id != "processes" for ref in refs)
    assert all("execution" not in (ref.source_native_id or "") for ref in refs)


def test_endpoint_url_uses_printed_server() -> None:
    url = printed_endpoint_url(OPENAPI, "/collections", OPENAPI_URL)
    assert url == COLLECTIONS_URL
    assert "openapi" not in url
    with_host = printed_endpoint_url(
        {
            "host": "kartverket-ogc-api.azurewebsites.net",
            "schemes": ["https"],
        },
        "/collections",
        OPENAPI_URL,
    )
    assert with_host == COLLECTIONS_URL
    origin_only = printed_endpoint_url({}, "/collections", OPENAPI_URL)
    assert origin_only == COLLECTIONS_URL


def test_printed_operation_id_is_path_without_leading_slash() -> None:
    assert printed_operation_id("/collections") == "collections"
    assert (
        printed_operation_id("/collections/dtm-10-terrengmodell/coverage")
        == "collections/dtm-10-terrengmodell/coverage"
    )


def test_printed_license_url_copies_openapi_license() -> None:
    assert printed_license_url(OPENAPI["info"]) == LICENSE_URL
    assert printed_license_url({"title": "OGC"}) is None
    assert printed_license_url({"license": {"name": "CC-BY 4.0 license"}}) is None


def test_ogccoverages_is_a_registered_source() -> None:
    assert "ogccoverages" in SOURCE_IDS
    assert "artskart" in SOURCE_IDS
    assert "nortaxa" in SOURCE_IDS
    assert "georegister" in SOURCE_IDS
    assert "hoydedata" in SOURCE_IDS
    source = build_source("ogccoverages")
    assert isinstance(source, OgccoveragesSource)
    assert source.source_id == "ogccoverages"


def test_harvest_writes_printed_id_license_and_null_publisher(tmp_path: Path) -> None:
    source = OgccoveragesSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    assert counts.ignored == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "ogccoverages"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == COLLECTIONS_URL
    assert row["title"] == "Collections"
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("nortaxa:")
    assert not str(row["id"]).startswith("georegister:")
    assert not str(row["id"]).startswith("hoydedata:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["ogccoverages_openapi_path"] == "/collections"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_collection_titles(tmp_path: Path) -> None:
    source = OgccoveragesSource(http=CatalogHttp())
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
    assert set(by_value) == {
        "DTM 10 Terrengmodell (UTM32)",
        "Dybdedata - terrengmodell 50 meters grid for Rogaland",
    }
    assert by_value["DTM 10 Terrengmodell (UTM32)"]["measure"] == "title"
    dims = json.loads(by_value["DTM 10 Terrengmodell (UTM32)"]["dimensions_json"])
    assert dims["id"] == "dtm-10-terrengmodell"
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == COLLECTIONS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_title_or_scalar() -> None:
    cells = cells_from_ogccoverages(COLLECTIONS_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "title"
    assert value == "DTM 10 Terrengmodell (UTM32)"
    assert dims["id"] == "dtm-10-terrengmodell"
    assert "nested" not in dims
    fallback = cells_from_ogccoverages({"processes": [{"name": "Fullstendighetsdekning", "id": "x"}]})
    assert fallback == [("name", "Fullstendighetsdekning", {"id": "x"})]
    assert cells_from_ogccoverages({"conformsTo": ["http://example.test/core"]}) == [
        ("value", "http://example.test/core", {})
    ]
    assert cells_from_ogccoverages({"title": "DTM 10 Terrengmodell (UTM32)", "id": "dtm"}) == [
        ("title", "DTM 10 Terrengmodell (UTM32)", {"id": "dtm"})
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_ogccoverages(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_ogccoverages([])


def test_is_ogccoverages_url_accepts_only_ogc_host() -> None:
    assert is_ogccoverages_url(COLLECTIONS_URL)
    assert is_ogccoverages_url(OPENAPI_URL)
    assert ogccoverages_table_id(COLLECTIONS_URL) == "collections"
    assert printed_endpoint_url(OPENAPI, "/collections", OPENAPI_URL) == COLLECTIONS_URL
    assert not is_ogccoverages_url("https://nortaxa.artsdatabanken.no/api/v1/Lists/RankList")
    assert not is_ogccoverages_url("https://register.geonorge.no/api/v2/organisasjoner/kommuner")
    assert not is_ogccoverages_url("https://hoydedata.kartverket.no/api/v1/punkt")
    assert not is_ogccoverages_url("https://artskart.artsdatabanken.no/publicapi/api/observations/list")
    assert not is_ogccoverages_url("https://data.norge.no/datasets/x")
    assert not is_ogccoverages_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = OgccoveragesSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "collections"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=2)
    assert [ref.source_native_id for ref in nxt] == [
        "collections/dtm-10-terrengmodell/coverage"
    ]
