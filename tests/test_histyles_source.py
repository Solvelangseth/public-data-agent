from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.histyles import (
    HistylesSource,
    cells_from_histyles,
    histyles_table_id,
    is_histyles_url,
    printed_json_get_hrefs,
    printed_operation_id,
)

LIST_URL = "https://kart.hi.no/data/ogc/styles/v1"
STYLES_URL = "https://kart.hi.no/data/ogc/styles/v1/styles?f=application%2Fjson"
CONFORMANCE_URL = (
    "https://kart.hi.no/data/ogc/styles/v1/conformance?f=application%2Fjson"
)
SELF_URL = "https://kart.hi.no/data/ogc/styles/v1/?f=application%2Fjson"
HTML_URL = "https://kart.hi.no/data/ogc/styles/v1/styles?f=text%2Fhtml"
OPENAPI_URL = (
    "https://kart.hi.no/data/ogc/styles/v1/openapi"
    "?f=application%2Fvnd.oai.openapi%2Bjson%3Bversion%3D3.0"
)
FEATURES_URL = "https://kart.hi.no/data/ogc/features/v1/collections"
COVERAGES_URL = (
    "https://kart.hi.no/data/ogc/coverages/v1/collections?f=application%2Fjson"
)
MAPS_URL = "https://kart.hi.no/data/ogc/maps/v1/collections?f=application%2Fjson"
DATASET_ID = "histyles:styles"

LANDING = {
    "title": "Styles Service",
    "links": [
        {"href": SELF_URL, "rel": "self", "type": "application/json", "title": "This document"},
        {
            "href": "https://kart.hi.no/data/ogc/styles/v1/?f=text%2Fhtml",
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
            "rel": "http://www.opengis.net/def/rel/ogc/1.0/conformance",
            "type": "application/json",
            "title": "Conformance declaration as application/json",
        },
        {
            "href": HTML_URL,
            "rel": "styles",
            "type": "text/html",
        },
        {
            "href": STYLES_URL,
            "rel": "styles",
            "type": "application/json",
            "title": "Styles Metadata as application/json",
        },
        {
            "href": "https://kart.hi.no/",
            "rel": "data",
            "type": "application/json",
        },
    ],
}
STYLES_BODY = {
    "styles": [
        {"id": "spredningssimulering:spredningssimulering_torsk", "title": "Spredningssimulering torsk"},
        {
            "id": "spredningssimulering:spredningssimulering_torsk_conc_2022_29_30d",
            "title": "spredningssimulering_torsk_conc_2022_29_30d",
            "nested": {"skip": True},
        },
    ],
    "links": [{"rel": "self", "href": STYLES_URL, "type": "application/json"}],
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
        if url == STYLES_URL:
            return JsonResponse(status=200, url=url, body=STYLES_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"histyles fetch must GET, not POST {url}")


def test_printed_refs_skip_self_alternate_html_and_empty_segment() -> None:
    source = HistylesSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["conformance", "styles"]
    assert [ref.source_native_uri for ref in refs] == [CONFORMANCE_URL, STYLES_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert SELF_URL not in [ref.source_native_uri for ref in refs]
    assert HTML_URL not in [ref.source_native_uri for ref in refs]
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]
    assert all(ref.source_native_id != "" for ref in refs)
    assert all(ref.source_native_id != "v1" for ref in refs)


def test_printed_json_get_hrefs_keep_document_order() -> None:
    listed = printed_json_get_hrefs(LANDING)
    assert [ident for ident, _href, _title in listed] == ["conformance", "styles"]
    assert [href for _ident, href, _title in listed] == [CONFORMANCE_URL, STYLES_URL]


def test_printed_operation_id_uses_last_path_segment() -> None:
    assert printed_operation_id(STYLES_URL) == "styles"
    assert printed_operation_id(CONFORMANCE_URL) == "conformance"
    assert printed_operation_id("https://kart.hi.no/") is None


def test_histyles_is_a_registered_source() -> None:
    assert "histyles" in SOURCE_IDS
    assert "hi" in SOURCE_IDS
    assert "hicoverages" in SOURCE_IDS
    assert "himaps" in SOURCE_IDS
    assert "stortinget" in SOURCE_IDS
    source = build_source("histyles")
    assert isinstance(source, HistylesSource)
    assert source.source_id == "histyles"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = HistylesSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "histyles"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == STYLES_URL
    assert row["title"] == "Styles Metadata as application/json"
    conformance = registry.get_dataset("histyles:conformance")
    assert conformance is not None
    assert conformance["access_path"] == CONFORMANCE_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("hi:")
    assert not str(row["id"]).startswith("hicoverages:")
    assert not str(row["id"]).startswith("himaps:")
    assert not str(row["id"]).startswith("stortinget:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["histyles_landing_id"] == "styles"
    assert payload["histyles_landing_href"] == STYLES_URL
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_style_titles(tmp_path: Path) -> None:
    source = HistylesSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == STYLES_URL
    assert result.table_id == "styles"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {
        "Spredningssimulering torsk",
        "spredningssimulering_torsk_conc_2022_29_30d",
    }
    assert by_value["Spredningssimulering torsk"]["measure"] == "title"
    dims = json.loads(by_value["Spredningssimulering torsk"]["dimensions_json"])
    assert dims["id"] == "spredningssimulering:spredningssimulering_torsk"
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == STYLES_URL for row in rows)
    registry.close()


def test_cells_copy_printed_title_or_scalar() -> None:
    cells = cells_from_histyles(STYLES_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "title"
    assert value == "Spredningssimulering torsk"
    assert dims["id"] == "spredningssimulering:spredningssimulering_torsk"
    assert "nested" not in dims
    assert cells_from_histyles({"conformsTo": ["http://example.test/core"]}) == [
        ("value", "http://example.test/core", {})
    ]
    assert cells_from_histyles(
        {"title": "Spredningssimulering torsk", "id": "spredningssimulering:spredningssimulering_torsk"}
    ) == [
        ("title", "Spredningssimulering torsk", {"id": "spredningssimulering:spredningssimulering_torsk"})
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_histyles(None)
    with pytest.raises(ValueError, match="style members"):
        cells_from_histyles([])


def test_is_histyles_url_accepts_only_styles_host_path() -> None:
    assert is_histyles_url(STYLES_URL)
    assert is_histyles_url(CONFORMANCE_URL)
    assert is_histyles_url(LIST_URL)
    assert histyles_table_id(STYLES_URL) == "styles"
    assert histyles_table_id(CONFORMANCE_URL) == "conformance"
    assert not is_histyles_url(FEATURES_URL)
    assert not is_histyles_url(COVERAGES_URL)
    assert not is_histyles_url(MAPS_URL)
    assert not is_histyles_url("https://kartverket-ogc-api.azurewebsites.net/collections")
    assert not is_histyles_url("https://data.stortinget.no/eksport/stortingsperioder")
    assert not is_histyles_url("https://data.norge.no/datasets/x")
    assert not is_histyles_url(None)


def test_limit_and_offset_slice_printed_hrefs() -> None:
    source = HistylesSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "conformance"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["styles"]
