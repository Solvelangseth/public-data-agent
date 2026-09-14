from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import classify_access_path, fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.resource_index import index_dataset
from public_data_agent.sources.nbr import (
    NbrSource,
    cells_from_nbr,
    is_nbr_lookup_url,
    is_nbr_url,
    lookups_from_payload,
    lookup_catalog,
    nbr_table_id,
    printed_endpoint_url,
    printed_license_url,
)

OPENAPI_URL = "https://data-nbr.udir.no/swagger/v3/swagger.json"
ENHETER_URL = "https://data-nbr.udir.no/v3/enheter"
MAALFORMER_URL = "https://data-nbr.udir.no/v3/maalformer"
KATEGORIER_URL = "https://data-nbr.udir.no/v3/barnehagekategorier"
NLOD_URL = "https://data.norge.no/nlod/no"
DATASET_ID = "nbr:barnehagekategorier"

OPENAPI = {
    "info": {
        "title": "Nasjonalt barnehageregister API",
        "description": "Data fra Nasjonalt barnehageregister (NBR).",
        "license": {"name": "Lisens: Norsk lisens for offentlige data (NLOD)", "url": NLOD_URL},
        "version": "v3",
    },
    "paths": {
        "/v3/enheter": {"get": {"summary": "Alle enheter"}},
        "/v3/enhet/{orgnr}": {"get": {"summary": "Get enhet"}},
        "/v3/maalformer": {"get": {"summary": "Alle målformer"}},
        "/v3/barnehagekategorier": {"get": {"summary": "Alle barnehagekategorier"}},
    },
}
KATEGORIER_BODY = [
    {
        "Navn": "Offentlig barnehage",
        "Id": "18",
        "nested": {"skip": "dict"},
    },
    {
        "Navn": "Privat barnehage",
        "Id": "20",
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
        if url == KATEGORIER_URL:
            return JsonResponse(status=200, url=url, body=KATEGORIER_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"nbr fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_paths() -> None:
    source = NbrSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "enheter",
        "maalformer",
        "barnehagekategorier",
    ]
    assert [ref.source_native_uri for ref in refs] == [
        ENHETER_URL,
        MAALFORMER_URL,
        KATEGORIER_URL,
    ]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)
    assert OPENAPI_URL not in [ref.source_native_uri for ref in refs]


def test_endpoint_url_uses_openapi_origin_when_servers_absent() -> None:
    url = printed_endpoint_url(OPENAPI, "/v3/barnehagekategorier", OPENAPI_URL)
    assert url == KATEGORIER_URL
    assert "/swagger/" not in url
    with_server = printed_endpoint_url(
        {"servers": [{"url": "https://data-nbr.udir.no/"}]},
        "/v3/barnehagekategorier",
        OPENAPI_URL,
    )
    assert with_server == KATEGORIER_URL


def test_nbr_is_a_registered_source() -> None:
    assert "nbr" in SOURCE_IDS
    source = build_source("nbr")
    assert isinstance(source, NbrSource)
    assert source.source_id == "nbr"


def test_harvest_writes_printed_id_license_and_null_publisher(tmp_path: Path) -> None:
    source = NbrSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 3
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "nbr"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == KATEGORIER_URL
    assert row["title"] == "Alle barnehagekategorier"
    assert row["publisher_name"] is None
    assert row["license"] == NLOD_URL
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("udir:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["nbr_openapi_path"] == "/v3/barnehagekategorier"
    assert payload["license"] == NLOD_URL
    assert payload["publisher"] is None
    registry.close()


def test_url_is_lookup_not_name_observations() -> None:
    assert is_nbr_lookup_url(KATEGORIER_URL)
    assert is_nbr_lookup_url(MAALFORMER_URL)
    assert classify_access_path(KATEGORIER_URL)["kind"] == "lookup"
    assert not is_nbr_lookup_url(ENHETER_URL)


def test_maalformer_skips_empty_id() -> None:
    spec = lookup_catalog(MAALFORMER_URL)
    members = lookups_from_payload(
        [
            {"Id": "", "Navn": "Udefinert"},
            {"Id": "B", "Navn": "Bokmål"},
            {"Id": "N", "Navn": "Nynorsk"},
        ],
        spec,
    )
    assert [item["subject_code"] for item in members] == ["B", "N"]
    assert members[0]["subject_label"] == "Bokmål"


def test_fetch_stores_lookup_entities_not_name_observations(tmp_path: Path) -> None:
    source = NbrSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    indexed = index_dataset(registry, DATASET_ID, http=FetchHttp(), catalogues={})
    assert indexed["fields"] >= 1
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        select={"id": ["18"]},
        http=FetchHttp(),
    )
    assert result.request_url == KATEGORIER_URL
    assert result.table_id == "barnehagekategorier"
    assert result.http_status == 200
    assert result.counts.listed == 1
    assert result.sample[0]["kind"] == "entity"
    assert result.sample[0]["subject_code"] == "18"
    assert result.sample[0]["subject_label"] == "Offentlig barnehage"
    assert registry.list_observations(DATASET_ID) == []
    cap = registry.get_capability(DATASET_ID)
    assert cap["capability"] == "lookup"
    assert cap["subject_scheme"] == "nbr:barnehagekategori"
    assert cap["verified_sample_count"] == 1
    with pytest.raises(ValueError, match="not in nbr:barnehagekategorier"):
        fetch_observations(
            registry,
            DATASET_ID,
            table_id="ignored",
            select={"id": ["NOPE"]},
            http=FetchHttp(),
        )
    registry.close()


def test_cells_copy_printed_navn() -> None:
    cells = cells_from_nbr(KATEGORIER_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "Navn"
    assert value == "Offentlig barnehage"
    assert dims["Id"] == "18"
    fallback = cells_from_nbr([{"Kode": "85.100", "Versjon": "2025"}])
    assert fallback == [("Kode", "85.100", {"Versjon": "2025"})]
    with pytest.raises(ValueError, match="JSON array"):
        cells_from_nbr({"Navn": "Offentlig barnehage"})


def test_is_nbr_url_accepts_only_nbr_host() -> None:
    assert is_nbr_url(KATEGORIER_URL)
    assert is_nbr_url(OPENAPI_URL)
    assert nbr_table_id(KATEGORIER_URL) == "barnehagekategorier"
    assert printed_license_url(OPENAPI["info"]) == NLOD_URL
    assert printed_license_url({}) is None
    assert not is_nbr_url("https://data-nsr.udir.no/skoletyper")
    assert not is_nbr_url("https://data.norge.no/datasets/x")
    assert not is_nbr_url("https://www.udir.no/barnehagekategorier")
    assert not is_nbr_url("https://nbr.udir.no/v3/barnehagekategorier")
    assert not is_nbr_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = NbrSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=2)] == [
        "enheter",
        "maalformer",
    ]
    nxt = source.list_dataset_refs(limit=1, offset=2)
    assert [ref.source_native_id for ref in nxt] == ["barnehagekategorier"]
