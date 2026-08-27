from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.stedsnavn import (
    StedsnavnSource,
    cells_from_stedsnavn,
    is_stedsnavn_url,
    printed_endpoint_url,
    printed_license_url,
    stedsnavn_table_id,
)

OPENAPI_URL = "https://ws.geonorge.no/stedsnavn/v1/openapi.json"
NAVN_URL = "https://api.kartverket.no/stedsnavn/v1/navn"
TYPER_URL = "https://api.kartverket.no/stedsnavn/v1/navneobjekttyper"
PUNKT_URL = "https://api.kartverket.no/stedsnavn/v1/punkt"
SPRAK_URL = "https://api.kartverket.no/stedsnavn/v1/sprak"
STED_URL = "https://api.kartverket.no/stedsnavn/v1/sted"
DATASET_ID = "stedsnavn:navneobjekttyper"
SERVER = "https://api.kartverket.no/stedsnavn/v1"

OPENAPI = {
    "openapi": "3.0.3",
    "info": {
        "title": "Kartverkets åpne API for søk etter stedsnavn",
        "description": "API for søk etter stedsnavn.",
        "version": "1.1",
    },
    "servers": [{"url": SERVER}],
    "paths": {
        "/navn": {"get": {"summary": "Søk etter et spesifikt navn (skrivemåte/stedsnavn)."}},
        "/navneobjekttyper": {
            "get": {
                "summary": "Vis alle navneobjekttyper (f.eks by, elv, kirke) som et sted kan ha."
            }
        },
        "/navn/{stedsnummer}": {"get": {"summary": "Get one place name"}},
        "/punkt": {"get": {"summary": "Finn steder nær et gitt geografisk punkt."}},
        "/sprak": {"get": {"summary": "Vis alle språk som et navn kan ha."}},
        "/sted": {
            "get": {
                "summary": "Søk etter et sted. Et sted kan ha flere navn og hvert navn kan ha flere skrivemåter."
            }
        },
    },
}
TYPER_BODY = [
    {
        "navneobjekttype": "Militært bygg/anlegg",
        "navneobjekttypekode": "militærtByggAnlegg",
        "nested": {"skip": True},
    },
    {
        "navneobjekttype": "Fornøyelsespark",
        "navneobjekttypekode": "fornøyelsespark",
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
        if url == TYPER_URL:
            return JsonResponse(status=200, url=url, body=TYPER_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"stedsnavn fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_paths() -> None:
    source = StedsnavnSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "navn",
        "navneobjekttyper",
        "punkt",
        "sprak",
        "sted",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        NAVN_URL,
        TYPER_URL,
        PUNKT_URL,
        SPRAK_URL,
        STED_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_uses_printed_server() -> None:
    url = printed_endpoint_url(OPENAPI, "/navneobjekttyper", OPENAPI_URL)
    assert url == TYPER_URL
    assert "/openapi.json" not in url
    assert "ws.geonorge.no" not in url
    without_server = printed_endpoint_url({}, "/navneobjekttyper", OPENAPI_URL)
    assert without_server == "https://ws.geonorge.no/navneobjekttyper"


def test_stedsnavn_is_a_registered_source() -> None:
    assert "stedsnavn" in SOURCE_IDS
    source = build_source("stedsnavn")
    assert isinstance(source, StedsnavnSource)
    assert source.source_id == "stedsnavn"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = StedsnavnSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 5
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "stedsnavn"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == TYPER_URL
    assert row["title"] == "Vis alle navneobjekttyper (f.eks by, elv, kirke) som et sted kan ha."
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("geonorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["stedsnavn_openapi_path"] == "/navneobjekttyper"
    assert payload["license"] is None
    assert payload["publisher"] is None
    registry.close()


def test_fetch_gets_printed_navneobjekttyper(tmp_path: Path) -> None:
    source = StedsnavnSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == TYPER_URL
    assert result.table_id == "navneobjekttyper"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    assert [json.loads(row["value_json"]) for row in rows] == [
        "Militært bygg/anlegg",
        "Fornøyelsespark",
    ]
    assert all(row["measure"] == "navneobjekttype" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["navneobjekttypekode"] == "militærtByggAnlegg"
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == TYPER_URL for row in rows)
    registry.close()


def test_cells_copy_printed_name_and_skip_nested() -> None:
    cells = cells_from_stedsnavn(TYPER_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "navneobjekttype"
    assert value == "Militært bygg/anlegg"
    assert dims["navneobjekttypekode"] == "militærtByggAnlegg"
    assert "nested" not in dims
    sprak = cells_from_stedsnavn([{"språk": "Norsk", "språkkode": "nor"}])
    assert sprak == [("språk", "Norsk", {"språkkode": "nor"})]
    fallback = cells_from_stedsnavn([{"kode": "kirke"}])
    assert fallback == [("kode", "kirke", {})]
    with pytest.raises(ValueError, match="JSON array"):
        cells_from_stedsnavn({"navneobjekttype": "Kirke"})


def test_is_stedsnavn_url_accepts_only_kartverket_stedsnavn_host() -> None:
    assert is_stedsnavn_url(TYPER_URL)
    assert is_stedsnavn_url(SPRAK_URL)
    assert stedsnavn_table_id(TYPER_URL) == "navneobjekttyper"
    assert printed_license_url({}) is None
    assert printed_license_url({"license": {"url": "https://example.invalid/nlod"}}) == (
        "https://example.invalid/nlod"
    )
    assert not is_stedsnavn_url(OPENAPI_URL)
    assert not is_stedsnavn_url("https://ws.geonorge.no/stedsnavn/v1/navneobjekttyper")
    assert not is_stedsnavn_url("https://kartkatalog.geonorge.no/api/search")
    assert not is_stedsnavn_url("https://api.kartverket.no/kommuneinfo/v1/kommuner")
    assert not is_stedsnavn_url("https://data.norge.no/datasets/x")
    assert not is_stedsnavn_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = StedsnavnSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=2)] == [
        "navn",
        "navneobjekttyper",
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["navneobjekttyper"]
