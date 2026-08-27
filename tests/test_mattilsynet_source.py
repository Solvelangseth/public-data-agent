from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.mattilsynet import (
    MattilsynetPlantevernSource,
    cells_from_mattilsynet,
    is_mattilsynet_url,
    mattilsynet_table_id,
    printed_publisher,
)

OPENAPI_URL = "https://api.plantevernmidler.mattilsynet.io/json"
HOBBY_URL = "https://api.plantevernmidler.mattilsynet.io/hobby_preparater"
PREPARATER_URL = "https://api.plantevernmidler.mattilsynet.io/preparater"
NLOD_URL = "https://data.norge.no/nlod/no/2.0"
DATASET_ID = "mattilsynet:hobby_preparater"

OPENAPI = {
    "info": {
        "title": "Plantevernmidler",
        "description": "Mattilsynet plantevernmidler OpenAPI",
        "version": "1.0.0",
        "license": {"url": NLOD_URL},
    },
    "paths": {
        "/hobby_preparater": {
            "get": {"description": "Hobbypreparater"}
        },
        "/preparater": {
            "get": {"description": "Preparater"}
        },
        "/preparat/{id}": {
            "get": {"description": "Ett preparat"}
        },
    },
}
HOBBY_BODY = {
    "preparater": [
        {
            "id": 4572,
            "navn": "ANDERcontrol",
            "form": "Rovmidd",
            "status": "Godkjent",
            "godkjentTil": "2027-12-31",
            "registreringsnummer": "2021.12",
            "hobbyPreparat": True,
            "merknader": ["skip-list"],
            "detaljer": {"skip": "dict"},
        },
        {
            "id": 12,
            "navn": "Annet middel",
            "form": "Granulat",
        },
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
        assert url == HOBBY_URL
        return JsonResponse(status=200, url=url, body=HOBBY_BODY)

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"mattilsynet fetch must GET, not POST {url}")


def test_printed_refs_skip_templated_paths() -> None:
    source = MattilsynetPlantevernSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["hobby_preparater", "preparater"]
    assert [ref.source_native_uri for ref in refs] == [HOBBY_URL, PREPARATER_URL]
    assert all("{" not in (ref.source_native_uri or "") for ref in refs)


def test_printed_publisher_copies_token_from_openapi_description() -> None:
    assert printed_publisher(OPENAPI["info"]) == "Mattilsynet"
    assert printed_publisher({"description": "no publisher name here"}) is None


def test_mattilsynet_is_a_registered_source() -> None:
    assert "mattilsynet" in SOURCE_IDS
    source = build_source("mattilsynet")
    assert isinstance(source, MattilsynetPlantevernSource)
    assert source.source_id == "mattilsynet"


def test_harvest_writes_printed_access_path_license_and_publisher(tmp_path: Path) -> None:
    source = MattilsynetPlantevernSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "mattilsynet"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == HOBBY_URL
    assert row["title"] == "Hobbypreparater"
    assert row["publisher_name"] == "Mattilsynet"
    assert row["license"] == NLOD_URL
    assert not str(row["id"]).startswith("datanorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["mattilsynet_openapi_path"] == "/hobby_preparater"
    assert payload["license"] == NLOD_URL
    registry.close()


def test_fetch_writes_observations_and_provenance(tmp_path: Path) -> None:
    source = MattilsynetPlantevernSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == HOBBY_URL
    assert result.table_id == "hobby_preparater"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    assert sorted(json.loads(row["value_json"]) for row in rows) == [
        "ANDERcontrol",
        "Annet middel",
    ]
    assert all(row["measure"] == "navn" for row in rows)
    ander = next(row for row in rows if json.loads(row["value_json"]) == "ANDERcontrol")
    dims = json.loads(ander["dimensions_json"])
    assert dims["id"] == "4572"
    assert dims["form"] == "Rovmidd"
    assert "merknader" not in dims
    assert "detaljer" not in dims
    assert all(row["publisher_name"] == "Mattilsynet" for row in rows)
    assert all(row["license"] == NLOD_URL for row in rows)
    assert all(row["access_path"] == HOBBY_URL for row in rows)
    registry.close()


def test_cells_from_copies_printed_navn() -> None:
    cells = cells_from_mattilsynet(HOBBY_BODY)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "navn"
    assert value == "ANDERcontrol"
    assert dims["id"] == "4572"
    assert dims["form"] == "Rovmidd"
    assert dims["hobbyPreparat"] == "True"
    assert "merknader" not in dims
    fallback = cells_from_mattilsynet([{"id": 9, "form": "Pulver"}])
    assert fallback == [("id", 9, {"form": "Pulver"})]
    with pytest.raises(ValueError, match="JSON object or array"):
        cells_from_mattilsynet("not-json")


def test_is_mattilsynet_url_accepts_only_plantevernmidler_host() -> None:
    assert is_mattilsynet_url(HOBBY_URL)
    assert is_mattilsynet_url(OPENAPI_URL)
    assert mattilsynet_table_id(HOBBY_URL) == "hobby_preparater"
    assert not is_mattilsynet_url("https://data.norge.no/datasets/x")
    assert not is_mattilsynet_url("https://mattilsynet.no/hobby_preparater")
    assert not is_mattilsynet_url("https://api.mattilsynet.io/hobby_preparater")
    assert not is_mattilsynet_url(None)


def test_limit_and_offset_slice_printed_paths() -> None:
    source = MattilsynetPlantevernSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "hobby_preparater"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["preparater"]
