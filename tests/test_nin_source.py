from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.nin import (
    NinSource,
    cells_from_nin,
    is_nin_url,
    nin_table_id,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://nin-kode-api.artsdatabanken.no/swagger/v3.0/swagger.json"
ALLEKODER_URL = "https://nin-kode-api.artsdatabanken.no/v3.0/typer/allekoder"
VARIABLER_URL = "https://nin-kode-api.artsdatabanken.no/v3.0/variabler/allekoder"
KODEOVERSIKT_URL = "https://nin-kode-api.artsdatabanken.no/v3.0/rapporter/kodeoversikt"
DATASET_ID = "nin:v3.0/typer/allekoder"

OPENAPI = {
    "info": {
        "title": "NinKode API",
        "description": "This API version has been deprecated.",
        "version": "3.0",
    },
    "paths": {
        "/v3.0/soek/enkeltSoek": {"get": {"summary": "Search codes"}},
        "/v3.0/rapporter/kodeoversikt": {"get": {}},
        "/v3.0/typer/allekoder": {
            "get": {"summary": "This method gets all Type-codes"}
        },
        "/v3.0/typer/klasse/{kortkode}": {"get": {"summary": "Type by kortkode"}},
        "/v3.0/variabler/allekoder": {"get": {}},
    },
}

ALLEKODER_BODY = {
    "navn": "3.0",
    "typer": [
        {
            "navn": "Bremassiv",
            "kode": {"id": "A-LV-BM", "langkode": "NIN-3.0-T-A-LV-BM"},
            "kategori": "Type",
            "ecosystnivaaEnum": "A",
            "typekategori2Enum": "BM",
            "hovedtypegrupper": [{"skip": True}],
        },
        {
            "navn": "Elveløp",
            "kode": {"id": "A-LV-EL"},
            "kategori": "Type",
            "ecosystnivaaEnum": "A",
            "typekategori2Enum": "EL",
        },
    ],
    "variabler": [],
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
        if url == ALLEKODER_URL:
            return JsonResponse(status=200, url=url, body=ALLEKODER_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nin fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_paths() -> None:
    source = NinSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "v3.0/soek/enkeltSoek",
        "v3.0/rapporter/kodeoversikt",
        "v3.0/typer/allekoder",
        "v3.0/variabler/allekoder",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        "https://nin-kode-api.artsdatabanken.no/v3.0/soek/enkeltSoek",
        KODEOVERSIKT_URL,
        ALLEKODER_URL,
        VARIABLER_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_uses_origin_when_servers_absent() -> None:
    url = printed_endpoint_url(OPENAPI, "/v3.0/typer/allekoder", OPENAPI_URL)
    assert url == ALLEKODER_URL
    assert "swagger" not in url
    with_server = printed_endpoint_url(
        {"servers": [{"url": "https://nin-kode-api.artsdatabanken.no/"}]},
        "/v3.0/typer/allekoder",
        OPENAPI_URL,
    )
    assert with_server == ALLEKODER_URL
    assert printed_operation_id("/v3.0/typer/allekoder") == "v3.0/typer/allekoder"
    assert printed_operation_id("/v3.0/variabler/allekoder") == "v3.0/variabler/allekoder"


def test_nin_is_a_registered_source() -> None:
    assert "nin" in SOURCE_IDS
    source = build_source("nin")
    assert isinstance(source, NinSource)
    assert source.source_id == "nin"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = NinSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 4
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nin"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == ALLEKODER_URL
    assert row["title"] == "v3.0/typer/allekoder"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("geonorge:")
    assert not str(row["id"]).startswith("sodir:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["nin_openapi_path"] == "/v3.0/typer/allekoder"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_type_names(tmp_path: Path) -> None:
    source = NinSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == ALLEKODER_URL
    assert result.table_id == "allekoder"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"Bremassiv", "Elveløp"}
    assert all(row["measure"] == "navn" for row in rows)
    dims = json.loads(by_value["Bremassiv"]["dimensions_json"])
    assert dims["kategori"] == "Type"
    assert dims["ecosystnivaaEnum"] == "A"
    assert dims["typekategori2Enum"] == "BM"
    assert "kode" not in dims
    assert "hovedtypegrupper" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == ALLEKODER_URL for row in rows)
    registry.close()


def test_cells_copy_printed_navn_and_skip_nested() -> None:
    cells = cells_from_nin(ALLEKODER_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "navn"
    assert value == "Bremassiv"
    assert dims["kategori"] == "Type"
    assert "kode" not in dims
    assert "hovedtypegrupper" not in dims
    strings = cells_from_nin(["v1", "v2"])
    assert strings == [("value", "v1", {}), ("value", "v2", {})]
    fallback = cells_from_nin([{"kategori": "Type", "ecosystnivaaEnum": "A"}])
    assert fallback == [("kategori", "Type", {"ecosystnivaaEnum": "A"})]
    with pytest.raises(ValueError, match="JSON object or array"):
        cells_from_nin(None)
    with pytest.raises(ValueError, match="printed no collection"):
        cells_from_nin({"typer": [], "variabler": []})


def test_is_nin_url_accepts_only_v3_collection() -> None:
    assert is_nin_url(ALLEKODER_URL)
    assert is_nin_url(VARIABLER_URL)
    assert nin_table_id(ALLEKODER_URL) == "allekoder"
    assert printed_license_url({}) is None
    assert printed_license_url({"license": {"url": "https://example.invalid/nlod"}}) == (
        "https://example.invalid/nlod"
    )
    assert not is_nin_url(OPENAPI_URL)
    assert not is_nin_url("https://artsdatabanken.no/api/Resource")
    assert not is_nin_url("https://data.norge.no/datasets/x")
    assert not is_nin_url("https://factmaps.sodir.no/api/rest/services/DataService/Data/FeatureServer/1001?f=json")
    assert not is_nin_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = NinSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "v3.0/soek/enkeltSoek"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=2)
    assert [ref.source_native_id for ref in nxt] == ["v3.0/typer/allekoder"]
