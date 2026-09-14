from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import classify_access_path, fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.stormflo import (
    StormfloSource,
    cells_from_stormflo,
    is_stormflo_national_url,
    is_stormflo_url,
    openapi_from_yaml,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
    stormflo_table_id,
)

OPENAPI_URL = "https://stormflo-konsekvens.kartverket.no/openapi.yaml"
NATIONAL_URL = "https://stormflo-konsekvens.kartverket.no/public/api/v1/national.json"
ALLE_URL = "https://stormflo-konsekvens.kartverket.no/public/api/v1/alle_kommuner.json"
LICENSE_URL = "https://www.apache.org/licenses/LICENSE-2.0.html"
DATASET_ID = "stormflo:national.json"
KOMMUNEINFO_URL = "https://api.kartverket.no/kommuneinfo/v1/kommuner"
VANNKRAFT_URL = "https://api.nve.no/web/Powerplant/GetHydroPowerPlants"
AVIATION_URL = "https://api.met.no/weatherapi/aviationforecast/2.0/locations"

OPENAPI_YAML = """openapi: 3.0.4
info:
  title: API - Konsekvenser ved stormflo og havnivåstigning
  license:
    name: Apache 2.0
    url: https://www.apache.org/licenses/LICENSE-2.0.html
  version: 1.0.12
servers:
  - url: https://stormflo-konsekvens.kartverket.no
paths:
  /public/api/v1/{kommune}.json:
    get:
      summary: Statistikk for en gitt kommune.
      description: Bruk kommunenummer til å finne statisitikk.
      operationId: perKommune
      parameters:
        - name: kommune
          in: path
          required: true
  /public/api/v1/national.json:
    get:
      summary: Statistikk for hele landet.
      description: statisitikk over potensielle konsekvenser ved stormflo og havnivåstigning for hele landet.
  /public/api/v1/alle_kommuner.json:
    get:
      summary: Statistikk for alle kommuner.
      description: henter statisitikk over potensielle konsekvenser ved stormflo og havnivåstigning for alle kommuner.
"""
OPENAPI = {
    "info": {
        "title": "API - Konsekvenser ved stormflo og havnivåstigning",
        "license": {"url": LICENSE_URL},
    },
    "servers": [{"url": "https://stormflo-konsekvens.kartverket.no"}],
    "paths": {
        "/public/api/v1/{kommune}.json": {
            "get": {"summary": "Statistikk for en gitt kommune."}
        },
        "/public/api/v1/national.json": {
            "get": {
                "summary": "Statistikk for hele landet.",
                "description": (
                    "statisitikk over potensielle konsekvenser ved stormflo "
                    "og havnivåstigning for hele landet."
                ),
            }
        },
        "/public/api/v1/alle_kommuner.json": {
            "get": {"summary": "Statistikk for alle kommuner."}
        },
    },
}
NATIONAL_BODY = {
    "200ymax": {
        "2025": {"offentlige_bygg": 1810, "private_bygninger": 100022},
        "2100": {"offentlige_bygg": 4176, "private_bygninger": 138781},
    }
}
ALLE_BODY = [
    {
        "kommunenummer": "0301",
        "data": [
            {"code": "200ymax", "year": "2025", "offentlige_bygg": 87},
        ],
    }
]


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_text(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == OPENAPI_URL:
            return OPENAPI_YAML
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == NATIONAL_URL:
            return JsonResponse(status=200, url=url, body=NATIONAL_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"stormflo fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_kommune_path() -> None:
    source = StormfloSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["national.json", "alle_kommuner.json"]
    assert [ref.source_native_uri for ref in refs] == [NATIONAL_URL, ALLE_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert all(ref.source_native_id != "{kommune}.json" for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_openapi_from_yaml_copies_printed_paths() -> None:
    spec = openapi_from_yaml(OPENAPI_YAML)
    assert spec["servers"][0]["url"] == "https://stormflo-konsekvens.kartverket.no"
    assert printed_license_url(spec["info"]) == LICENSE_URL
    assert "/public/api/v1/national.json" in spec["paths"]
    assert "/public/api/v1/{kommune}.json" in spec["paths"]


def test_endpoint_url_joins_printed_server_and_path() -> None:
    url = printed_endpoint_url(OPENAPI, "/public/api/v1/national.json", OPENAPI_URL)
    assert url == NATIONAL_URL
    assert "/openapi.yaml" not in url


def test_printed_operation_id_is_last_path_segment() -> None:
    assert printed_operation_id("/public/api/v1/national.json") == "national.json"
    assert printed_operation_id("/public/api/v1/alle_kommuner.json") == "alle_kommuner.json"


def test_stormflo_is_a_registered_source() -> None:
    assert "stormflo" in SOURCE_IDS
    assert "vannkraft" in SOURCE_IDS
    assert "aviationforecast" in SOURCE_IDS
    assert "kommuneinfo" in SOURCE_IDS
    source = build_source("stormflo")
    assert isinstance(source, StormfloSource)
    assert source.source_id == "stormflo"


def test_harvest_writes_printed_id_and_license(tmp_path: Path) -> None:
    source = StormfloSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "stormflo"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == NATIONAL_URL
    assert "landet" in (row["title"] or "")
    assert row["publisher_name"] is None
    assert row["license"] == LICENSE_URL
    assert not str(row["id"]).startswith("geonorge:")
    assert not str(row["id"]).startswith("kommuneinfo:")
    assert not str(row["id"]).startswith("vannkraft:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["stormflo_openapi_path"] == "/public/api/v1/national.json"
    assert payload["license"] == LICENSE_URL
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_national_numbers(tmp_path: Path) -> None:
    source = StormfloSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == NATIONAL_URL
    assert result.table_id == "national.json"
    assert result.http_status == 200
    assert result.counts.listed == 4
    rows = registry.list_observations(DATASET_ID)
    years = {json.loads(row["dimensions_json"])["year"] for row in rows}
    assert years == {"2025", "2100"}
    by_key = {
        (row["measure"], json.loads(row["dimensions_json"])["year"]): json.loads(
            row["value_json"]
        )
        for row in rows
    }
    assert by_key[("offentlige_bygg", "2025")] == 1810
    assert by_key[("offentlige_bygg", "2100")] == 4176
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] == LICENSE_URL for row in rows)
    assert all(row["access_path"] == NATIONAL_URL for row in rows)
    cap = registry.get_capability(DATASET_ID)
    assert cap["capability"] == "observations"
    registry.close()


def test_national_url_is_observations() -> None:
    assert is_stormflo_national_url(NATIONAL_URL)
    assert not is_stormflo_national_url(ALLE_URL)
    assert classify_access_path(NATIONAL_URL)["kind"] == "observations"
    assert classify_access_path(ALLE_URL)["kind"] == "none"


def test_fetch_refuses_alle_kommuner_dump(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_observation_dataset(
        dataset_id="stormflo:alle_kommuner.json",
        title="Statistikk for alle kommuner",
        publisher_name=None,
        access_path=ALLE_URL,
        license=LICENSE_URL,
    )
    registry.conn.commit()
    with pytest.raises(ValueError, match="national.json"):
        fetch_observations(
            registry,
            "stormflo:alle_kommuner.json",
            table_id="alle_kommuner.json",
            http=FetchHttp(),
        )
    registry.close()


def test_cells_copy_printed_national_and_kommune_numbers() -> None:
    cells = cells_from_stormflo(NATIONAL_BODY)
    assert len(cells) == 4
    measure, value, dims = cells[0]
    assert measure == "offentlige_bygg"
    assert value == 1810
    assert dims == {"code": "200ymax", "year": "2025"}
    kommune_cells = cells_from_stormflo(ALLE_BODY)
    assert kommune_cells == [
        ("offentlige_bygg", 87, {"kommunenummer": "0301", "code": "200ymax", "year": "2025"})
    ]
    with pytest.raises(ValueError, match="JSON object or array"):
        cells_from_stormflo("nope")
    with pytest.raises(ValueError, match="numeric cells"):
        cells_from_stormflo({})


def test_is_stormflo_url_accepts_only_stormflo_host_path() -> None:
    assert is_stormflo_url(NATIONAL_URL)
    assert is_stormflo_url(ALLE_URL)
    assert stormflo_table_id(NATIONAL_URL) == "national.json"
    assert not is_stormflo_url(OPENAPI_URL)
    assert not is_stormflo_url(KOMMUNEINFO_URL)
    assert not is_stormflo_url(VANNKRAFT_URL)
    assert not is_stormflo_url(AVIATION_URL)
    assert not is_stormflo_url("https://data.norge.no/datasets/x")
    assert not is_stormflo_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = StormfloSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "national.json"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["alle_kommuner.json"]
