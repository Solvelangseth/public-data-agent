from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.oslo import (
    OsloStatbankSource,
    is_oslo_statbank_url,
    join_catalog_url,
    oslo_table_id,
    printed_table_id,
)

API_ROOT = "https://statistikkbanken.oslo.kommune.no/statbank/api/v1/no"
BEFOLKNING_URL = f"{API_ROOT}/db1/Befolkning"
FOLKEMENGDE_URL = f"{API_ROOT}/db1/Befolkning/Folkemengde"
FOEDTE_URL = (
    f"{API_ROOT}/db1/Befolkning/"
    "F%C3%B8dte%2C%20d%C3%B8de%20og%20forventet%20levealder"
)
TABLE_URL = f"{FOLKEMENGDE_URL}/OK-BEF008.px"
BEF001_URL = f"{FOLKEMENGDE_URL}/OK-BEF001.px"
DATASET_ID = "oslo:OK-BEF008.px"

META = {
    "title": "BEF008: Folkemengden i Oslo/Kristiania, antall personer og årlig endring, 1801-2026",
    "variables": [
        {
            "code": "geografisk område",
            "text": "geografisk område",
            "values": ["0"],
            "valueTexts": ["Oslo (Kristiania og Aker) i alt"],
        },
        {
            "code": "statistikkvariabel",
            "text": "statistikkvariabel",
            "values": ["Folkemengden i alt (antall personer)"],
            "valueTexts": ["Folkemengden i alt (antall personer)"],
        },
        {
            "code": "år",
            "text": "år",
            "values": ["2024", "2025"],
            "valueTexts": ["2024", "2025"],
            "time": True,
        },
    ],
}
JSONSTAT = {
    "label": "BEF008",
    "id": ["statistikkvariabel", "geografisk område", "år"],
    "size": [1, 1, 2],
    "value": [717710, 724290],
    "role": {"metric": ["statistikkvariabel"], "time": ["år"]},
    "dimension": {
        "statistikkvariabel": {
            "category": {
                "index": {"Folkemengden i alt (antall personer)": 0},
                "label": {
                    "Folkemengden i alt (antall personer)": (
                        "Folkemengden i alt (antall personer)"
                    )
                },
            }
        },
        "geografisk område": {
            "category": {
                "index": {"0": 0},
                "label": {"0": "Oslo (Kristiania og Aker) i alt"},
            }
        },
        "år": {
            "category": {
                "index": {"2024": 0, "2025": 1},
                "label": {"2024": "2024", "2025": "2025"},
            }
        },
    },
}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url == BEFOLKNING_URL:
            return [
                {"id": "Folkemengde", "type": "l", "text": "Folkemengde"},
                {
                    "id": "Fødte, døde og forventet levealder",
                    "type": "l",
                    "text": "Fødte, døde og forventet levealder",
                },
            ]
        if url == FOLKEMENGDE_URL:
            return [
                {
                    "id": "OK-BEF001.px",
                    "type": "t",
                    "text": "BEF001: Folkemengden etter kjønn og alder (B), 1990-2026",
                    "updated": "2026-02-26T08:00:00",
                },
                {
                    "id": "OK-BEF008.px",
                    "type": "t",
                    "text": "BEF008: Folkemengden i Oslo/Kristiania, 1801-2026",
                    "updated": "2026-02-26T08:00:00",
                },
            ]
        if url == FOEDTE_URL:
            return [
                {
                    "id": "OK-BEF010.px",
                    "type": "t",
                    "text": "BEF010: Antall fødte barn etter bosted (GO), 2017-2025",
                }
            ]
        if url == TABLE_URL:
            return META
        if url == BEF001_URL:
            return {"title": "BEF001: Folkemengden", "variables": []}
        if url.endswith("/OK-BEF010.px"):
            return {"title": "BEF010: Fødte", "variables": []}
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        assert url == TABLE_URL
        return JsonResponse(status=200, url=url, body=META)

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        assert url == TABLE_URL
        return JsonResponse(status=200, url=url, body=JSONSTAT)


def test_printed_table_id_copies_printed_id() -> None:
    assert printed_table_id({"id": "OK-BEF008.px", "text": "BEF008: Folkemengden"}) == "OK-BEF008.px"
    with pytest.raises(Exception, match="printed table id"):
        printed_table_id({"text": "BEF008: Folkemengden"})


def test_join_catalog_url_quotes_printed_spaces() -> None:
    url = join_catalog_url(BEFOLKNING_URL, "Fødte, døde og forventet levealder")
    assert url == FOEDTE_URL
    assert " " not in url


def test_oslo_is_a_registered_source() -> None:
    assert "oslo" in SOURCE_IDS
    source = build_source("oslo")
    assert isinstance(source, OsloStatbankSource)
    assert source.source_id == "oslo"


def test_limit_and_offset_slice_printed_tables() -> None:
    source = OsloStatbankSource(http=CatalogHttp(), max_tables=10)
    first = source.list_dataset_refs(limit=1)
    assert [ref.source_native_id for ref in first] == ["OK-BEF001.px"]
    nxt = source.list_dataset_refs(limit=1, offset=1)
    assert [ref.source_native_id for ref in nxt] == ["OK-BEF008.px"]
    assert nxt[0].source_native_uri == TABLE_URL


def test_harvest_writes_printed_id_and_null_license(tmp_path: Path) -> None:
    source = OsloStatbankSource(http=CatalogHttp(), max_tables=2)
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 2
    row = registry.get_dataset(DATASET_ID)
    assert row is not None
    assert row["source_id"] == "oslo"
    assert row["id"] == DATASET_ID
    assert row["access_path"] == TABLE_URL
    assert row["title"].startswith("BEF008")
    assert row["publisher_name"] is None
    assert row["license"] is None
    assert not str(row["id"]).startswith("datanorge:")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            (DATASET_ID,),
        ).fetchone()["payload_json"]
    )
    assert payload["oslo_table_metadata"]["title"].startswith("BEF008")
    assert payload["license"] is None
    assert payload["publisher"] is None
    registry.close()


def test_fetch_posts_printed_oslo_table_url(tmp_path: Path) -> None:
    source = OsloStatbankSource(http=CatalogHttp(), max_tables=2)
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        DATASET_ID,
        table_id="ignored",
        from_year=2024,
        to_year=2025,
        http=FetchHttp(),
    )
    assert result.request_url == TABLE_URL
    assert result.table_id == "OK-BEF008.px"
    assert result.http_status == 200
    assert result.counts.listed == 2
    values = [json.loads(row["value_json"]) for row in registry.list_observations(DATASET_ID)]
    assert sorted(values) == [717710, 724290]
    assert all(row["publisher_name"] is None for row in registry.list_observations(DATASET_ID))
    assert all(row["license"] is None for row in registry.list_observations(DATASET_ID))
    assert all(row["access_path"] == TABLE_URL for row in registry.list_observations(DATASET_ID))
    cap = registry.get_capability(DATASET_ID)
    assert cap["capability"] == "observations"
    registry.close()


def test_is_oslo_statbank_url_accepts_only_oslo_pxweb_api() -> None:
    assert is_oslo_statbank_url(TABLE_URL)
    assert is_oslo_statbank_url(FOLKEMENGDE_URL)
    assert oslo_table_id(TABLE_URL) == "OK-BEF008.px"
    assert not is_oslo_statbank_url(
        "https://statistikkbanken.oslo.kommune.no/statbank/pxweb/no/db1/"
    )
    assert not is_oslo_statbank_url("https://data.ssb.no/api/v0/no/table/06683")
    assert not is_oslo_statbank_url("https://data.norge.no/datasets/x")
    assert not is_oslo_statbank_url(None)
