from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.hoydedata import (
    HoydedataSource,
    cells_from_hoydedata,
    hoydedata_table_id,
    is_hoydedata_url,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://ws.geonorge.no/hoydedata/v1/openapi.json"
DATAKILDER_URL = "https://ws.geonorge.no/hoydedata/v1/datakilder"
PUNKT_URL = "https://ws.geonorge.no/hoydedata/v1/punkt"
TERRENGTYPER_URL = "https://ws.geonorge.no/hoydedata/v1/terrengtyper"
DATASET_ID = "hoydedata:datakilder"

OPENAPI = {
    "info": {
        "title": "Åpent API for høyde- og dybdedata fra Kartverket",
        "description": "API for oppslag av høyde- og dybdedata.",
        "version": "1.0",
    },
    "servers": [{"url": "/hoydedata/v1"}],
    "paths": {
        "/datakilder": {
            "get": {"summary": "Alle datakilder man kan hente høyder/dybder fra."}
        },
        "/datakilder/{datakilde}": {"get": {"summary": "Mer informasjon om spesifisert datakilde."}},
        "/datakilder/{datakilde}/punkt": {"get": {"summary": "Hent data fra spesifisert datakilde."}},
        "/punkt": {
            "get": {"summary": "Finner den beste tilgjengelige høyden eller dybden til ett eller flere punkter"}
        },
        "/terrengtyper": {
            "get": {"summary": "Alle mulige terrengtyper som et punkt kan treffe."}
        },
    },
}

DATAKILDER_BODY = [
    {
        "datakilde": "dtm1",
        "kortbeskrivelse": "Digital terrengmodell med 1 meters oppløsning.",
        "nested": {"skip": True},
    },
    {
        "datakilde": "dom1",
        "kortbeskrivelse": "Digital overflatemodell med 1 meters oppløsning.",
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
        if url == DATAKILDER_URL:
            return JsonResponse(status=200, url=url, body=DATAKILDER_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"hoydedata fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_paths() -> None:
    source = HoydedataSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["datakilder", "punkt", "terrengtyper"]
    assert [ref.source_native_uri for ref in refs] == [
        DATAKILDER_URL,
        PUNKT_URL,
        TERRENGTYPER_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]
    assert "https://ws.geonorge.no/datakilder" not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_joins_printed_relative_server() -> None:
    url = printed_endpoint_url(OPENAPI, "/datakilder", OPENAPI_URL)
    assert url == DATAKILDER_URL
    assert url != "https://ws.geonorge.no/datakilder"
    assert "openapi" not in url
    absolute = printed_endpoint_url(
        {"servers": [{"url": "https://ws.geonorge.no/hoydedata/v1"}]},
        "/datakilder",
        OPENAPI_URL,
    )
    assert absolute == DATAKILDER_URL
    assert printed_operation_id("/datakilder") == "datakilder"
    assert printed_operation_id("/terrengtyper") == "terrengtyper"


def test_hoydedata_is_a_registered_source() -> None:
    assert "hoydedata" in SOURCE_IDS
    source = build_source("hoydedata")
    assert isinstance(source, HoydedataSource)
    assert source.source_id == "hoydedata"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = HoydedataSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "hoydedata"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == DATAKILDER_URL
    assert row["title"] == "Alle datakilder man kan hente høyder/dybder fra."
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("geonorge:")
    assert not str(row["id"]).startswith("kommuneinfo:")
    assert not str(row["id"]).startswith("nin:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["hoydedata_openapi_path"] == "/datakilder"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_datakilde_names(tmp_path: Path) -> None:
    source = HoydedataSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == DATAKILDER_URL
    assert result.table_id == "datakilder"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"dtm1", "dom1"}
    assert all(row["measure"] == "datakilde" for row in rows)
    dims = json.loads(by_value["dtm1"]["dimensions_json"])
    assert dims["kortbeskrivelse"] == "Digital terrengmodell med 1 meters oppløsning."
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == DATAKILDER_URL for row in rows)
    registry.close()


def test_cells_copy_printed_datakilde_and_skip_nested() -> None:
    cells = cells_from_hoydedata(DATAKILDER_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "datakilde"
    assert value == "dtm1"
    assert dims["kortbeskrivelse"] == "Digital terrengmodell med 1 meters oppløsning."
    assert "nested" not in dims
    terreng = cells_from_hoydedata([{"terreng": "ÅpentOmråde"}])
    assert terreng == [("terreng", "ÅpentOmråde", {})]
    strings = cells_from_hoydedata(["dtm1", "dom1"])
    assert strings == [("value", "dtm1", {}), ("value", "dom1", {})]
    fallback = cells_from_hoydedata([{"kortbeskrivelse": "Digital terrengmodell med 1 meters oppløsning."}])
    assert fallback == [("kortbeskrivelse", "Digital terrengmodell med 1 meters oppløsning.", {})]
    with pytest.raises(ValueError, match="JSON array"):
        cells_from_hoydedata({"datakilde": "dtm1"})
    with pytest.raises(ValueError, match="printed no collection"):
        cells_from_hoydedata([])


def test_is_hoydedata_url_accepts_only_hoydedata_collection() -> None:
    assert is_hoydedata_url(DATAKILDER_URL)
    assert is_hoydedata_url(TERRENGTYPER_URL)
    assert is_hoydedata_url(PUNKT_URL)
    assert hoydedata_table_id(DATAKILDER_URL) == "datakilder"
    assert printed_license_url({}) is None
    assert printed_license_url({"license": {"url": "https://example.invalid/nlod"}}) == (
        "https://example.invalid/nlod"
    )
    assert not is_hoydedata_url("https://ws.geonorge.no/datakilder")
    assert not is_hoydedata_url("https://ws.geonorge.no/adresser/v1/sok")
    assert not is_hoydedata_url("https://ws.geonorge.no/stedsnavn/v1/navneobjekttyper")
    assert not is_hoydedata_url("https://api.kartverket.no/kommuneinfo/v1/fylker")
    assert not is_hoydedata_url("https://kartkatalog.geonorge.no/api/search")
    assert not is_hoydedata_url("https://geo.ngu.no/api/features")
    assert not is_hoydedata_url("https://data.norge.no/datasets/x")
    assert not is_hoydedata_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = HoydedataSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "datakilder"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=2)
    assert [ref.source_native_id for ref in nxt] == ["terrengtyper"]
