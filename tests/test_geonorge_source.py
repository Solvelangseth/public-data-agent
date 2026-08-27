from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from public_data_agent.fetch import fetch_observations
from public_data_agent.geonorge_rest import (
    cells_from_geonorge,
    collection_request_url,
    is_geonorge_rest_url,
    pick_collection_path,
    printed_collection_paths,
)
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.geonorge import (
    GeonorgeKartkatalogSource,
    is_kartverket_rest,
    printed_license_uri,
    printed_uuid,
)

UUID = "3fcce35c-759b-4c6e-adb9-f03478c6fb72"
DETAILS = f"https://kartkatalog.geonorge.no/metadata/uuid/{UUID}"
GETDATA = f"https://kartkatalog.geonorge.no/api/getdata/{UUID}"
ACCESS = "https://ws.geonorge.no/kommuneinfo/v1/"
OPENAPI = "https://ws.geonorge.no/kommuneinfo/v1/openapi.json"
KOMMUNER = "https://ws.geonorge.no/kommuneinfo/v1/kommuner"
DATASET_ID = f"geonorge:{UUID}"

SEARCH_HIT = {
    "Uuid": UUID,
    "Title": "Administrative inndelinger REST-API",
    "Organization": "Kartverket",
    "DistributionUrl": ACCESS,
    "DistributionProtocol": "W3C:REST",
    "ShowDetailsUrl": DETAILS,
}
OTHER_HIT = {
    "Uuid": "169ba527-36e2-41e9-913f-25cb0fda4b03",
    "Title": "Værdata API",
    "Organization": "Meteorologisk institutt",
    "DistributionUrl": "https://api.met.no/",
    "DistributionProtocol": "W3C:REST",
    "ShowDetailsUrl": "https://kartkatalog.geonorge.no/metadata/uuid/169ba527-36e2-41e9-913f-25cb0fda4b03",
}
GETDATA_BODY = {
    "Uuid": UUID,
    "Title": "Administrative inndelinger REST-API",
    "Abstract": "API for oppslag mot datasettet administrative inndelinger.",
    "Organization": "Kartverket",
    "DistributionUrl": ACCESS,
    "DistributionProtocol": "W3C:REST",
    "Constraints": {
        "AccessConstraints": "Åpne data",
        "UseConstraints": "Lisens",
        "OtherConstraintsLink": "http://inspire.ec.europa.eu/metadata-codelist/ConditionsApplyingToAccessAndUse/noConditionsApply",
    },
}
OPENAPI_BODY = {
    "paths": {
        "/punkt": {
            "get": {
                "parameters": [
                    {"name": "nord", "in": "query", "required": True},
                    {"name": "ost", "in": "query", "required": True},
                ]
            }
        },
        "/kommuner": {
            "get": {
                "parameters": [
                    {"name": "sorter", "in": "query", "required": False},
                ]
            }
        },
        "/fylker": {"get": {"parameters": []}},
        "/kommuner/{kommunenummer}": {"get": {"parameters": []}},
    }
}
KOMMUNER_BODY = [
    {"kommunenavn": "Våler", "kommunenavnNorsk": "Våler", "kommunenummer": "3419"},
    {"kommunenavn": "Oslo", "kommunenavnNorsk": "Oslo", "kommunenummer": "0301"},
]


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        parsed = urlparse(url)
        if parsed.path == "/api/search":
            return {"NumFound": 2, "Results": [OTHER_HIT, SEARCH_HIT]}
        if url == GETDATA:
            return GETDATA_BODY
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == OPENAPI:
            return JsonResponse(status=200, url=url, body=OPENAPI_BODY)
        if url == KOMMUNER:
            return JsonResponse(status=200, url=url, body=KOMMUNER_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"geonorge fetch must GET, not POST {url}")


def test_printed_uuid_copies_catalog_field() -> None:
    assert printed_uuid(SEARCH_HIT) == UUID


def test_kartverket_rest_uses_printed_fields_only() -> None:
    assert is_kartverket_rest(SEARCH_HIT)
    assert not is_kartverket_rest(OTHER_HIT)


def test_license_stays_null_when_catalog_prints_no_license_uri() -> None:
    assert printed_license_uri(GETDATA_BODY) is None


def test_geonorge_is_a_registered_source() -> None:
    assert "geonorge" in SOURCE_IDS
    source = build_source("geonorge")
    assert isinstance(source, GeonorgeKartkatalogSource)
    assert source.source_id == "geonorge"


def test_openapi_picks_printed_kommuner_collection() -> None:
    assert printed_collection_paths(OPENAPI_BODY) == ["/kommuner", "/fylker"]
    assert pick_collection_path(OPENAPI_BODY) == "/kommuner"
    assert collection_request_url(ACCESS, OPENAPI_BODY) == KOMMUNER
    assert is_geonorge_rest_url(ACCESS)
    assert not is_geonorge_rest_url("https://data.norge.no/datasets/x")


def test_cells_copy_printed_kommune_fields() -> None:
    cells = cells_from_geonorge(KOMMUNER_BODY, measure="Administrative inndelinger REST-API")
    assert len(cells) == 2
    measure, value, dims = cells[1]
    assert measure == "Administrative inndelinger REST-API"
    assert value == "Oslo"
    assert dims["kommunenummer"] == "0301"
    assert dims["kommunenavn"] == "Oslo"


def test_geonorge_lists_capped_printed_services_and_harvests_access_path(tmp_path: Path) -> None:
    source = GeonorgeKartkatalogSource(http=CatalogHttp(), max_items=1)
    refs = source.list_dataset_refs()
    assert len(refs) == 1
    assert refs[0].source_native_id == UUID
    assert refs[0].source_native_uri == DETAILS
    search_url = source.http.gets[0]
    query = parse_qs(urlparse(search_url).query)
    assert query["text"] == ["REST-API"]
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 1
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "geonorge"
    assert row["access_path"] == ACCESS
    assert row["publisher_name"] == "Kartverket"
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["geonorge_metadata"]["Uuid"] == UUID
    assert payload["geonorge_metadata"]["DistributionUrl"] == ACCESS
    registry.close()


def test_fetch_uses_openapi_printed_kommuner_url(tmp_path: Path) -> None:
    source = GeonorgeKartkatalogSource(http=CatalogHttp(), max_items=1)
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == KOMMUNER
    assert result.table_id == "kommuner"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    values = [json.loads(row["value_json"]) for row in rows]
    assert sorted(values) == ["Oslo", "Våler"]
    assert all(row["publisher_name"] == "Kartverket" for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == ACCESS for row in rows)
    registry.close()
