from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.npr import (
    NprSource,
    cells_from_npr,
    is_npr_url,
    npr_table_id,
    printed_endpoint_url,
    printed_license_url,
)

OPENAPI_URL = "https://data-npr.udir.no/swagger/v4/swagger.json"
ENHETER_URL = "https://data-npr.udir.no/v4/enheter"
NAERINGSKODER_URL = "https://data-npr.udir.no/v4/naeringskoder"
MAALFORMER_URL = "https://data-npr.udir.no/v4/maalformer"
NLOD_URL = "https://data.norge.no/nlod/no"
DATASET_ID = "npr:naeringskoder"

OPENAPI = {
    "info": {
        "title": "Nasjonalt register for PP-tjenester API",
        "description": "Data fra Nasjonalt register for PP-tjenester (NPR).",
        "license": {"name": "Lisens: Norsk lisens for offentlige data (NLOD)", "url": NLOD_URL},
        "version": "v4",
    },
    "paths": {
        "/v4/enheter": {"get": {"summary": "Alle enheter"}},
        "/v4/enhet/{organisasjonsnummer}": {"get": {"summary": "En enhet"}},
        "/v4/enheter/sok": {"post": {"summary": "Søk"}},
        "/v4/naeringskoder": {"get": {"summary": "PP-tjeneste næringskoder"}},
        "/v4/maalformer": {"get": {"summary": "Alle målformer"}},
    },
}
NAERINGSKODER_BODY = {
    "NaeringskodeListe": [
        {
            "Kode": "85.691",
            "Navn": "Pedagogisk-psykologisk rådgivningstjeneste",
            "Versjon": "2025",
            "nested": {"skip": "dict"},
        }
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
        if url == NAERINGSKODER_URL:
            return JsonResponse(status=200, url=url, body=NAERINGSKODER_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"npr fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_post_paths() -> None:
    source = NprSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "enheter",
        "naeringskoder",
        "maalformer",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        ENHETER_URL,
        NAERINGSKODER_URL,
        MAALFORMER_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_uses_openapi_origin_when_servers_absent() -> None:
    url = printed_endpoint_url(OPENAPI, "/v4/naeringskoder", OPENAPI_URL)
    assert url == NAERINGSKODER_URL
    assert "/swagger/" not in url
    with_server = printed_endpoint_url(
        {"servers": [{"url": "https://data-npr.udir.no/"}]},
        "/v4/naeringskoder",
        OPENAPI_URL,
    )
    assert with_server == NAERINGSKODER_URL


def test_npr_is_a_registered_source() -> None:
    assert "npr" in SOURCE_IDS
    source = build_source("npr")
    assert isinstance(source, NprSource)
    assert source.source_id == "npr"


def test_harvest_writes_printed_id_license_and_null_publisher(tmp_path: Path) -> None:
    source = NprSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "npr"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == NAERINGSKODER_URL
    assert row["title"] == "PP-tjeneste næringskoder"
    assert row["publisher_name"] is None
    assert row["license"] == NLOD_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("udir:")
    assert not str(row["id"]).startswith("nbr:")
    assert not str(row["id"]).startswith("nor:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["npr_openapi_path"] == "/v4/naeringskoder"
    assert payload["license"] == NLOD_URL
    assert payload["publisher"] is None
    assert registry.enrichment_count() == 0
    registry.close()


def test_fetch_gets_printed_naeringskoder(tmp_path: Path) -> None:
    source = NprSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == NAERINGSKODER_URL
    assert result.table_id == "naeringskoder"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert values == ["Pedagogisk-psykologisk rådgivningstjeneste"]
    assert all(row["measure"] == "Navn" for row in rows)
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["Kode"] == "85.691"
    assert dims["Versjon"] == "2025"
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == NLOD_URL for row in rows)
    assert all(row["access_path"] == NAERINGSKODER_URL for row in rows)
    registry.close()


def test_cells_copy_printed_liste_navn() -> None:
    cells = cells_from_npr(NAERINGSKODER_BODY)
    assert len(cells) == 1
    measure, value, dims = cells[0]
    assert measure == "Navn"
    assert value == "Pedagogisk-psykologisk rådgivningstjeneste"
    assert dims["Kode"] == "85.691"
    assert "nested" not in dims
    fallback = cells_from_npr({"KodeListe": [{"Kode": "AS", "Versjon": "2025"}]})
    assert fallback == [("Kode", "AS", {"Versjon": "2025"})]
    unwrapped = cells_from_npr([{"Id": "21", "Navn": "Godkjent i fylker struktur"}])
    assert unwrapped == [("Navn", "Godkjent i fylker struktur", {"Id": "21"})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_npr("naeringskoder")
    with pytest.raises(ValueError, match="printed no collection list"):
        cells_from_npr({"Sidenummer": 1, "AntallPerSide": 1000})
    with pytest.raises(ValueError, match="printed no collection members"):
        cells_from_npr({"NaeringskodeListe": []})


def test_is_npr_url_accepts_only_npr_host() -> None:
    assert is_npr_url(NAERINGSKODER_URL)
    assert is_npr_url(OPENAPI_URL)
    assert npr_table_id(NAERINGSKODER_URL) == "naeringskoder"
    assert printed_license_url(OPENAPI["info"]) == NLOD_URL
    assert printed_license_url({}) is None
    assert not is_npr_url("https://data-nsr.udir.no/skoletyper")
    assert not is_npr_url("https://data-nbr.udir.no/v3/barnehagekategorier")
    assert not is_npr_url("https://data-nor.udir.no/v4/maalformer")
    assert not is_npr_url("https://data.norge.no/datasets/x")
    assert not is_npr_url("https://www.udir.no/naeringskoder")
    assert not is_npr_url("https://npr.udir.no/v4/naeringskoder")
    assert not is_npr_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = NprSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=2)] == [
        "enheter",
        "naeringskoder",
    ]
    nxt = source.list_dataset_refs(limit=1, offset=2)
    assert [ref.source_native_id for ref in nxt] == ["maalformer"]
