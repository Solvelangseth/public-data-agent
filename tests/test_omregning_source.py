from __future__ import annotations

import json
from pathlib import Path

import pytest

from urllib.parse import parse_qs, urlsplit

from public_data_agent.fetch import classify_access_path, fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.omregning import (
    OmregningSource,
    cells_from_omregning,
    is_omregning_search_url,
    is_omregning_url,
    omregning_table_id,
    printed_endpoint_url,
    printed_license_url,
    printed_operation_id,
)

OPENAPI_URL = "https://api.fiskeridir.no/conversion-factor-api/swagger/api"
SEARCH_URL = "https://api.fiskeridir.no/conversion-factor-api/api/v1/conversionfactors/search"
CODES_URL = "https://api.fiskeridir.no/conversion-factor-api/api/v1/conversionfactors/codes"
VESSEL_URL = "https://api.fiskeridir.no/vessel-api/api/v1/vessels"
BUYER_URL = "https://api.fiskeridir.no/buyer-api/v1/locations"
AQUA_URL = "https://api.fiskeridir.no/pub-aqua/api/v1/areas"
DATASET_ID = "omregning:search"

OPENAPI = {
    "openapi": "3.0.1",
    "info": {
        "title": "API for omregningsfaktorer",
        "description": "API for uthenting av omregningsfaktorer.",
        "version": "1.0.0",
    },
    "servers": [
        {
            "url": "https://api.fiskeridir.no/conversion-factor-api",
            "description": "Generated server url",
        }
    ],
    "paths": {
        "/api/v1/conversionfactors/search": {
            "get": {
                "summary": "Hent ut omregningsfaktorer gitt et filter",
                "operationId": "searchConversionFactors",
                "parameters": [
                    {"name": "fish", "in": "query", "required": False},
                ],
            }
        },
        "/api/v1/conversionfactors/{id}": {
            "get": {
                "summary": "Hent én omregningsfaktor",
                "parameters": [
                    {"name": "id", "in": "path", "required": True},
                ],
            }
        },
        "/api/v1/conversionfactors/codes": {
            "get": {
                "summary": "Hent kodeliste",
                "parameters": [
                    {"name": "type", "in": "query", "required": True},
                ],
            }
        },
    },
}
SEARCH_BODY = [
    {
        "fish": "0102",
        "condition": "110",
        "preservation": "99",
        "validityPeriodStart": "1976-12-31T23:00:00Z",
        "validityPeriodEnd": "9999-12-30T23:00:00Z",
        "modifiedTime": "2017-11-01T06:57:07Z",
        "factor": 1,
        "nested": {"skip": True},
    },
    {
        "fish": "0108",
        "condition": "110",
        "preservation": "99",
        "factor": 1.2,
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
        parts = urlsplit(url)
        if parts.path.rstrip("/") != urlsplit(SEARCH_URL).path.rstrip("/"):
            raise AssertionError(f"unexpected GET {url}")
        fish = parse_qs(parts.query).get("fish", [None])[0]
        body = SEARCH_BODY if fish is None else [row for row in SEARCH_BODY if row["fish"] == fish]
        return JsonResponse(status=200, url=url, body=body)

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"omregning fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_and_required_paths() -> None:
    source = OmregningSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["search"]
    assert [ref.source_native_uri for ref in refs] == [SEARCH_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]
    assert all("codes" not in (ref.source_native_id or "") for ref in refs)


def test_endpoint_url_uses_printed_server() -> None:
    url = printed_endpoint_url(OPENAPI, "/api/v1/conversionfactors/search", OPENAPI_URL)
    assert url == SEARCH_URL
    assert "swagger" not in url
    origin_only = printed_endpoint_url({}, "/api/v1/conversionfactors/search", OPENAPI_URL)
    assert origin_only == "https://api.fiskeridir.no/api/v1/conversionfactors/search"


def test_printed_operation_id_is_last_path_segment() -> None:
    assert printed_operation_id("/api/v1/conversionfactors/search") == "search"


def test_printed_license_url_stays_null_without_license_url() -> None:
    assert printed_license_url(OPENAPI["info"]) is None
    assert printed_license_url({"title": "API for omregningsfaktorer"}) is None
    assert printed_license_url({"license": {"name": "NLOD"}}) is None
    assert (
        printed_license_url({"license": {"url": "https://data.norge.no/nlod/no"}})
        == "https://data.norge.no/nlod/no"
    )


def test_omregning_is_a_registered_source() -> None:
    assert "omregning" in SOURCE_IDS
    assert "fiskeridir" in SOURCE_IDS
    assert "aqua" in SOURCE_IDS
    assert "regnskap" in SOURCE_IDS
    source = build_source("omregning")
    assert isinstance(source, OmregningSource)
    assert source.source_id == "omregning"


def test_harvest_writes_printed_id_and_null_publisher_license(tmp_path: Path) -> None:
    source = OmregningSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "omregning"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == SEARCH_URL
    assert row["title"] == "Hent ut omregningsfaktorer gitt et filter"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("fiskeridir:")
    assert not str(row["id"]).startswith("aqua:")
    assert not str(row["id"]).startswith("buyer:")
    assert not str(row["id"]).startswith("regnskap:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["omregning_openapi_path"] == "/api/v1/conversionfactors/search"
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_conversion_factors(tmp_path: Path) -> None:
    source = OmregningSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
        select={"fish": ["0102"]},
    )
    assert result.request_url == f"{SEARCH_URL}?fish=0102"
    assert result.table_id == "search"
    assert result.http_status == 200
    assert result.counts.listed == 1
    rows = registry.list_observations(DATASET_ID)
    assert len(rows) == 1
    assert rows[0]["measure"] == "factor"
    assert json.loads(rows[0]["value_json"]) == 1
    dims = json.loads(rows[0]["dimensions_json"])
    assert dims["fish"] == "0102"
    assert dims["condition"] == "110"
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == SEARCH_URL for row in rows)
    cap = registry.get_capability(DATASET_ID)
    assert cap["capability"] == "observations"
    registry.close()


def test_search_url_is_observations() -> None:
    assert is_omregning_search_url(SEARCH_URL)
    assert not is_omregning_search_url(OPENAPI_URL)
    assert classify_access_path(SEARCH_URL)["kind"] == "observations"


def test_fetch_refuses_unfiltered_conversion_catalog(tmp_path: Path) -> None:
    source = OmregningSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    with pytest.raises(ValueError, match="printed fish code"):
        fetch_observations(
            registry,
            DATASET_ID,
            table_id="search",
            http=FetchHttp(),
        )
    registry.close()


def test_cells_copy_printed_factor() -> None:
    cells = cells_from_omregning(SEARCH_BODY)
    assert cells[0][0] == "factor"
    assert cells[0][1] == 1
    assert cells[0][2]["fish"] == "0102"
    assert "nested" not in cells[0][2]
    assert cells_from_omregning({"factor": 1.5, "condition": "110"}) == [
        ("factor", 1.5, {"condition": "110"})
    ]
    with pytest.raises(ValueError, match="JSON object or array"):
        cells_from_omregning(None)
    with pytest.raises(ValueError, match="numeric factor"):
        cells_from_omregning([])


def test_is_omregning_url_accepts_only_conversion_factor_path() -> None:
    assert is_omregning_url(SEARCH_URL)
    assert is_omregning_url(OPENAPI_URL)
    assert omregning_table_id(SEARCH_URL) == "search"
    assert printed_endpoint_url(OPENAPI, "/api/v1/conversionfactors/search", OPENAPI_URL) == (
        SEARCH_URL
    )
    assert not is_omregning_url(VESSEL_URL)
    assert not is_omregning_url(BUYER_URL)
    assert not is_omregning_url(AQUA_URL)
    assert not is_omregning_url("https://data.brreg.no/regnskapsregisteret/regnskap/log")
    assert not is_omregning_url("https://data.norge.no/datasets/x")
    assert not is_omregning_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = OmregningSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["search"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert nxt == []
