from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.ngu import (
    NguSource,
    cells_from_ngu,
    is_ngu_url,
    ngu_table_id,
    printed_landing_page,
)

LIST_URL = "https://geo.ngu.no/api/features"
ANKRING_URL = "https://geo.ngu.no/api/features/ankringsforhold"
BUNN_URL = "https://geo.ngu.no/api/features/bunnfellingsomrader"
DATASET_ID = "ngu:ankringsforhold"

LIST_BODY = {
    "title": "Norges geologiske undersøkelse - OGC API Features",
    "catalogUri": LIST_URL,
    "apis": [
        {
            "title": "Marin: Ankringsforhold",
            "description": "Ankringsforhold på havbunnen.",
            "id": "ankringsforhold",
            "landingPageUri": ANKRING_URL,
            "isDataset": True,
        },
        {
            "title": "Marin: Bunnfellingsområder",
            "id": "bunnfellingsomrader",
            "landingPageUri": BUNN_URL,
            "isDataset": True,
        },
        {
            "title": "missing-uri",
            "id": "missing-uri",
        },
        {
            "landingPageUri": "https://geo.ngu.no/api/features/blank",
            "id": "",
        },
    ],
}

ANKRING_BODY = {
    "title": "Ankringsforhold",
    "description": "Datasettet viser ankringsforhold.",
    "attribution": "&copy; NGU",
    "links": [
        {
            "rel": "data",
            "title": "Access the data (ankringOmr)",
            "href": "https://geo.ngu.no/api/features/ankringsforhold/collections",
            "nested": {"skip": True},
        },
        {
            "rel": "self",
            "type": "application/json",
            "title": "This document",
            "href": "https://geo.ngu.no/api/features/ankringsforhold?f=json",
        },
        {
            "rel": "conformance",
            "href": "https://geo.ngu.no/api/features/ankringsforhold/conformance",
        },
    ],
}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == LIST_URL:
            return LIST_BODY
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == ANKRING_URL:
            return JsonResponse(status=200, url=url, body=ANKRING_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"ngu fetch must GET, not POST {url}")


def test_printed_refs_skip_blank_ids() -> None:
    source = NguSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "ankringsforhold",
        "bunnfellingsomrader",
    ]
    assert [ref.source_native_uri for ref in refs] == [ANKRING_URL, BUNN_URL]
    assert LIST_URL not in [ref.source_native_uri for ref in refs]


def test_landing_page_copies_printed_uri() -> None:
    url = printed_landing_page(LIST_BODY["apis"][0])
    assert url == ANKRING_URL
    assert url.endswith("ankringsforhold")


def test_ngu_is_a_registered_source() -> None:
    assert "ngu" in SOURCE_IDS
    source = build_source("ngu")
    assert isinstance(source, NguSource)
    assert source.source_id == "ngu"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = NguSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "ngu"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == ANKRING_URL
    assert row["title"] == "Marin: Ankringsforhold"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("geonorge:")
    assert not str(row["id"]).startswith("hi:")
    assert not str(row["id"]).startswith("kommuneinfo:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["ngu_api"]["id"] == "ankringsforhold"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_landing_page_links(tmp_path: Path) -> None:
    source = NguSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == ANKRING_URL
    assert result.table_id == "ankringsforhold"
    assert result.http_status == 200
    assert result.counts.listed == 3
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {
        "Access the data (ankringOmr)",
        "This document",
        "conformance",
    }
    assert by_value["Access the data (ankringOmr)"]["measure"] == "title"
    assert by_value["This document"]["measure"] == "title"
    assert by_value["conformance"]["measure"] == "rel"
    dims = json.loads(by_value["Access the data (ankringOmr)"]["dimensions_json"])
    assert dims["rel"] == "data"
    assert dims["href"] == "https://geo.ngu.no/api/features/ankringsforhold/collections"
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == ANKRING_URL for row in rows)
    registry.close()


def test_cells_copy_printed_link_titles() -> None:
    cells = cells_from_ngu(ANKRING_BODY)
    assert len(cells) == 3
    measure, value, dims = cells[0]
    assert measure == "title"
    assert value == "Access the data (ankringOmr)"
    assert dims["rel"] == "data"
    assert "nested" not in dims
    assert cells[2] == (
        "rel",
        "conformance",
        {"href": "https://geo.ngu.no/api/features/ankringsforhold/conformance"},
    )
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_ngu([{"title": "Ankringsforhold"}])
    with pytest.raises(ValueError, match="links array"):
        cells_from_ngu({"title": "Ankringsforhold"})
    with pytest.raises(ValueError, match="printed no links"):
        cells_from_ngu({"links": []})


def test_is_ngu_url_accepts_only_dataset_landing_page() -> None:
    assert is_ngu_url(ANKRING_URL)
    assert is_ngu_url(BUNN_URL)
    assert ngu_table_id(ANKRING_URL) == "ankringsforhold"
    assert printed_landing_page(LIST_BODY["apis"][0]) == ANKRING_URL
    assert not is_ngu_url(LIST_URL)
    assert not is_ngu_url("https://geo.ngu.no/api/features/")
    assert not is_ngu_url("https://kart.hi.no/data/ogc/features/v1/collections")
    assert not is_ngu_url("https://ws.geonorge.no/kommuneinfo/v1/openapi.json")
    assert not is_ngu_url("https://api.kartverket.no/kommuneinfo/v1/fylker")
    assert not is_ngu_url("https://data.norge.no/datasets/x")
    assert not is_ngu_url(None)


def test_limit_and_offset_slice_printed_apis() -> None:
    source = NguSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "ankringsforhold"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["bunnfellingsomrader"]
