from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.riksantikvaren import (
    RiksantikvarenSource,
    cells_from_riksantikvaren,
    is_riksantikvaren_url,
    printed_layer_url,
    printed_publisher,
    riksantikvaren_table_id,
)

LIST_URL = (
    "https://kart.ra.no/arcgis/rest/services/MABYGIS/MABYGIS_rest_ro/FeatureServer?f=json"
)
BORHULL_URL = (
    "https://kart.ra.no/arcgis/rest/services/MABYGIS/MABYGIS_rest_ro/FeatureServer/0?f=json"
)
DISPENSASJONER_URL = (
    "https://kart.ra.no/arcgis/rest/services/MABYGIS/MABYGIS_rest_ro/FeatureServer/2?f=json"
)
DATASET_ID = "riksantikvaren:Borhull"

LIST_BODY = {
    "copyrightText": "",
    "serviceDescription": "",
    "layers": [
        {"id": 0, "name": "Borhull", "type": "Feature Layer"},
        {"id": 2, "name": "Dispensasjoner", "type": "Feature Layer"},
        {"id": 3, "name": "", "type": "Feature Layer"},
        {"name": "missing-id", "type": "Feature Layer"},
    ],
}

BORHULL_BODY = {
    "id": 0,
    "name": "Borhull",
    "copyrightText": "",
    "fields": [
        {
            "name": "OBJECTID",
            "alias": "OBJECTID",
            "type": "esriFieldTypeOID",
            "nested": {"skip": True},
        },
        {
            "name": "X_UTM33",
            "alias": "X_UTM33",
            "type": "esriFieldTypeDouble",
        },
        {
            "name": "",
            "alias": "EIER",
            "type": "esriFieldTypeString",
        },
    ],
}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == LIST_URL:
            return LIST_BODY
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == BORHULL_URL:
            return JsonResponse(status=200, url=url, body=BORHULL_BODY)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"riksantikvaren fetch must GET, not POST {url}")


def test_printed_refs_skip_blank_names() -> None:
    source = RiksantikvarenSource(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["Borhull", "Dispensasjoner"]
    assert [ref.source_native_uri for ref in refs] == [BORHULL_URL, DISPENSASJONER_URL]
    assert LIST_URL not in [ref.source_native_uri for ref in refs]


def test_layer_url_joins_printed_origin_and_id() -> None:
    url = printed_layer_url(0, LIST_URL)
    assert url == BORHULL_URL
    assert "layers" not in url
    assert "/query" not in url


def test_printed_publisher_copies_only_copyright_text() -> None:
    assert printed_publisher(LIST_BODY) is None
    assert printed_publisher({}) is None
    assert printed_publisher({"copyrightText": "  "}) is None


def test_riksantikvaren_is_a_registered_source() -> None:
    assert "riksantikvaren" in SOURCE_IDS
    source = build_source("riksantikvaren")
    assert isinstance(source, RiksantikvarenSource)
    assert source.source_id == "riksantikvaren"


def test_harvest_writes_printed_id_null_license_and_publisher(tmp_path: Path) -> None:
    source = RiksantikvarenSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "riksantikvaren"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == BORHULL_URL
    assert row["title"] == "Borhull"
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    assert not str(row["id"]).startswith("geonorge:")
    assert not str(row["id"]).startswith("opencom:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["riksantikvaren_layer"]["id"] == 0
    assert payload["license"] is None
    assert payload["publisher"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_borhull_fields(tmp_path: Path) -> None:
    source = RiksantikvarenSource(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == BORHULL_URL
    assert result.table_id == "0"
    assert result.http_status == 200
    assert result.counts.listed == 3
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {"OBJECTID", "X_UTM33", "EIER"}
    assert by_value["OBJECTID"]["measure"] == "name"
    assert by_value["X_UTM33"]["measure"] == "name"
    assert by_value["EIER"]["measure"] == "alias"
    dims = json.loads(by_value["X_UTM33"]["dimensions_json"])
    assert dims["alias"] == "X_UTM33"
    assert dims["type"] == "esriFieldTypeDouble"
    assert "nested" not in dims
    assert all(row["publisher_name"] is None for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == BORHULL_URL for row in rows)
    registry.close()


def test_cells_copy_printed_field_names() -> None:
    cells = cells_from_riksantikvaren(BORHULL_BODY)
    assert len(cells) == 3
    measure, value, dims = cells[0]
    assert measure == "name"
    assert value == "OBJECTID"
    assert dims["alias"] == "OBJECTID"
    assert "nested" not in dims
    assert cells[2] == (
        "alias",
        "EIER",
        {"name": "", "type": "esriFieldTypeString"},
    )
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_riksantikvaren([{"name": "Borhull"}])
    with pytest.raises(ValueError, match="fields array"):
        cells_from_riksantikvaren({"name": "Borhull"})
    with pytest.raises(ValueError, match="printed no fields"):
        cells_from_riksantikvaren({"fields": []})


def test_is_riksantikvaren_url_accepts_only_mabygis_layer() -> None:
    assert is_riksantikvaren_url(BORHULL_URL)
    assert is_riksantikvaren_url(DISPENSASJONER_URL)
    assert riksantikvaren_table_id(BORHULL_URL) == "0"
    assert printed_layer_url(0, LIST_URL) == BORHULL_URL
    assert not is_riksantikvaren_url(LIST_URL)
    assert not is_riksantikvaren_url(
        "https://kart.ra.no/arcgis/rest/services/Askeladden/Askeladden/FeatureServer/0?f=json"
    )
    assert not is_riksantikvaren_url(
        "https://factmaps.sodir.no/api/rest/services/DataService/Data/FeatureServer/1001?f=json"
    )
    assert not is_riksantikvaren_url("https://kartkatalog.geonorge.no/api/search")
    assert not is_riksantikvaren_url("https://ws.geonorge.no/hoydedata/v1/datakilder")
    assert not is_riksantikvaren_url("https://geo.ngu.no/api/features")
    assert not is_riksantikvaren_url(
        "https://nin-kode-api.artsdatabanken.no/v3.0/typer/allekoder"
    )
    assert not is_riksantikvaren_url("https://api.kartverket.no/kommuneinfo/v1/fylker")
    assert not is_riksantikvaren_url(None)


def test_limit_and_offset_slice_printed_layers() -> None:
    source = RiksantikvarenSource(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == [
        "Borhull"
    ]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["Dispensasjoner"]
