from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.ssbkart import (
    SsbkartSource,
    cells_from_ssbkart,
    is_ssbkart_url,
    printed_collection_id,
    printed_collections,
    printed_items_url,
    ssbkart_table_id,
)

LIST_URL = "https://kart.ssb.no/api/core/v1/ogc/features/collections"
FYLKER_URL = (
    "https://kart.ssb.no/api/core/v1/ogc/features/collections/fylker_2024/items.json"
)
KOMMUNER_URL = (
    "https://kart.ssb.no/api/core/v1/ogc/features/collections/kommuner_2024/items.json"
)
TETTSTED_URL = (
    "https://kart.ssb.no/api/core/v1/ogc/features/collections/tettsted_2023/items.json"
)
SSB_PXWEB_URL = "https://data.ssb.no/api/v0/no/table/06683"
HI_URL = "https://kart.hi.no/data/ogc/features/v1/collections"
NGU_URL = "https://geo.ngu.no/api/features"
DATASET_ID = "ssbkart:fylker_2024"

COLLECTIONS = {
    "links": [{"href": LIST_URL, "rel": "self", "type": "application/json"}],
    "collections": [
        {
            "id": "0670625b-b717-7373-8000-43bd3cfe494d",
            "title": "Counties",
            "description": "The current counties of Norway.",
            "links": [
                {
                    "href": "https://kart.ssb.no/api/core/v1/ogc/features/collections/fylker_2024/items",
                    "rel": "items",
                    "type": "application/geo+json",
                },
                {"href": FYLKER_URL, "rel": "items", "type": "application/json"},
            ],
        },
        {
            "id": "0670625b-b75e-7cf6-8000-0accc3180cd2",
            "title": "Municipalities",
            "links": [
                {"href": KOMMUNER_URL, "rel": "items", "type": "application/json"},
            ],
        },
        {
            "id": "06751a7f-f15b-7c8c-8000-7352ca249836",
            "title": "Tettsted 2023",
            "links": [
                {"href": TETTSTED_URL, "rel": "items", "type": "application/json"},
            ],
        },
        {
            "id": "skip-no-items",
            "title": "Missing items",
            "links": [],
        },
        {
            "title": "Missing id",
            "links": [{"href": FYLKER_URL, "rel": "items", "type": "application/json"}],
        },
    ],
}
FYLKER_BODY = {
    "id": "fylker_2024",
    "total": 2,
    "limit": 100,
    "offset": 0,
    "data": [
        {"nr": "03", "navn": "Oslo", "geom": "MULTIPOLYGON(((10 59)))"},
        {
            "nr": "11",
            "navn": "Rogaland",
            "nested": {"skip": True},
        },
    ],
}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == LIST_URL:
            return COLLECTIONS
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == FYLKER_URL:
            return JsonResponse(status=200, url=url, body=FYLKER_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"ssbkart fetch must GET, not POST {url}")


def test_printed_refs_use_items_href_last_segment() -> None:
    source = SsbkartSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "fylker_2024",
        "kommuner_2024",
        "tettsted_2023",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        FYLKER_URL,
        KOMMUNER_URL,
        TETTSTED_URL,
    ]
    assert all(ref.source_native_id != "0670625b-b717-7373-8000-43bd3cfe494d" for ref in refs)
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)


def test_printed_collections_keep_document_order() -> None:
    listed = printed_collections(COLLECTIONS)
    assert [item["id"] for item in listed] == [
        "fylker_2024",
        "kommuner_2024",
        "tettsted_2023",
    ]
    assert listed[0]["catalog_id"] == "0670625b-b717-7373-8000-43bd3cfe494d"
    assert printed_items_url(COLLECTIONS["collections"][0]) == FYLKER_URL


def test_printed_collection_id_uses_collections_segment() -> None:
    assert printed_collection_id(FYLKER_URL) == "fylker_2024"
    assert printed_collection_id(KOMMUNER_URL) == "kommuner_2024"
    assert printed_collection_id(LIST_URL) is None


def test_ssbkart_is_a_registered_source() -> None:
    assert "ssbkart" in SOURCE_IDS
    assert "ssb" in SOURCE_IDS
    assert "hi" in SOURCE_IDS
    assert "ngu" in SOURCE_IDS
    source = build_source("ssbkart")
    assert isinstance(source, SsbkartSource)
    assert source.source_id == "ssbkart"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = SsbkartSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "ssbkart"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == FYLKER_URL
    assert row["title"] == "Counties"
    kommuner = registry.get_dataset("ssbkart:kommuner_2024")
    assert kommuner is not None
    assert kommuner["access_path"] == KOMMUNER_URL
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("ssb:")
    assert not str(row["id"]).startswith("hi:")
    assert not str(row["id"]).startswith("ngu:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["ssbkart_collection"]["id"] == "fylker_2024"
    assert payload["ssbkart_collection"]["items_url"] == FYLKER_URL
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_county_names(tmp_path: Path) -> None:
    source = SsbkartSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == FYLKER_URL
    assert result.table_id == "fylker_2024"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"Oslo", "Rogaland"}
    assert by_value["Oslo"]["measure"] == "navn"
    dims = json.loads(by_value["Oslo"]["dimensions_json"])
    assert dims["nr"] == "03"
    assert "geom" not in dims
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == FYLKER_URL for row in rows)
    registry.close()


def test_cells_copy_printed_name_and_skip_geom() -> None:
    cells = cells_from_ssbkart(FYLKER_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "navn"
    assert value == "Oslo"
    assert dims["nr"] == "03"
    assert "geom" not in dims
    catalog = cells_from_ssbkart(
        {
            "collections": [
                {"id": "fylker_2024", "title": "Counties", "extent": {"skip": True}}
            ]
        }
    )
    assert catalog == [("title", "Counties", {"id": "fylker_2024"})]
    named = cells_from_ssbkart(
        {"features": [{"properties": {"navn": "Oslo", "nr": "03"}}]}
    )
    assert named == [("navn", "Oslo", {"nr": "03"})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_ssbkart(None)
    with pytest.raises(ValueError, match="printed items wrapper"):
        cells_from_ssbkart({"title": "Counties"})
    with pytest.raises(ValueError, match="printed no records"):
        cells_from_ssbkart({"data": []})


def test_is_ssbkart_url_accepts_only_kart_ssb_collections() -> None:
    assert is_ssbkart_url(FYLKER_URL)
    assert is_ssbkart_url(LIST_URL)
    assert ssbkart_table_id(FYLKER_URL) == "fylker_2024"
    assert ssbkart_table_id(KOMMUNER_URL) == "kommuner_2024"
    assert not is_ssbkart_url(SSB_PXWEB_URL)
    assert not is_ssbkart_url(HI_URL)
    assert not is_ssbkart_url(NGU_URL)
    assert not is_ssbkart_url("https://data.norge.no/datasets/x")
    assert not is_ssbkart_url("https://kart.ssb.no/api/core/v1/datasets")
    assert not is_ssbkart_url(None)


def test_limit_and_offset_slice_printed_collections() -> None:
    source = SsbkartSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "fylker_2024"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["kommuner_2024"]
