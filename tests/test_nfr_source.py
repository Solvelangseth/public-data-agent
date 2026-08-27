from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.nfr import (
    NfrSource,
    cells_from_nfr,
    is_nfr_url,
    nfr_table_id,
    printed_endpoint_url,
    printed_license_url,
)

OPENAPI_URL = "https://data-nfr.udir.no/swagger/v4/swagger.json"
ENHETER_URL = "https://data-nfr.udir.no/v4/enheter"
KATEGORIER_URL = "https://data-nfr.udir.no/v4/skolefritidsordningskategorier"
NAERING_URL = "https://data-nfr.udir.no/v4/naeringskoder"
NLOD_URL = "https://data.norge.no/nlod/no"
DATASET_ID = "nfr:skolefritidsordningskategorier"

OPENAPI = {
    "info": {
        "title": "Nasjonalt register for skolefritidsordningen API",
        "description": "Data fra Nasjonalt register for skolefritidsordningen (NFR).",
        "license": {"name": "Lisens: Norsk lisens for offentlige data (NLOD)", "url": NLOD_URL},
        "version": "v4",
    },
    "paths": {
        "/v4/enheter": {"get": {"summary": "Alle enheter"}},
        "/v4/enhet/{organisasjonsnummer}": {"get": {"summary": "En enhet"}},
        "/v4/enheter/sok": {"post": {"summary": "Søk"}},
        "/v4/naeringskoder": {"get": {"summary": "Skolefritidsordning næringskoder"}},
        "/v4/skolefritidsordningskategorier": {
            "get": {"summary": "Alle skolefritidsordningskategorier"}
        },
    },
}
KATEGORIER_BODY = {
    "SkolefritidsordningskategoriListe": [
        {
            "Id": "0",
            "Navn": "Ingen verdi",
            "nested": {"skip": "dict"},
        },
        {
            "Id": "33",
            "Navn": "Offentlig skolefritidsordning",
        },
    ]
}


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
        if url == KATEGORIER_URL:
            return JsonResponse(status=200, url=url, body=KATEGORIER_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nfr fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_post_paths() -> None:
    source = NfrSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "enheter",
        "naeringskoder",
        "skolefritidsordningskategorier",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        ENHETER_URL,
        NAERING_URL,
        KATEGORIER_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_uses_openapi_origin_when_servers_absent() -> None:
    url = printed_endpoint_url(OPENAPI, "/v4/skolefritidsordningskategorier", OPENAPI_URL)
    assert url == KATEGORIER_URL
    assert "/swagger/" not in url
    with_server = printed_endpoint_url(
        {"servers": [{"url": "https://data-nfr.udir.no/"}]},
        "/v4/skolefritidsordningskategorier",
        OPENAPI_URL,
    )
    assert with_server == KATEGORIER_URL


def test_nfr_is_a_registered_source() -> None:
    assert "nfr" in SOURCE_IDS
    source = build_source("nfr")
    assert isinstance(source, NfrSource)
    assert source.source_id == "nfr"


def test_harvest_writes_printed_id_license_and_null_publisher(tmp_path: Path) -> None:
    source = NfrSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nfr"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == KATEGORIER_URL
    assert row["title"] == "Alle skolefritidsordningskategorier"
    assert row["publisher_name"] is None
    assert row["license"] == NLOD_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("udir:")
    assert not str(row["id"]).startswith("nbr:")
    assert not str(row["id"]).startswith("nor:")
    assert not str(row["id"]).startswith("npr:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["nfr_openapi_path"] == "/v4/skolefritidsordningskategorier"
    assert payload["license"] == NLOD_URL
    assert payload["publisher"] is None
    assert registry.enrichment_count() == 0
    registry.close()


def test_fetch_gets_printed_kategorier(tmp_path: Path) -> None:
    source = NfrSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == KATEGORIER_URL
    assert result.table_id == "skolefritidsordningskategorier"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["Ingen verdi", "Offentlig skolefritidsordning"]
    assert all(row["measure"] == "Navn" for row in rows)
    by_name = {json.loads(row["value_json"]): row for row in rows}
    dims = json.loads(by_name["Ingen verdi"]["dimensions_json"])
    assert dims["Id"] == "0"
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == NLOD_URL for row in rows)
    assert all(row["access_path"] == KATEGORIER_URL for row in rows)
    registry.close()


def test_cells_copy_printed_liste_navn() -> None:
    cells = cells_from_nfr(KATEGORIER_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "Navn"
    assert value == "Ingen verdi"
    assert dims["Id"] == "0"
    assert "nested" not in dims
    fallback = cells_from_nfr({"KodeListe": [{"Kode": "88.910", "Versjon": "2025"}]})
    assert fallback == [("Kode", "88.910", {"Versjon": "2025"})]
    unwrapped = cells_from_nfr([{"Id": "33", "Navn": "Offentlig skolefritidsordning"}])
    assert unwrapped == [("Navn", "Offentlig skolefritidsordning", {"Id": "33"})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_nfr("kategorier")
    with pytest.raises(ValueError, match="printed no collection list"):
        cells_from_nfr({"Sidenummer": 1, "AntallPerSide": 1000})
    with pytest.raises(ValueError, match="printed no collection members"):
        cells_from_nfr({"SkolefritidsordningskategoriListe": []})


def test_is_nfr_url_accepts_only_nfr_host() -> None:
    assert is_nfr_url(KATEGORIER_URL)
    assert is_nfr_url(OPENAPI_URL)
    assert nfr_table_id(KATEGORIER_URL) == "skolefritidsordningskategorier"
    assert printed_license_url(OPENAPI["info"]) == NLOD_URL
    assert printed_license_url({}) is None
    assert not is_nfr_url("https://data-nsr.udir.no/skoletyper")
    assert not is_nfr_url("https://data-nbr.udir.no/v3/barnehagekategorier")
    assert not is_nfr_url("https://data-nor.udir.no/v4/maalformer")
    assert not is_nfr_url("https://data-npr.udir.no/v4/naeringskoder")
    assert not is_nfr_url("https://data.norge.no/datasets/x")
    assert not is_nfr_url("https://www.udir.no/skolefritidsordningskategorier")
    assert not is_nfr_url("https://nfr.udir.no/v4/skolefritidsordningskategorier")
    assert not is_nfr_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = NfrSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=2)] == [
        "enheter",
        "naeringskoder",
    ]
    nxt = source.list_dataset_refs(limit=1, offset=2)
    assert [ref.source_native_id for ref in nxt] == ["skolefritidsordningskategorier"]
