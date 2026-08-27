from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.baf import (
    BafSource,
    cells_from_baf,
    is_baf_url,
    baf_table_id,
    printed_endpoint_url,
    printed_license_url,
)

SWAGGER_URL = "https://www.barnehagefakta.no/swagger/docs/v1"
FYLKER_URL = "https://www.barnehagefakta.no/api/Fylker"
LOCATION_URL = "https://www.barnehagefakta.no/api/Location"
DATASET_ID = "baf:Fylker"

SWAGGER = {
    "swagger": "2.0",
    "info": {"version": "v1", "title": "Barnehagefakta"},
    "host": "www.barnehagefakta.no",
    "schemes": ["https"],
    "paths": {
        "/api/Barnehage/{id}": {"get": {"summary": "En barnehage"}},
        "/api/Fylker": {"get": {"summary": "Returnerer struktur med fylker / kommuner"}},
        "/api/Kommune/{kommunenummer}": {"get": {"summary": "En kommune"}},
        "/api/Location": {"get": {"summary": "Returnerer alle barnehager"}},
    },
}
FYLKER_BODY = {
    "fylker": [
        {
            "fylkesnavn": "Oslo",
            "fylkesnummer": "03",
            "kommuner": [{"kommunenavn": "Oslo", "kommunenummer": "0301"}],
        },
        {
            "fylkesnavn": "Rogaland",
            "fylkesnummer": "11",
        },
    ]
}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == SWAGGER_URL:
            return SWAGGER
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == FYLKER_URL:
            return JsonResponse(status=200, url=url, body=FYLKER_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"baf fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_paths() -> None:
    source = BafSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["Fylker", "Location"]
    assert [ref.source_native_uri for ref in refs] == [FYLKER_URL, LOCATION_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert SWAGGER_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_uses_printed_swagger_host() -> None:
    url = printed_endpoint_url(SWAGGER, "/api/Fylker", SWAGGER_URL)
    assert url == FYLKER_URL
    assert "/swagger/" not in url
    with_server = printed_endpoint_url(
        {"servers": [{"url": "https://www.barnehagefakta.no/"}]},
        "/api/Fylker",
        SWAGGER_URL,
    )
    assert with_server == FYLKER_URL


def test_baf_is_a_registered_source() -> None:
    assert "baf" in SOURCE_IDS
    source = build_source("baf")
    assert isinstance(source, BafSource)
    assert source.source_id == "baf"


def test_harvest_writes_printed_id_and_null_license_publisher(tmp_path: Path) -> None:
    source = BafSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "baf"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == FYLKER_URL
    assert row["title"] == "Returnerer struktur med fylker / kommuner"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("udir:")
    assert not str(row["id"]).startswith("nbr:")
    assert not str(row["id"]).startswith("nfr:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["baf_swagger_path"] == "/api/Fylker"
    assert payload["license"] is None
    assert payload["publisher"] is None
    assert registry.enrichment_count() == 0
    registry.close()


def test_fetch_gets_printed_fylker(tmp_path: Path) -> None:
    source = BafSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == FYLKER_URL
    assert result.table_id == "Fylker"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = {json.loads(row["value_json"]) for row in rows}
    assert values == {"Oslo", "Rogaland"}
    assert all(row["measure"] == "fylkesnavn" for row in rows)
    by_name = {json.loads(row["value_json"]): row for row in rows}
    dims = json.loads(by_name["Oslo"]["dimensions_json"])
    assert dims["fylkesnummer"] == "03"
    assert "kommuner" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == FYLKER_URL for row in rows)
    registry.close()


def test_cells_copy_printed_fylker_and_location_navn() -> None:
    cells = cells_from_baf(FYLKER_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "fylkesnavn"
    assert value == "Oslo"
    assert dims["fylkesnummer"] == "03"
    assert "kommuner" not in dims
    unwrapped = cells_from_baf([{"orgnr": "999669514", "navn": "Rabben barnehage"}])
    assert unwrapped == [("navn", "Rabben barnehage", {"orgnr": "999669514"})]
    fallback = cells_from_baf({"fylker": [{"fylkesnummer": "03"}]})
    assert fallback == [("fylkesnummer", "03", {})]
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_baf("fylker")
    with pytest.raises(ValueError, match="printed no collection list"):
        cells_from_baf({"Sidenummer": 1, "AntallPerSide": 1000})
    with pytest.raises(ValueError, match="printed no collection members"):
        cells_from_baf({"fylker": []})


def test_is_baf_url_accepts_only_barnehagefakta_host() -> None:
    assert is_baf_url(FYLKER_URL)
    assert is_baf_url(SWAGGER_URL)
    assert is_baf_url("https://barnehagefakta.no/api/Fylker")
    assert baf_table_id(FYLKER_URL) == "Fylker"
    assert printed_license_url(SWAGGER["info"]) is None
    assert printed_license_url({}) is None
    assert printed_license_url({"license": {"url": "https://data.norge.no/nlod/no"}}) == (
        "https://data.norge.no/nlod/no"
    )
    assert not is_baf_url("https://data-nbr.udir.no/v3/barnehagekategorier")
    assert not is_baf_url("https://data-nsr.udir.no/skoletyper")
    assert not is_baf_url("https://data-nfr.udir.no/v4/skolefritidsordningskategorier")
    assert not is_baf_url("https://data-nxr-fellestjeneste.udir.no/api/v2/fylkedata")
    assert not is_baf_url("https://www.udir.no/barnehagefakta")
    assert not is_baf_url("https://data.norge.no/datasets/x")
    assert not is_baf_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = BafSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["Fylker"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["Location"]
