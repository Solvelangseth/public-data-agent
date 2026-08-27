from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.kommuneinfo import (
    KommuneinfoSource,
    cells_from_kommuneinfo,
    is_kommuneinfo_url,
    kommuneinfo_table_id,
    printed_endpoint_url,
    printed_license_url,
)

OPENAPI_URL = "https://api.kartverket.no/kommuneinfo/v1/openapi.json"
FYLKER_URL = "https://api.kartverket.no/kommuneinfo/v1/fylker"
FYLKERKOMMUNER_URL = "https://api.kartverket.no/kommuneinfo/v1/fylkerkommuner"
KOMMUNER_URL = "https://api.kartverket.no/kommuneinfo/v1/kommuner"
KART_URL = "https://api.kartverket.no/kommuneinfo/v1/kommuner/illustrasjonskart"
PUNKT_URL = "https://api.kartverket.no/kommuneinfo/v1/punkt"
SOK_URL = "https://api.kartverket.no/kommuneinfo/v1/sok"
DATASET_ID = "kommuneinfo:fylker"
SERVER = "https://api.kartverket.no/kommuneinfo/v1"

OPENAPI = {
    "openapi": "3.0.1",
    "info": {
        "title": "Åpent API fra Kartverket for administrative enheter",
        "description": "Data om fylker og kommuner. Ingen innlogging.",
        "version": "1.2",
    },
    "servers": [{"url": SERVER}],
    "paths": {
        "/fylker": {"get": {"summary": "Fylker i Norge."}},
        "/fylker/{fylkesnummer}": {"get": {"summary": "Vis mer informasjon om et fylke"}},
        "/fylkerkommuner": {"get": {"summary": "Full informasjon om alle fylker og alle kommuner."}},
        "/kommuner": {"get": {"summary": "Kommuner i Norge."}},
        "/kommuner/illustrasjonskart": {
            "get": {"summary": "Illustrasjonskart over kommuner i Norge."}
        },
        "/kommuner/{kommunenummer}": {"get": {"summary": "Full informasjon om spesifikk kommune"}},
        "/punkt": {"get": {"summary": "Finn kommune og fylke for et gitt geografisk punkt"}},
        "/sok": {"get": {"summary": "Søk etter kommunenavn."}},
    },
}
FYLKER_BODY = [
    {"fylkesnavn": "Troms", "fylkesnummer": "55", "nested": {"skip": True}},
    {"fylkesnavn": "Finnmark", "fylkesnummer": "56"},
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
        if url == FYLKER_URL:
            return JsonResponse(status=200, url=url, body=FYLKER_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"kommuneinfo fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_paths() -> None:
    source = KommuneinfoSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "fylker",
        "fylkerkommuner",
        "kommuner",
        "illustrasjonskart",
        "punkt",
        "sok",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        FYLKER_URL,
        FYLKERKOMMUNER_URL,
        KOMMUNER_URL,
        KART_URL,
        PUNKT_URL,
        SOK_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_uses_printed_server() -> None:
    url = printed_endpoint_url(OPENAPI, "/fylker", OPENAPI_URL)
    assert url == FYLKER_URL
    assert "/openapi.json" not in url
    without_server = printed_endpoint_url({}, "/fylker", OPENAPI_URL)
    assert without_server == "https://api.kartverket.no/fylker"


def test_kommuneinfo_is_a_registered_source() -> None:
    assert "kommuneinfo" in SOURCE_IDS
    source = build_source("kommuneinfo")
    assert isinstance(source, KommuneinfoSource)
    assert source.source_id == "kommuneinfo"


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = KommuneinfoSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 6
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "kommuneinfo"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == FYLKER_URL
    assert row["title"] == "Fylker i Norge."
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("geonorge:")
    assert not str(row["id"]).startswith("stedsnavn:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["kommuneinfo_openapi_path"] == "/fylker"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_fylker(tmp_path: Path) -> None:
    source = KommuneinfoSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == FYLKER_URL
    assert result.table_id == "fylker"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    assert [json.loads(row["value_json"]) for row in rows] == ["Troms", "Finnmark"]
    assert all(row["measure"] == "fylkesnavn" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["fylkesnummer"] == "55"
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == FYLKER_URL for row in rows)
    registry.close()


def test_cells_copy_printed_name_and_skip_nested() -> None:
    cells = cells_from_kommuneinfo(FYLKER_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "fylkesnavn"
    assert value == "Troms"
    assert dims["fylkesnummer"] == "55"
    assert "nested" not in dims
    kommuner = cells_from_kommuneinfo(
        [{"kommunenavnNorsk": "Våler", "kommunenavn": "Våler", "kommunenummer": "3419"}]
    )
    assert kommuner == [
        ("kommunenavnNorsk", "Våler", {"kommunenavn": "Våler", "kommunenummer": "3419"})
    ]
    fallback = cells_from_kommuneinfo([{"fylkesnummer": "55"}])
    assert fallback == [("fylkesnummer", "55", {})]
    with pytest.raises(ValueError, match="JSON array"):
        cells_from_kommuneinfo({"fylkesnavn": "Troms"})


def test_is_kommuneinfo_url_accepts_only_kartverket_kommuneinfo_host() -> None:
    assert is_kommuneinfo_url(FYLKER_URL)
    assert is_kommuneinfo_url(KOMMUNER_URL)
    assert kommuneinfo_table_id(FYLKER_URL) == "fylker"
    assert kommuneinfo_table_id(KART_URL) == "illustrasjonskart"
    assert printed_license_url({}) is None
    assert printed_license_url({"license": {"url": "https://example.invalid/nlod"}}) == (
        "https://example.invalid/nlod"
    )
    assert not is_kommuneinfo_url("https://ws.geonorge.no/kommuneinfo/v1/fylker")
    assert not is_kommuneinfo_url("https://ws.geonorge.no/kommuneinfo/v1/openapi.json")
    assert not is_kommuneinfo_url("https://api.kartverket.no/stedsnavn/v1/navneobjekttyper")
    assert not is_kommuneinfo_url("https://kartkatalog.geonorge.no/api/search")
    assert not is_kommuneinfo_url("https://data.norge.no/datasets/x")
    assert not is_kommuneinfo_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = KommuneinfoSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=2)] == [
        "fylker",
        "fylkerkommuner",
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["fylkerkommuner"]
