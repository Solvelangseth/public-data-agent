from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.ssbv2 import (
    Ssbv2Source,
    cells_from_ssbv2,
    is_ssbv2_url,
    printed_data_url,
    printed_tables,
    ssbv2_table_id,
)

LIST_URL = "https://data.ssb.no/api/pxwebapi/v2/tables"
TABLE_13760_URL = (
    "https://data.ssb.no/api/pxwebapi/v2/tables/13760/data?lang=no&outputFormat=json-stat2"
)
TABLE_14483_URL = (
    "https://data.ssb.no/api/pxwebapi/v2/tables/14483/data?lang=no&outputFormat=json-stat2"
)
SSB_V0_URL = "https://data.ssb.no/api/v0/no/table/06683"
DATASET_ID = "ssbv2:13760"

CATALOG = {
    "language": "no",
    "tables": [
        {
            "id": "13760",
            "label": "13760: Arbeidsstyrken, sysselsatte, arbeidsledige",
            "description": "",
            "source": "Statistisk sentralbyrå",
            "links": [
                {
                    "rel": "self",
                    "href": "https://data.ssb.no/api/pxwebapi/v2/tables/13760?lang=no",
                },
                {"rel": "data", "href": TABLE_13760_URL},
            ],
        },
        {
            "id": "14483",
            "label": "14483: Personer, etter arbeidsstyrkestatus",
            "source": "Statistisk sentralbyrå",
            "links": [{"rel": "data", "href": TABLE_14483_URL}],
        },
        {
            "id": "",
            "label": "skip empty id",
            "links": [{"rel": "data", "href": TABLE_13760_URL}],
        },
        {
            "id": "99999",
            "label": "Missing data href",
            "links": [],
        },
        {"nested": True},
    ],
}
DATA_13760 = {
    "version": "2.0",
    "class": "dataset",
    "label": "13760: Arbeidsstyrken",
    "source": "Statistisk sentralbyrå",
    "id": ["Justering", "ContentsCode", "Tid"],
    "size": [2, 1, 1],
    "dimension": {
        "Justering": {
            "label": "type justering",
            "category": {
                "index": {"T": 0, "S": 1},
                "label": {"T": "Trend", "S": "Sesongjustert"},
            },
        },
        "ContentsCode": {
            "label": "statistikkvariabel",
            "category": {
                "index": {"Arbeidsstyrken": 0},
                "label": {"Arbeidsstyrken": "Arbeidsstyrken (1000 personer)"},
            },
        },
        "Tid": {
            "label": "måned",
            "category": {"index": {"2026M07": 0}, "label": {"2026M07": "2026M07"}},
        },
    },
    "value": [3067, 3074],
}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == LIST_URL:
            return CATALOG
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        if url == TABLE_13760_URL:
            return JsonResponse(status=200, url=url, body=DATA_13760)
        raise AssertionError(f"unexpected GET {url}")

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError(f"ssbv2 fetch must GET, not POST {url}")


def test_printed_refs_copy_id_and_data_href() -> None:
    source = Ssbv2Source(http=CatalogHttp())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["13760", "14483"]
    assert [ref.source_native_uri for ref in refs] == [TABLE_13760_URL, TABLE_14483_URL]
    assert all("outputFormat=json-stat2" in (ref.source_native_uri or "") for ref in refs)


def test_printed_tables_keep_document_order() -> None:
    listed = printed_tables(CATALOG)
    assert [item["id"] for item in listed] == ["13760", "14483"]
    assert printed_data_url(CATALOG["tables"][0]) == TABLE_13760_URL


def test_ssbv2_is_a_registered_source() -> None:
    assert "ssbv2" in SOURCE_IDS
    assert "ssb" in SOURCE_IDS
    source = build_source("ssbv2")
    assert isinstance(source, Ssbv2Source)
    assert source.source_id == "ssbv2"


def test_harvest_writes_printed_id_and_publisher(tmp_path: Path) -> None:
    source = Ssbv2Source(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "ssbv2"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == TABLE_13760_URL
    assert row["title"] == "13760: Arbeidsstyrken, sysselsatte, arbeidsledige"
    assert row["publisher_name"] == "Statistisk sentralbyrå"
    assert row["license"] is None
    assert not str(row["id"]).startswith("ssb:")
    nxt = registry.get_dataset("ssbv2:14483")
    assert nxt is not None
    assert nxt["access_path"] == TABLE_14483_URL
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["ssbv2_table"]["id"] == "13760"
    assert payload["ssbv2_table"]["data_url"] == TABLE_13760_URL
    assert payload["license"] is None
    enrichments = registry.conn.execute("SELECT COUNT(*) AS n FROM enrichments").fetchone()["n"]
    assert enrichments == 0
    registry.close()


def test_fetch_gets_printed_jsonstat_cells(tmp_path: Path) -> None:
    source = Ssbv2Source(http=CatalogHttp())
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        http=FetchHttp(),
    )
    assert result.request_url == TABLE_13760_URL
    assert result.table_id == "13760"
    assert result.http_status == 200
    assert result.counts.listed == 2
    rows = registry.list_observations(DATASET_ID)
    by_value = {json.loads(row["value_json"]): row for row in rows}
    assert set(by_value) == {3067, 3074}
    assert by_value[3067]["measure"] == "Arbeidsstyrken (1000 personer)"
    dims = json.loads(by_value[3067]["dimensions_json"])
    assert dims["Justering"] == "Trend"
    assert dims["Tid"] == "2026M07"
    assert all(row["publisher_name"] == "Statistisk sentralbyrå" for row in rows)
    assert all(row["license"] is None for row in rows)
    assert all(row["access_path"] == TABLE_13760_URL for row in rows)
    registry.close()


def test_cells_copy_jsonstat_or_catalog() -> None:
    cells = cells_from_ssbv2(DATA_13760)
    assert len(cells) == 2
    measure, value, dims = cells[0]
    assert measure == "Arbeidsstyrken (1000 personer)"
    assert value == 3067
    assert dims["Justering"] == "Trend"
    catalog = cells_from_ssbv2(CATALOG)
    assert catalog[0][0] == "label"
    assert catalog[0][1] == "13760: Arbeidsstyrken, sysselsatte, arbeidsledige"
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_ssbv2(None)
    with pytest.raises(ValueError, match="JSON-stat2"):
        cells_from_ssbv2({"title": "13760"})


def test_is_ssbv2_url_accepts_only_pxwebapi_v2() -> None:
    assert is_ssbv2_url(TABLE_13760_URL)
    assert is_ssbv2_url(LIST_URL)
    assert ssbv2_table_id(TABLE_13760_URL) == "13760"
    assert ssbv2_table_id(TABLE_14483_URL) == "14483"
    assert not is_ssbv2_url(SSB_V0_URL)
    assert not is_ssbv2_url("https://data.norge.no/datasets/x")
    assert not is_ssbv2_url(None)


def test_limit_and_offset_slice_printed_tables() -> None:
    source = Ssbv2Source(http=CatalogHttp(), max_items=10)
    assert [ref.source_native_id for ref in source.list_dataset_refs(limit=1)] == ["13760"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["14483"]
