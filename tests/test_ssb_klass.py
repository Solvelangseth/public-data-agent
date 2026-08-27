from __future__ import annotations

import json
from pathlib import Path

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources.fixture import FixtureSource
from public_data_agent.ssb_klass import cells_from_klass, is_klass_url, klass_table_id

FIXTURES = Path(__file__).parent / "fixtures"
STRANDSONE_ID = "fixture:b2864e84-b474-31ae-97b1-8b94a71f5b0f"
KLASS_URL = "https://data.ssb.no/api/klass/v1/versions/1168.json"

KLASS_PAYLOAD = {
    "name": "Bydelsinndeling 2020",
    "id": 1168,
    "classificationItems": [
        {"code": "030101", "name": "Gamle Oslo", "level": "1", "parentCode": ""},
        {"code": "030102", "name": "Grünerløkka", "level": "1", "parentCode": ""},
    ],
}


class KlassHttp:
    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        return JsonResponse(status=200, url=url, body=KLASS_PAYLOAD)

    def post_json_response(self, url: str, body, *, headers=None) -> JsonResponse:
        raise AssertionError("klass fetch must GET, not POST")


def _registry(tmp_path: Path) -> Registry:
    payloads = [
        json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        for name in ("ssb-strandsone.json", "helsedata-ssb.json", "sparse.json")
    ]
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FixtureSource(payloads))
    registry.conn.execute(
        "UPDATE datasets SET access_path = ? WHERE id = ?",
        (KLASS_URL, STRANDSONE_ID),
    )
    registry.conn.commit()
    return registry


def test_is_klass_url_accepts_only_ssb_klass() -> None:
    assert is_klass_url(KLASS_URL)
    assert not is_klass_url("https://statistikkbanken.oslo.kommune.no/statbank/api/v1/no/db1/")
    assert not is_klass_url("https://data.ssb.no/api/v0/no/table/07459")


def test_cells_from_klass_copy_source_names() -> None:
    cells = cells_from_klass(KLASS_PAYLOAD)
    assert cells == [
        ("Bydelsinndeling 2020", "Gamle Oslo", {"code": "030101", "level": "1"}),
        ("Bydelsinndeling 2020", "Grünerløkka", {"code": "030102", "level": "1"}),
    ]
    assert klass_table_id(KLASS_PAYLOAD, KLASS_URL) == "klass:1168"


def test_fetch_klass_stores_rows_and_second_run_is_unchanged(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    harvest_before = registry.conn.execute("SELECT COUNT(*) FROM harvested_payloads").fetchone()[0]
    first = fetch_observations(registry, STRANDSONE_ID, table_id="ignored", http=KlassHttp())
    assert first.http_status == 200
    assert first.request_url == KLASS_URL
    assert first.table_id == "klass:1168"
    assert first.counts.listed == 2
    assert first.counts.inserted == 2
    assert registry.observation_count() == 2
    assert registry.conn.execute("SELECT COUNT(*) FROM harvested_payloads").fetchone()[0] == harvest_before
    row = registry.list_observations(STRANDSONE_ID)[0]
    assert row["publisher_name"]
    assert row["request_url"] == KLASS_URL
    assert json.loads(row["value_json"]) in {"Gamle Oslo", "Grünerløkka"}
    second = fetch_observations(registry, STRANDSONE_ID, table_id="ignored", http=KlassHttp())
    assert second.counts.unchanged == 2
    assert second.counts.inserted == 0
    assert registry.observation_count() == 2
    registry.close()
