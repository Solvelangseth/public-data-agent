from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.transformering import (
    TransformeringSource,
    cells_from_transformering,
    is_transformering_url,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
    transformering_table_id,
)

OPENAPI_URL = "https://ws.geonorge.no/transformering/v1/openapi.json"
PROJEKSJONER_URL = "https://ws.geonorge.no/transformering/v1/projeksjoner"
TRANSFORMER_URL = "https://ws.geonorge.no/transformering/v1/transformer"
DATASET_ID = "transformering:projeksjoner"

OPENAPI = {
    "info": {
        "title": "Transformering",
        "description": "Transformer koordinater mellom forskjellige koordinatsystemer.",
        "version": "1.10.0",
    },
    "servers": [{"url": "/transformering/v1"}],
    "paths": {
        "/transformer": {
            "get": {
                "summary": "Transformer Ett Koordinat",
                "parameters": [
                    {"name": "x", "required": True, "in": "query"},
                    {"name": "y", "required": True, "in": "query"},
                    {"name": "fra", "required": True, "in": "query"},
                    {"name": "til", "required": True, "in": "query"},
                ],
            },
            "post": {
                "summary": "Transformer Mange Koordinater",
                "parameters": [
                    {"name": "fra", "required": True, "in": "query"},
                    {"name": "til", "required": True, "in": "query"},
                ],
            },
        },
        "/projeksjoner": {
            "get": {
                "summary": "Koordinatsystemer",
                "parameters": [
                    {"name": "kategori", "required": False, "in": "query"},
                    {"name": "system", "required": False, "in": "query"},
                ],
            }
        },
        "/projeksjoner/{epsg}": {"get": {"summary": "Ett koordinatsystem"}},
    },
}

PROJEKSJONER_BODY = [
    {
        "degrees": True,
        "epsg": 4258,
        "name": "ETRS89 Geografisk 2D",
        "nested": {"skip": True},
    },
    {
        "degrees": False,
        "epsg": 25833,
        "name": "ETRS89 / UTM sone 33",
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
        if url == PROJEKSJONER_URL:
            return JsonResponse(status=200, url=url, body=PROJEKSJONER_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"transformering fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_required_param_paths() -> None:
    source = TransformeringSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["projeksjoner"]
    assert [ref.source_native_uri for ref in refs] == [PROJEKSJONER_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]
    assert TRANSFORMER_URL not in [ref.source_native_uri for ref in refs]
    assert "https://ws.geonorge.no/projeksjoner" not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_joins_printed_relative_server() -> None:
    url = printed_endpoint_url(OPENAPI, "/projeksjoner", OPENAPI_URL)
    assert url == PROJEKSJONER_URL
    assert url != "https://ws.geonorge.no/projeksjoner"
    assert "openapi" not in url
    absolute = printed_endpoint_url(
        {"servers": [{"url": "https://ws.geonorge.no/transformering/v1"}]},
        "/projeksjoner",
        OPENAPI_URL,
    )
    assert absolute == PROJEKSJONER_URL
    assert printed_operation_id("/projeksjoner") == "projeksjoner"


def test_transformering_is_a_registered_source() -> None:
    assert "transformering" in SOURCE_IDS
    assert "hoydedata" in SOURCE_IDS
    assert "subjectiveforecast" in SOURCE_IDS
    assert "polarsatellite" in SOURCE_IDS
    source = build_source("transformering")
    assert isinstance(source, TransformeringSource)
    assert source.source_id == "transformering"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = TransformeringSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "transformering"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == PROJEKSJONER_URL
    assert row["title"] == "Koordinatsystemer"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("hoydedata:")
    assert not str(row["id"]).startswith("kommuneinfo:")
    assert not str(row["id"]).startswith("stedsnavn:")
    assert not str(row["id"]).startswith("subjectiveforecast:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["transformering_openapi_path"] == "/projeksjoner"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_projection_names(tmp_path: Path) -> None:
    source = TransformeringSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == PROJEKSJONER_URL
    assert result.table_id == "projeksjoner"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"ETRS89 Geografisk 2D", "ETRS89 / UTM sone 33"}
    assert all(row["measure"] == "name" for row in rows)
    dims = json.loads(by_value["ETRS89 Geografisk 2D"]["dimensions_json"])
    assert dims["epsg"] == "4258"
    assert dims["degrees"] == "True"
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == PROJEKSJONER_URL for row in rows)
    registry.close()


def test_cells_copy_printed_name_and_skip_nested() -> None:
    cells = cells_from_transformering(PROJEKSJONER_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "ETRS89 Geografisk 2D"
    assert dims["epsg"] == "4258"
    assert "nested" not in dims
    strings = cells_from_transformering(["ETRS89", "WGS84"])
    assert strings == [("value", "ETRS89", {}), ("value", "WGS84", {})]
    fallback = cells_from_transformering([{"epsg": 4258}])
    assert fallback == [("epsg", 4258, {})]
    with pytest.raises(ValueError, match="JSON array"):
        cells_from_transformering({"name": "ETRS89 Geografisk 2D"})
    with pytest.raises(ValueError, match="printed no collection"):
        cells_from_transformering([])


def test_is_transformering_url_accepts_only_transformering_collection() -> None:
    assert is_transformering_url(PROJEKSJONER_URL)
    assert is_transformering_url(TRANSFORMER_URL)
    assert is_transformering_url(OPENAPI_URL)
    assert transformering_table_id(PROJEKSJONER_URL) == "projeksjoner"
    assert printed_license_url({}) is None
    assert printed_license_url({"license": {"url": "https://example.invalid/nlod"}}) == (
        "https://example.invalid/nlod"
    )
    assert not is_transformering_url("https://ws.geonorge.no/hoydedata/v1/datakilder")
    assert not is_transformering_url("https://ws.geonorge.no/adresser/v1/sok")
    assert not is_transformering_url("https://ws.geonorge.no/stedsnavn/v1/navneobjekttyper")
    assert not is_transformering_url("https://api.kartverket.no/kommuneinfo/v1/fylker")
    assert not is_transformering_url("https://api.met.no/weatherapi/subjectiveforecast/1.0/features")
    assert not is_transformering_url("https://data.norge.no/datasets/x")
    assert not is_transformering_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = TransformeringSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "projeksjoner"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == []
