from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.search import search
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.sandnes import (
    DOCS_TITLE,
    DOCS_URL,
    PRINTED_QUERY,
    SandnesSource,
    cells_from_sandnes,
    is_sandnes_url,
    printed_api_url,
    printed_process_titles,
    sandnes_table_id,
)

API_URL = "https://medvirkning.sandnes.kommune.no/api"
DATASET_ID = "sandnes:api"
GRAPHQL_BODY = {
    "data": {
        "participatoryProcesses": [
            {
                "id": "8",
                "title": {
                    "translations": [
                        {"locale": "en", "text": None},
                        {"locale": "no", "text": "Ny plan for Sviland"},
                        {"locale": "pl", "text": None},
                    ]
                },
            },
            {
                "id": "9",
                "title": {
                    "translations": [
                        {"locale": "en", "text": None},
                        {"locale": "no", "text": "Bedre tverrfaglig innsats"},
                    ]
                },
            },
        ],
        "decidim": {"version": "0.28.2"},
    }
}


class CatalogHttp:
    def __init__(self) -> None:
        self.posts: list[tuple[str, object]] = []

    def post_json(self, url: str, body, *, headers=None):
        self.posts.append((url, body))
        assert url == API_URL
        assert body == {"query": PRINTED_QUERY}
        return GRAPHQL_BODY


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        raise AssertionError(f"sandnes fetch must POST, not GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        assert url == API_URL
        assert body == {"query": PRINTED_QUERY}
        return JsonResponse(status=200, url=url, body=GRAPHQL_BODY)


def test_printed_api_url_joins_docs_origin_to_printed_path() -> None:
    assert printed_api_url(DOCS_URL) == API_URL
    with pytest.raises(Exception, match="printed origin"):
        printed_api_url("/api/docs")


def test_sandnes_is_a_registered_source() -> None:
    assert "sandnes" in SOURCE_IDS
    assert "oslo" in SOURCE_IDS
    assert "trondheim" in SOURCE_IDS
    assert "opencom" in SOURCE_IDS
    assert "vegogc" in SOURCE_IDS
    source = build_source("sandnes")
    assert isinstance(source, SandnesSource)
    assert source.source_id == "sandnes"


def test_list_is_the_one_printed_api_route() -> None:
    source = SandnesSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["api"]
    assert [ref.source_native_uri for ref in refs] == [API_URL]
    assert source.list_dataset_refs(limit=0) == []
    assert source.list_dataset_refs(limit=1, offset=1) == []


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    http = CatalogHttp()
    source = SandnesSource(http=http)
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 1
    assert http.posts == [(API_URL, {"query": PRINTED_QUERY})]
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "sandnes"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == API_URL
    assert row["title"] == DOCS_TITLE
    assert "Sviland" in (row["description"] or "")
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert payload["sandnes_graphql"]["data"]["decidim"]["version"] == "0.28.2"
    registry.close()


def test_search_hits_sandnes_on_printed_process_title(tmp_path: Path) -> None:
    source = SandnesSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    hits = search(registry, "Sviland")
    assert any(hit.dataset_id == DATASET_ID and hit.title == DOCS_TITLE for hit in hits)
    registry.close()


def test_fetch_posts_printed_graphql_query(tmp_path: Path) -> None:
    source = SandnesSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == API_URL
    assert result.table_id == "api"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"Ny plan for Sviland", "Bedre tverrfaglig innsats"}
    assert all(row["measure"] == "text" for row in rows)
    assert json.loads(by_value["Ny plan for Sviland"]["dimensions_json"]) == {
        "id": "8",
        "locale": "no",
    }
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == API_URL for row in rows)
    registry.close()


def test_cells_copy_printed_non_null_title_texts() -> None:
    cells = cells_from_sandnes(GRAPHQL_BODY)
    assert cells == [
        ("text", "Ny plan for Sviland", {"id": "8", "locale": "no"}),
        ("text", "Bedre tverrfaglig innsats", {"id": "9", "locale": "no"}),
    ]
    assert printed_process_titles(GRAPHQL_BODY) == [
        "Ny plan for Sviland",
        "Bedre tverrfaglig innsats",
    ]
    with pytest.raises(ValueError, match="participatoryProcesses"):
        cells_from_sandnes({"data": {"decidim": {"version": "0.28.2"}}})
    with pytest.raises(ValueError, match="process titles"):
        cells_from_sandnes({"data": {"participatoryProcesses": []}})


def test_is_sandnes_url_accepts_only_printed_api_route() -> None:
    assert is_sandnes_url(API_URL)
    assert is_sandnes_url(API_URL + "/")
    assert sandnes_table_id(API_URL) == "api"
    assert not is_sandnes_url(DOCS_URL)
    assert not is_sandnes_url("https://medvirkning.sandnes.kommune.no/api/graphiql")
    assert not is_sandnes_url("https://www.sandnes.kommune.no/api")
    assert not is_sandnes_url("https://www.decidim.barcelona/api/")
    assert not is_sandnes_url("https://data.norge.no/datasets/x")
    assert not is_sandnes_url(None)
