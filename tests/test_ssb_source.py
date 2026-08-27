from __future__ import annotations

import json
from pathlib import Path

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources import SOURCE_IDS, build_source
from public_data_agent.sources.ssb import SsbStatbankSource, printed_table_id

TABLE_URL = "https://data.ssb.no/api/v0/no/table/06683"
META = {
    "title": "06683: Adopsjoner, etter adopsjonstype, statistikkvariabel og år",
    "variables": [
        {
            "code": "Adopsjonstype",
            "text": "adopsjonstype",
            "values": ["00", "01"],
            "valueTexts": ["Utenlandsadopsjoner", "Stebarn"],
        },
        {
            "code": "ContentsCode",
            "text": "statistikkvariabel",
            "values": ["Adopsjoner"],
            "valueTexts": ["Adopsjoner"],
        },
        {
            "code": "Tid",
            "text": "år",
            "values": ["2023", "2024"],
            "valueTexts": ["2023", "2024"],
            "time": True,
        },
    ],
}
JSONSTAT = {
    "label": "06683",
    "id": ["Adopsjonstype", "ContentsCode", "Tid"],
    "size": [2, 1, 2],
    "value": [100, 110, 20, 22],
    "role": {"metric": ["ContentsCode"], "time": ["Tid"]},
    "dimension": {
        "Adopsjonstype": {
            "category": {
                "index": {"00": 0, "01": 1},
                "label": {"00": "Utenlandsadopsjoner", "01": "Stebarn"},
            }
        },
        "ContentsCode": {
            "category": {
                "index": {"Adopsjoner": 0},
                "label": {"Adopsjoner": "Adopsjoner"},
            }
        },
        "Tid": {
            "category": {
                "index": {"2023": 0, "2024": 1},
                "label": {"2023": "2023", "2024": "2024"},
            }
        },
    },
}


class CatalogHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []

    def get_json(self, url: str, *, headers=None):
        self.gets.append(url)
        if url.endswith("/table/be"):
            return [{"id": "be01", "type": "l", "text": "Folkemengde"}]
        if url.endswith("/be01"):
            return [
                {
                    "id": "Adopsjoner01",
                    "type": "t",
                    "text": "06683: Adopsjoner, etter adopsjonstype 1986 - 2024",
                    "updated": "2025-09-23T08:00:00",
                },
                {
                    "id": "Other",
                    "type": "t",
                    "text": "07277: Adopsjoner, etter adopsjonstype (F) 2006 - 2024",
                    "updated": "2025-09-23T08:00:00",
                },
            ]
        if url == TABLE_URL:
            return META
        if url.endswith("/table/07277"):
            return {"title": "07277: other", "variables": []}
        raise AssertionError(f"unexpected GET {url}")


class FetchHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        assert url == TABLE_URL
        return JsonResponse(status=200, url=url, body=META)

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        assert url == TABLE_URL
        return JsonResponse(status=200, url=url, body=JSONSTAT)


def test_printed_table_id_copies_leading_number() -> None:
    assert printed_table_id({"id": "Adopsjoner01", "text": "06683: Adopsjoner"}) == "06683"
    assert printed_table_id({"id": "slug", "text": "no number"}) == "slug"


def test_ssb_is_a_registered_source() -> None:
    assert "ssb" in SOURCE_IDS
    source = build_source("ssb")
    assert isinstance(source, SsbStatbankSource)
    assert source.source_id == "ssb"


def test_ssb_lists_capped_printed_tables_and_harvests_access_path(tmp_path: Path) -> None:
    source = SsbStatbankSource(http=CatalogHttp(), max_tables=1)
    refs = source.list_dataset_refs()
    assert len(refs) == 1
    assert refs[0].source_native_id == "06683"
    assert refs[0].source_native_uri == TABLE_URL
    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, source)
    assert counts.inserted == 1
    row = registry.get_dataset("ssb:06683")
    assert row is not None
    assert row["source_id"] == "ssb"
    assert row["access_path"] == TABLE_URL
    assert row["license"] is None
    assert "07459" not in (row["access_path"] or "")
    payload = json.loads(
        registry.conn.execute(
            "SELECT payload_json FROM harvested_payloads WHERE dataset_id = ?",
            ("ssb:06683",),
        ).fetchone()["payload_json"]
    )
    assert payload["ssb_table_metadata"]["title"].startswith("06683")
    registry.close()


def test_fetch_uses_printed_ssb_table_url(tmp_path: Path) -> None:
    source = SsbStatbankSource(http=CatalogHttp(), max_tables=1)
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, source)
    result = fetch_observations(
        registry,
        "ssb:06683",
        table_id="ignored",
        from_year=2023,
        to_year=2024,
        http=FetchHttp(),
    )
    assert result.request_url == TABLE_URL
    assert result.table_id == "06683"
    assert result.http_status == 200
    assert result.counts.listed == 4
    values = [json.loads(row["value_json"]) for row in registry.list_observations("ssb:06683")]
    assert sorted(values) == [20, 22, 100, 110]
    registry.close()
