from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.regnskap import (
    RegnskapSource,
    cells_from_regnskap,
    is_regnskap_url,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
    regnskap_table_id,
)

OPENAPI_URL = "https://data.brreg.no/regnskapsregisteret/regnskap/v3/api-docs"
LOG_URL = "https://data.brreg.no/regnskapsregisteret/regnskap/log"
BY_METHOD_URL = "https://data.brreg.no/statistikk/by-method"
BY_IP_URL = "https://data.brreg.no/statistikk/by-ip"
BY_ORGNR_URL = "https://data.brreg.no/statistikk/by-orgnr"
ENHET_URL = "https://data.brreg.no/enhetsregisteret/api/organisasjonsformer"
DATASET_ID = "regnskap:regnskapsregisteret/regnskap/log"

OPENAPI = {
    "openapi": "3.1.0",
    "info": {
        "title": "RegnskapsRegister-API",
        "version": "1.1.16",
    },
    "servers": [{"url": "https://data.brreg.no", "description": "Generated server url"}],
    "paths": {
        "/statistikk/by-orgnr": {
            "get": {
                "summary": "Query for statisctics, by organization number",
                "operationId": "getStatisticsByOrgnr",
                "parameters": [
                    {"name": "fraDato", "in": "query", "required": False},
                ],
            }
        },
        "/statistikk/by-method": {
            "get": {
                "summary": "Query for statisctics, by REST method",
                "operationId": "getStatisticsByMethod",
            }
        },
        "/statistikk/by-ip": {
            "get": {
                "summary": "Query for statisctics, by IP",
                "operationId": "getStatisticsByIp",
            }
        },
        "/regnskapsregisteret/regnskap/{orgNummer}": {
            "get": {
                "operationId": "getRegnskap",
                "parameters": [
                    {"name": "orgNummer", "in": "path", "required": True},
                ],
            }
        },
        "/regnskapsregisteret/regnskap/log": {
            "get": {
                "summary": "Query for log.",
                "operationId": "getLog",
            }
        },
        "/regnskapsregisteret/regnskap/aarsregnskap/kopi/{orgnr}/aar": {
            "get": {
                "summary": "Hent ut en liste over år hvor kopi av årsregnskap er tilgjengelig",
                "parameters": [
                    {"name": "orgnr", "in": "path", "required": True},
                ],
            }
        },
        "/regnskapsregisteret/regnskap/aarsregnskap/kopi/{orgnr}/{aar}": {
            "get": {
                "summary": "Hent ut kopi av årsregnskap som PDF",
                "parameters": [
                    {"name": "orgnr", "in": "path", "required": True},
                    {"name": "aar", "in": "path", "required": True},
                ],
            }
        },
    },
}
LOG_BODY = [
    "20180102202758-masse.xml",
    "20180103202854-masse.xml",
    {"nested": {"skip": True}},
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
        if url == LOG_URL:
            return JsonResponse(status=200, url=url, body=LOG_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"regnskap fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_required_paths() -> None:
    source = RegnskapSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "statistikk/by-orgnr",
        "statistikk/by-method",
        "statistikk/by-ip",
        "regnskapsregisteret/regnskap/log",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        BY_ORGNR_URL,
        BY_METHOD_URL,
        BY_IP_URL,
        LOG_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]
    assert all("orgNummer" not in (ref.source_native_id or "") for ref in refs)
    assert all("aar" not in (ref.source_native_id or "") for ref in refs)


def test_endpoint_url_uses_printed_server() -> None:
    url = printed_endpoint_url(OPENAPI, "/regnskapsregisteret/regnskap/log", OPENAPI_URL)
    assert url == LOG_URL
    assert "api-docs" not in url
    with_host = printed_endpoint_url(
        {
            "host": "data.brreg.no",
            "schemes": ["https"],
        },
        "/regnskapsregisteret/regnskap/log",
        OPENAPI_URL,
    )
    assert with_host == LOG_URL
    origin_only = printed_endpoint_url({}, "/regnskapsregisteret/regnskap/log", OPENAPI_URL)
    assert origin_only == LOG_URL


def test_printed_operation_id_is_path_without_leading_slash() -> None:
    assert printed_operation_id("/regnskapsregisteret/regnskap/log") == (
        "regnskapsregisteret/regnskap/log"
    )
    assert printed_operation_id("/statistikk/by-method") == "statistikk/by-method"


def test_printed_license_url_stays_null_without_license_url() -> None:
    assert printed_license_url(OPENAPI["info"]) is None
    assert printed_license_url({"title": "RegnskapsRegister-API"}) is None
    assert printed_license_url({"license": {"name": "NLOD"}}) is None
    assert (
        printed_license_url({"license": {"url": "https://data.norge.no/nlod/no"}})
        == "https://data.norge.no/nlod/no"
    )


def test_regnskap_is_a_registered_source() -> None:
    assert "regnskap" in SOURCE_IDS
    assert "brreg" in SOURCE_IDS
    assert "ogccoverages" in SOURCE_IDS
    assert "lister" in SOURCE_IDS
    source = build_source("regnskap")
    assert isinstance(source, RegnskapSource)
    assert source.source_id == "regnskap"


def test_harvest_writes_printed_id_and_null_publisher_license(tmp_path: Path) -> None:
    source = RegnskapSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 4
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "regnskap"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == LOG_URL
    assert row["title"] == "Query for log."
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("brreg:")
    assert not str(row["id"]).startswith("ogccoverages:")
    assert not str(row["id"]).startswith("datanorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["regnskap_openapi_path"] == "/regnskapsregisteret/regnskap/log"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_log_filenames(tmp_path: Path) -> None:
    source = RegnskapSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == LOG_URL
    assert result.table_id == "log"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {
        "20180102202758-masse.xml",
        "20180103202854-masse.xml",
    }
    assert by_value["20180102202758-masse.xml"]["measure"] == "value"
    assert json.loads(by_value["20180102202758-masse.xml"]["dimensions_json"]) == {
        "value": "20180102202758-masse.xml"
    }
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == LOG_URL for row in rows)
    registry.close()


def test_cells_copy_printed_filenames_or_title() -> None:
    cells = cells_from_regnskap(LOG_BODY)
    assert cells == [
        ("value", "20180102202758-masse.xml", {"value": "20180102202758-masse.xml"}),
        ("value", "20180103202854-masse.xml", {"value": "20180103202854-masse.xml"}),
    ]
    assert cells_from_regnskap({"title": "Query for log.", "id": "getLog"}) == [
        ("title", "Query for log.", {"id": "getLog"})
    ]
    assert cells_from_regnskap("20180102202758-masse.xml") == [
        ("value", "20180102202758-masse.xml", {"value": "20180102202758-masse.xml"})
    ]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_regnskap(None)
    with pytest.raises(ValueError, match="collection members"):
        cells_from_regnskap([])


def test_is_regnskap_url_accepts_printed_paths_not_enhetsregisteret() -> None:
    assert is_regnskap_url(LOG_URL)
    assert is_regnskap_url(BY_METHOD_URL)
    assert is_regnskap_url(OPENAPI_URL)
    assert regnskap_table_id(LOG_URL) == "log"
    assert printed_endpoint_url(OPENAPI, "/regnskapsregisteret/regnskap/log", OPENAPI_URL) == LOG_URL
    assert not is_regnskap_url(ENHET_URL)
    assert not is_regnskap_url("https://kartverket-ogc-api.azurewebsites.net/collections")
    assert not is_regnskap_url("https://data.norge.no/datasets/x")
    assert not is_regnskap_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = RegnskapSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "statistikk/by-orgnr"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=3)
    assert [ref.source_native_id for ref in nxt] == [
        "regnskapsregisteret/regnskap/log"
    ]
