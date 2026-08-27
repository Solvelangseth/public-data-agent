from __future__ import annotations

import json
from pathlib import Path

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.nve import (
    NveMagasinSource,
    cells_from_nve,
    is_nve_magasin_url,
    printed_endpoint_url,
    printed_operation_id,
    printed_publisher,
    requestable_url,
)

OPENAPI_URL = "https://biapi.nve.no/magasinstatistikk/swagger/v1/swagger.json"
SISTE_UKE = (
    "https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk/HentOffentligDataSisteUke"
)
OPENAPI = {
    "info": {
        "title": "Magasinstatistikk",
        "description": "Norges vassdrags- og energidirektorat (NVE) magasinstatistikk",
        "version": "v1.0.0",
    },
    "servers": [{"url": "/magasinstatistikk"}],
    "paths": {
        "/api/Magasinstatistikk/HentOffentligData": {
            "get": {"summary": "Henter magasinstatistikk"}
        },
        "/api/Magasinstatistikk/HentOffentligDataSisteUke": {
            "get": {"summary": "Henter magasinstatistikk siste uke"}
        },
        "/api/Magasinstatistikk/HentOmråder": {
            "get": {"summary": "Henter områder for magasinstatistikk"}
        },
    },
}
SISTE_UKE_ROWS = [
    {
        "dato_Id": "2026-08-23",
        "omrType": "EL",
        "omrnr": 3,
        "iso_aar": 2026,
        "iso_uke": 34,
        "fyllingsgrad": 0.63724726,
        "kapasitet_TWh": 8.920932,
        "fylling_TWh": 5.6848392,
        "neste_Publiseringsdato": "2026-09-02T13:00:00",
        "fyllingsgrad_forrige_uke": 0.628683,
        "endring_fyllingsgrad": 0.008564293,
    },
    {
        "dato_Id": "2026-08-23",
        "omrType": "NO",
        "omrnr": 0,
        "iso_aar": 2026,
        "iso_uke": 34,
        "fyllingsgrad": 0.81,
        "kapasitet_TWh": 87.0,
        "fylling_TWh": 70.47,
        "neste_Publiseringsdato": "2026-09-02T13:00:00",
        "fyllingsgrad_forrige_uke": 0.80,
        "endring_fyllingsgrad": 0.01,
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
        assert url == SISTE_UKE
        return JsonResponse(status=200, url=url, body=SISTE_UKE_ROWS)

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"unexpected POST {url}")


def test_printed_publisher_copies_name_from_openapi_description() -> None:
    assert printed_publisher(OPENAPI["info"]) == "Norges vassdrags- og energidirektorat (NVE)"
    assert printed_publisher({"description": "no publisher name here"}) is None


def test_printed_operation_id_copies_last_path_segment() -> None:
    assert printed_operation_id("/api/Magasinstatistikk/HentOffentligDataSisteUke") == (
        "HentOffentligDataSisteUke"
    )
    assert printed_operation_id("/api/Magasinstatistikk/HentOmråder") == "HentOmråder"


def test_printed_endpoint_url_joins_printed_server_and_path() -> None:
    assert printed_endpoint_url(OPENAPI, "/api/Magasinstatistikk/HentOffentligDataSisteUke", OPENAPI_URL) == SISTE_UKE


def test_requestable_url_encodes_printed_area_path() -> None:
    printed = "https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk/HentOmråder"
    assert requestable_url(printed).endswith("HentOmr%C3%A5der")
    assert is_nve_magasin_url(printed)
    assert not is_nve_magasin_url("https://data.ssb.no/api/v0/no/table/06683")


def test_nve_is_a_registered_source() -> None:
    assert "nve" in SOURCE_IDS
    source = build_source("nve")
    assert isinstance(source, NveMagasinSource)
    assert source.source_id == "nve"


def test_nve_lists_capped_printed_paths_and_harvests_access_path(tmp_path: Path) -> None:
    source = NveMagasinSource(http=CatalogHttp(), max_items=2)
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "HentOffentligData",
        "HentOffentligDataSisteUke",
    ]
    assert refs[1].source_native_uri == SISTE_UKE
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset("nve:HentOffentligDataSisteUke")
    assert row is not None
    assert row["source_id"] == "nve"
    assert row["access_path"] == SISTE_UKE
    assert row["license"] is None
    assert row["publisher_name"] == "Norges vassdrags- og energidirektorat (NVE)"
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            ("nve:HentOffentligDataSisteUke",),
        ).fetchone()["payload_json"]
    )
    assert payload["nve_openapi_path"] == "/api/Magasinstatistikk/HentOffentligDataSisteUke"
    registry.close()


def test_nve_offset_skips_already_listed_paths() -> None:
    source = NveMagasinSource(http=CatalogHttp(), max_items=10)
    nxt = source.list_dataset_refs(limit=1, offset=2)
    assert [ref.source_native_id for ref in nxt] == ["HentOmråder"]


def test_cells_from_nve_copy_printed_numeric_fields() -> None:
    cells = cells_from_nve(SISTE_UKE_ROWS)
    fill = [cell for cell in cells if cell[0] == "fyllingsgrad"]
    assert [cell[1] for cell in fill] == [0.63724726, 0.81]
    assert fill[0][2]["omrType"] == "EL"
    assert fill[0][2]["iso_uke"] == "34"


def test_cells_from_nve_copy_printed_area_names() -> None:
    cells = cells_from_nve(
        [{"land": [{"navn": "Norge", "omrType": "NO", "omrnr": 0}]}]
    )
    assert cells == [("navn", "Norge", {"omrType": "NO", "omrnr": "0"})]


def test_fetch_uses_printed_nve_url(tmp_path: Path) -> None:
    source = NveMagasinSource(http=CatalogHttp(), max_items=2)
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        "nve:HentOffentligDataSisteUke",
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == SISTE_UKE
    assert result.table_id == "HentOffentligDataSisteUke"
    assert result.http_status == 200
    expected = sum(
        1 for row in SISTE_UKE_ROWS for value in row.values() if isinstance(value, float)
    )
    assert result.counts.listed == expected
    fill = [
        json.loads(row["value_json"])
        for row in registry.list_observations("nve:HentOffentligDataSisteUke")
        if row["measure"] == "fyllingsgrad"
    ]
    assert sorted(fill) == sorted([0.63724726, 0.81])
    rows = registry.list_observations("nve:HentOffentligDataSisteUke")
    assert all(row["publisher_name"] == "Norges vassdrags- og energidirektorat (NVE)" for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == SISTE_UKE for row in rows)
    registry.close()
