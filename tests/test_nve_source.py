from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import SelectionTooLarge, classify_access_path, fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from urllib.parse import unquote, urlsplit

from public_data_agent.sources.nve import (
    MAGASIN_MAX_CELLS,
    OMRADE_SCHEME,
    NveMagasinSource,
    cells_from_nve,
    is_nve_magasin_url,
    is_nve_minmax_url,
    is_nve_omrader_url,
    is_nve_siste_uke_url,
    lookups_from_nve_omrader,
    printed_endpoint_url,
    printed_operation_id,
    printed_publisher,
    requestable_url,
    rows_matching_iso_uke,
    selected_nve_iso_uke,
)

OPENAPI_URL = "https://biapi.nve.no/magasinstatistikk/swagger/v1/swagger.json"
SISTE_UKE = (
    "https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk/HentOffentligDataSisteUke"
)
OMRADER_URL = (
    "https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk/HentOmråder"
)
OMRADER_ID = "nve:HentOmråder"
MINMAX_URL = (
    "https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk/"
    "HentOffentligDataMinMaxMedian"
)
MINMAX_ID = "nve:HentOffentligDataMinMaxMedian"
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
MINMAX_ROWS = [
    {
        "omrType": "EL",
        "omrnr": 1,
        "iso_uke": 1,
        "minFyllingsgrad": 0.4569424,
        "minFyllingTWH": 2.7431457,
        "medianFyllingsGrad": 0.6194726,
        "medianFylling_TWH": 3.7188573,
        "maxFyllingsgrad": 0.7595958,
        "maxFyllingTWH": 4.560054,
    },
    {
        "omrType": "NO",
        "omrnr": 0,
        "iso_uke": 1,
        "minFyllingsgrad": 0.4268934,
        "minFyllingTWH": 37.326527,
        "medianFyllingsGrad": 0.6663519,
        "medianFylling_TWH": 58.2642,
        "maxFyllingsgrad": 0.7877036,
        "maxFyllingTWH": 68.87489,
    },
    {
        "omrType": "EL",
        "omrnr": 1,
        "iso_uke": 2,
        "minFyllingsgrad": 0.5,
        "minFyllingTWH": 3.0,
        "medianFyllingsGrad": 0.6,
        "medianFylling_TWH": 3.6,
        "maxFyllingsgrad": 0.7,
        "maxFyllingTWH": 4.2,
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


OMRADER_BODY = {
    "land": [
        {
            "navn": "Norge",
            "navn_langt": "Norge",
            "beskrivelse": "Hele landet",
            "omrType": "NO",
            "omrnr": 0,
        }
    ],
    "elspot": [{"navn": "NO 1", "omrType": "EL", "omrnr": 1}],
    "vassdrag": [{"navn": "Østlandet", "omrType": "VASS", "omrnr": 1}],
}


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == SISTE_UKE:
            return JsonResponse(status=200, url=url, body=SISTE_UKE_ROWS)
        if url == MINMAX_URL:
            return JsonResponse(status=200, url=url, body=MINMAX_ROWS)
        path = unquote(urlsplit(url).path)
        if path.rstrip("/").endswith("HentOmråder"):
            return JsonResponse(status=200, url=url, body=OMRADER_BODY)
        raise AssertionError(f"unexpected GET {url}")

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
    cap = registry.get_capability("nve:HentOffentligDataSisteUke")
    assert cap["capability"] == "observations"
    registry.close()


def test_siste_uke_url_is_observations() -> None:
    assert is_nve_siste_uke_url(SISTE_UKE)
    assert not is_nve_siste_uke_url(
        "https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk/HentOffentligData"
    )
    assert classify_access_path(SISTE_UKE)["kind"] == "observations"
    assert (
        classify_access_path(
            "https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk/HentOffentligData"
        )["kind"]
        == "none"
    )
    assert classify_access_path(OMRADER_URL)["kind"] == "lookup"
    assert is_nve_omrader_url(OMRADER_URL)
    assert is_nve_minmax_url(MINMAX_URL)
    assert not is_nve_minmax_url(SISTE_UKE)
    assert classify_access_path(MINMAX_URL)["kind"] == "observations"


def test_fetch_stores_omrader_as_lookup(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_observation_dataset(
        dataset_id=OMRADER_ID,
        title="Henter områder for magasinstatistikk",
        publisher_name="Norges vassdrags- og energidirektorat (NVE)",
        access_path=OMRADER_URL,
        license=None,
    )
    registry.conn.commit()
    result = fetch_observations(
        registry,
        OMRADER_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.http_status == 200
    assert result.counts.listed == 3
    assert registry.list_observations(OMRADER_ID) == []
    rows = registry.list_records(OMRADER_ID, kind="entity")
    codes = {row["subject_code"] for row in rows}
    assert codes == {"NO:0", "EL:1", "VASS:1"}
    assert all(row["subject_scheme"] == OMRADE_SCHEME for row in rows)
    norge = next(row for row in rows if row["subject_code"] == "NO:0")
    assert norge["subject_label"] == "Norge"
    cap = registry.get_capability(OMRADER_ID)
    assert cap["capability"] == "lookup"
    registry.close()


def test_lookups_copy_printed_omrade_keys() -> None:
    members = lookups_from_nve_omrader(OMRADER_BODY)
    assert members[0]["subject_code"] == "NO:0"
    assert members[0]["subject_scheme"] == OMRADE_SCHEME
    wrapped = lookups_from_nve_omrader([OMRADER_BODY])
    assert [item["subject_code"] for item in wrapped] == [
        item["subject_code"] for item in members
    ]


def test_fetch_gets_printed_minmax_iso_uke(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_observation_dataset(
        dataset_id=MINMAX_ID,
        title="Henter magasinstatistikk for Min, Max, og Median",
        publisher_name="Norges vassdrags- og energidirektorat (NVE)",
        access_path=MINMAX_URL,
        license=None,
    )
    registry.conn.commit()
    result = fetch_observations(
        registry,
        MINMAX_ID,
        table_id="ignored",
        http=FetchHttp(),
        select={"iso_uke": ["1"]},
    )
    assert result.request_url == MINMAX_URL
    assert result.http_status == 200
    assert result.counts.listed == 12
    rows = registry.list_observations(MINMAX_ID)
    by_key = {
        (row["measure"], json.loads(row["dimensions_json"])["omrType"]): json.loads(
            row["value_json"]
        )
        for row in rows
    }
    assert by_key[("minFyllingsgrad", "EL")] == 0.4569424
    assert by_key[("minFyllingsgrad", "NO")] == 0.4268934
    assert all(json.loads(row["dimensions_json"])["iso_uke"] == "1" for row in rows)
    assert all(row["license"] is None for row in rows)
    cap = registry.get_capability(MINMAX_ID)
    assert cap["capability"] == "observations"
    registry.close()


def test_fetch_refuses_unfiltered_minmax(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_observation_dataset(
        dataset_id=MINMAX_ID,
        title="minmax",
        publisher_name=None,
        access_path=MINMAX_URL,
        license=None,
    )
    registry.conn.commit()
    with pytest.raises(ValueError, match="printed iso_uke"):
        fetch_observations(
            registry,
            MINMAX_ID,
            table_id="ignored",
            http=FetchHttp(),
        )
    registry.close()


def test_selected_iso_uke_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError, match="omrType"):
        selected_nve_iso_uke({"omrType": ["NO"]})
    assert selected_nve_iso_uke({"iso_uke": ["1"]}) == "1"
    assert [row["iso_uke"] for row in rows_matching_iso_uke(MINMAX_ROWS, "1")] == [1, 1]
    with pytest.raises(ValueError, match="printed ISO week"):
        rows_matching_iso_uke(MINMAX_ROWS, "99")


def test_fetch_refuses_full_magasin_dump(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_observation_dataset(
        dataset_id="nve:HentOffentligData",
        title="Henter magasinstatistikk",
        publisher_name=None,
        access_path="https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk/HentOffentligData",
        license=None,
    )
    registry.conn.commit()
    with pytest.raises(ValueError, match="HentOffentligDataSisteUke"):
        fetch_observations(
            registry,
            "nve:HentOffentligData",
            table_id="HentOffentligData",
            http=FetchHttp(),
        )
    registry.close()


def test_fetch_refuses_more_than_magasin_cell_cap(tmp_path: Path) -> None:
    huge = []
    while True:
        huge.append(SISTE_UKE_ROWS[0])
        if sum(1 for row in huge for value in row.values() if isinstance(value, float)) > MAGASIN_MAX_CELLS:
            break

    class HugeHttp:
        def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
            return JsonResponse(status=200, url=url, body=huge)

        def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
            raise AssertionError(f"unexpected POST {url}")

    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_observation_dataset(
        dataset_id="nve:HentOffentligDataSisteUke",
        title="Henter magasinstatistikk siste uke",
        publisher_name=None,
        access_path=SISTE_UKE,
        license=None,
    )
    registry.conn.commit()
    with pytest.raises(SelectionTooLarge):
        fetch_observations(
            registry,
            "nve:HentOffentligDataSisteUke",
            table_id="HentOffentligDataSisteUke",
            http=HugeHttp(),
        )
    registry.close()
