from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.vegvesen import (
    VegvesenSource,
    cells_from_vegvesen,
    is_vegvesen_url,
    printed_license_url,
    printed_package_show_url,
    printed_publisher,
    vegvesen_table_id,
)

LIST_URL = "https://dataut.vegvesen.no/api/3/action/package_list"
ARTS_URL = "https://dataut.vegvesen.no/api/3/action/package_show?id=artsmangfold"
BOMPENGER_URL = "https://dataut.vegvesen.no/api/3/action/package_show?id=bompenger"
NLOD_URL = "https://data.norge.no/nlod/no"
DATASET_ID = "vegvesen:artsmangfold"
ORG_ID = "e6d3dc7a-752e-418b-9afd-36533b370285"

LIST_BODY = {
    "success": True,
    "result": ["artsmangfold", "bompenger", ""],
}

ARTS_PACKAGE = {
    "name": "artsmangfold",
    "title": "Artsmangfold",
    "notes": "Truede arter, fremmede arter, artsrike vegkanter.",
    "license_url": NLOD_URL,
    "license_id": "NLOD",
    "organization": {
        "id": ORG_ID,
        "name": "statens-vegvesen",
        "title": "Statens vegvesen",
    },
    "resources": [
        {
            "id": "ea2cfc45-2948-44e5-8490-bc1eb615b805",
            "name": "Åpne data via NVDB api",
            "format": "XML",
            "url": "https://nvdbapiles-v3.atlas.vegvesen.no/",
            "nested": {"skip": True},
        },
        {
            "id": "ef148dff-0df8-447e-bbfd-42cbb15386b9",
            "name": "Åpne data via NVDB api",
            "format": "JSON",
            "url": "http://api.vegdata.no/",
        },
    ],
}

BOMPENGER_PACKAGE = {
    "name": "bompenger",
    "title": "Bompenger",
    "notes": "Data om bompengeinnkrevingen i Norge.",
    "license_url": "https://creativecommons.org/licenses/by/4.0/deed.no",
    "organization": {
        "id": ORG_ID,
        "title": "Statens vegvesen",
    },
    "resources": [
        {
            "id": "281479c5-ab7f-475e-9e05-114a2d8dcbf6",
            "name": "",
            "url": "https://bfinfor.atlas.vegvesen.no/hjem",
        }
    ],
}

ARTS_BODY = {"success": True, "result": ARTS_PACKAGE}
BOMPENGER_BODY = {"success": True, "result": BOMPENGER_PACKAGE}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == LIST_URL:
            return LIST_BODY
        if url == ARTS_URL:
            return ARTS_BODY
        if url == BOMPENGER_URL:
            return BOMPENGER_BODY
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == ARTS_URL:
            return JsonResponse(status=200, url=url, body=ARTS_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"vegvesen fetch must GET, not POST {url}")


def test_printed_refs_skip_blank_names() -> None:
    source = VegvesenSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["artsmangfold", "bompenger"]
    assert [ref.source_native_uri for ref in refs] == [ARTS_URL, BOMPENGER_URL]
    assert LIST_URL not in [ref.source_native_uri for ref in refs]


def test_package_show_url_joins_printed_origin_and_name() -> None:
    url = printed_package_show_url("artsmangfold", LIST_URL)
    assert url == ARTS_URL
    assert "package_list" not in url


def test_printed_license_and_publisher_copy_only_printed_fields() -> None:
    assert printed_license_url(ARTS_PACKAGE) == NLOD_URL
    assert printed_license_url({"license_id": "notspecified"}) is None
    assert printed_license_url({"license_url": "notspecified"}) is None
    publisher = printed_publisher(ARTS_PACKAGE)
    assert publisher == {"title": {"no": "Statens vegvesen"}, "id": ORG_ID}
    assert printed_publisher({"organization": None}) is None
    assert printed_publisher({"organization": {"name": "statens-vegvesen"}}) is None


def test_vegvesen_is_a_registered_source() -> None:
    assert "vegvesen" in SOURCE_IDS
    source = build_source("vegvesen")
    assert isinstance(source, VegvesenSource)
    assert source.source_id == "vegvesen"


def test_harvest_writes_printed_id_license_and_publisher(tmp_path: Path) -> None:
    source = VegvesenSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "vegvesen"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == ARTS_URL
    assert row["title"] == "Artsmangfold"
    assert row["publisher_name"] == "Statens vegvesen"
    assert row["license"] == NLOD_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("geonorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["vegvesen_package_name"] == "artsmangfold"
    assert payload["license"] == NLOD_URL
    assert payload["publisher"]["title"]["no"] == "Statens vegvesen"
    registry.close()


def test_fetch_gets_printed_artsmangfold_resources(tmp_path: Path) -> None:
    source = VegvesenSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == ARTS_URL
    assert result.table_id == "artsmangfold"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["Åpne data via NVDB api", "Åpne data via NVDB api"]
    assert all(row["measure"] == "name" for row in rows)
    formats = {json.loads(row["dimensions_json"])["format"] for row in rows}
    assert formats == {"XML", "JSON"}
    xml = next(row for row in rows if json.loads(row["dimensions_json"])["format"] == "XML")
    dims = json.loads(xml["dimensions_json"])
    assert dims["url"] == "https://nvdbapiles-v3.atlas.vegvesen.no/"
    assert "nested" not in dims
    assert all(row["publisher_name"] == "Statens vegvesen" for row in rows)
    assert all(row["license"] == NLOD_URL for row in rows)
    assert all(row["access_path"] == ARTS_URL for row in rows)
    registry.close()


def test_cells_copy_printed_resource_names() -> None:
    cells = cells_from_vegvesen(ARTS_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "Åpne data via NVDB api"
    assert dims["format"] == "XML"
    assert "nested" not in dims
    fallback = cells_from_vegvesen(BOMPENGER_BODY)
    assert fallback == [
        (
            "url",
            "https://bfinfor.atlas.vegvesen.no/hjem",
            {"id": "281479c5-ab7f-475e-9e05-114a2d8dcbf6", "name": ""},
        )
    ]
    unwrapped = cells_from_vegvesen(
        {"resources": [{"id": "x", "name": "Nedlastbare filer", "format": "CSV"}]}
    )
    assert unwrapped == [("name", "Nedlastbare filer", {"id": "x", "format": "CSV"})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_vegvesen([{"name": "Artsmangfold"}])
    with pytest.raises(ValueError, match="printed no resources"):
        cells_from_vegvesen({"success": True, "result": {"name": "datex", "resources": []}})


def test_is_vegvesen_url_accepts_only_package_show() -> None:
    assert is_vegvesen_url(ARTS_URL)
    assert is_vegvesen_url(BOMPENGER_URL)
    assert vegvesen_table_id(ARTS_URL) == "artsmangfold"
    assert not is_vegvesen_url(LIST_URL)
    assert not is_vegvesen_url("https://dataut.vegvesen.no/dataset/artsmangfold")
    assert not is_vegvesen_url("https://nvdbapiles-v3.atlas.vegvesen.no/")
    assert not is_vegvesen_url("https://data.norge.no/datasets/x")
    assert not is_vegvesen_url(None)


def test_limit_and_offset_slice_printed_names() -> None:
    source = VegvesenSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "artsmangfold"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["bompenger"]
