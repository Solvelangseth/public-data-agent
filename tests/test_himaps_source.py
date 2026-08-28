from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.himaps import (
    HimapsSource,
    cells_from_himaps,
    himaps_table_id,
    is_himaps_url,
    printed_json_get_hrefs,
    printed_operation_id,
)

LIST_URL = "https://kart.hi.no/data/ogc/maps/v1"
COLLECTIONS_URL = (
    "https://kart.hi.no/data/ogc/maps/v1/collections?f=application%2Fjson"
)
CONFORMANCE_URL = (
    "https://kart.hi.no/data/ogc/maps/v1/conformance?f=application%2Fjson"
)
SELF_URL = "https://kart.hi.no/data/ogc/maps/v1/?f=application%2Fjson"
HTML_URL = "https://kart.hi.no/data/ogc/maps/v1/collections?f=text%2Fhtml"
OPENAPI_URL = (
    "https://kart.hi.no/data/ogc/maps/v1/openapi"
    "?f=application%2Fvnd.oai.openapi%2Bjson%3Bversion%3D3.0"
)
FEATURES_URL = "https://kart.hi.no/data/ogc/features/v1/collections"
COVERAGES_URL = (
    "https://kart.hi.no/data/ogc/coverages/v1/collections?f=application%2Fjson"
)
DATASET_ID = "himaps:collections"

LANDING = {
    "title": "Maps 1.0 server",
    "links": [
        {"href": SELF_URL, "rel": "self", "type": "application/json", "title": "This document"},
        {
            "href": "https://kart.hi.no/data/ogc/maps/v1/?f=text%2Fhtml",
            "rel": "alternate",
            "type": "text/html",
        },
        {
            "href": OPENAPI_URL,
            "rel": "service-desc",
            "type": "application/vnd.oai.openapi+json;version=3.0",
        },
        {
            "href": CONFORMANCE_URL,
            "rel": "conformance",
            "type": "application/json",
        },
        {
            "href": HTML_URL,
            "rel": "data",
            "type": "text/html",
        },
        {
            "href": COLLECTIONS_URL,
            "rel": "data",
            "type": "application/json",
        },
        {
            "href": "https://kart.hi.no/",
            "rel": "data",
            "type": "application/json",
        },
    ],
}
COLLECTIONS_BODY = {
    "collections": [
        {"id": "spredningssimulering:reprojected", "title": "reprojected"},
        {
            "id": "spredningssimulering:spredningssimulering_torsk_conc_2022_29_30d",
            "title": "spredningssimulering_torsk_conc_2022_29_30d",
            "nested": {"skip": True},
        },
    ],
    "links": [{"rel": "self", "href": COLLECTIONS_URL, "type": "application/json"}],
}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == LIST_URL:
            return LANDING
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == COLLECTIONS_URL:
            return JsonResponse(status=200, url=url, body=COLLECTIONS_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"himaps fetch must GET, not POST {url}")


def test_printed_refs_skip_self_alternate_html_and_empty_segment() -> None:
    source = HimapsSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["conformance", "collections"]
    assert [ref.source_native_uri for ref in refs] == [CONFORMANCE_URL, COLLECTIONS_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert SELF_URL not in [ref.source_native_uri for ref in refs]
    assert HTML_URL not in [ref.source_native_uri for ref in refs]
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "v1" for ref in refs)


def test_printed_json_get_hrefs_keep_document_order() -> None:
    listed = printed_json_get_hrefs(LANDING)
    assert [ident for ident, _href, _title in listed] == ["conformance", "collections"]
    assert [href for _ident, href, _title in listed] == [CONFORMANCE_URL, COLLECTIONS_URL]


def test_printed_operation_id_uses_last_path_segment() -> None:
    assert printed_operation_id(COLLECTIONS_URL) == "collections"
    assert printed_operation_id(CONFORMANCE_URL) == "conformance"
    assert printed_operation_id("https://kart.hi.no/") is None


def test_himaps_is_a_registered_source() -> None:
    assert "himaps" in SOURCE_IDS
    assert "hi" in SOURCE_IDS
    assert "hicoverages" in SOURCE_IDS
    assert "ogccoverages" in SOURCE_IDS
    source = build_source("himaps")
    assert isinstance(source, HimapsSource)
    assert source.source_id == "himaps"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = HimapsSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "himaps"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == COLLECTIONS_URL
    assert row["title"] == "collections"
    conformance = registry.get_dataset("himaps:conformance")
    assert conformance is not None
    assert conformance["access_path"] == CONFORMANCE_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("hi:")
    assert not str(row["id"]).startswith("hicoverages:")
    assert not str(row["id"]).startswith("ogccoverages:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["himaps_landing_id"] == "collections"
    assert payload["himaps_landing_href"] == COLLECTIONS_URL
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_collection_titles(tmp_path: Path) -> None:
    source = HimapsSource(http=CatalogHttp())
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
        "reprojected",
        "spredningssimulering_torsk_conc_2022_29_30d",
    }
    assert by_value["reprojected"]["measure"] == "title"
    dims = json.loads(by_value["reprojected"]["dimensions_json"])
    assert dims["id"] == "spredningssimulering:reprojected"
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == COLLECTIONS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_title_or_scalar() -> None:
    cells = cells_from_himaps(COLLECTIONS_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "title"
    assert value == "reprojected"
    assert dims["id"] == "spredningssimulering:reprojected"
    assert "nested" not in dims
    assert cells_from_himaps({"conformsTo": ["http://example.test/core"]}) == [
        ("value", "http://example.test/core", {})
    ]
    assert cells_from_himaps({"title": "reprojected", "id": "spredningssimulering:reprojected"}) == [
        ("title", "reprojected", {"id": "spredningssimulering:reprojected"})
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_himaps(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_himaps([])


def test_is_himaps_url_accepts_only_maps_host_path() -> None:
    assert is_himaps_url(COLLECTIONS_URL)
    assert is_himaps_url(CONFORMANCE_URL)
    assert is_himaps_url(LIST_URL)
    assert himaps_table_id(COLLECTIONS_URL) == "collections"
    assert himaps_table_id(CONFORMANCE_URL) == "conformance"
    assert not is_himaps_url(FEATURES_URL)
    assert not is_himaps_url(COVERAGES_URL)
    assert not is_himaps_url("https://kartverket-ogc-api.azurewebsites.net/collections")
    assert not is_himaps_url("https://api.cristin.no/v2/countries")
    assert not is_himaps_url("https://data.norge.no/datasets/x")
    assert not is_himaps_url(None)


def test_limit_and_offset_slice_printed_hrefs() -> None:
    source = HimapsSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "conformance"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["collections"]
