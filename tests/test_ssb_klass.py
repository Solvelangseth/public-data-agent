from __future__ import annotations

import json
from pathlib import Path

from public_data_agent.fetch import fetch_observations
from public_data_agent.harvest import harvest
from public_data_agent.http_util import JsonResponse
from public_data_agent.registry import Registry
from public_data_agent.sources.fixture import FixtureSource
from public_data_agent.ssb_klass import is_klass_url, klass_table_id, records_from_klass

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


def test_records_from_klass_make_the_code_the_subject() -> None:
    records = records_from_klass(KLASS_PAYLOAD, STRANDSONE_ID)
    assert records == [
        {
            "id": f"entity:{STRANDSONE_ID}:klass:1168:030101",
            "kind": "entity",
            "subject_scheme": "klass:1168",
            "subject_code": "030101",
            "subject_label": "Gamle Oslo",
            "attributes": {"classification": "Bydelsinndeling 2020", "level": "1"},
        },
        {
            "id": f"entity:{STRANDSONE_ID}:klass:1168:030102",
            "kind": "entity",
            "subject_scheme": "klass:1168",
            "subject_code": "030102",
            "subject_label": "Grünerløkka",
            "attributes": {"classification": "Bydelsinndeling 2020", "level": "1"},
        },
    ]
    assert klass_table_id(KLASS_PAYLOAD, KLASS_URL) == "klass:1168"


def test_records_from_klass_keep_the_parent_code_as_an_attribute() -> None:
    payload = {
        "name": "Kommuneinndeling 2026",
        "id": 3262,
        "classificationItems": [
            {"code": "0301", "name": "Oslo", "level": "2", "parentCode": "03"},
        ],
    }
    (record,) = records_from_klass(payload, STRANDSONE_ID)
    assert record["attributes"]["parentCode"] == "03"
    assert record["subject_code"] == "0301"


def test_fetch_klass_stores_entity_records_not_observations(tmp_path: Path) -> None:
    """A code list is a list of named things, and the count must say so.

    Stored as observation cells, 42 Oslo bydel names counted as 42 published
    measurements and the dataset verified as an observation source.
    """

    registry = _registry(tmp_path)
    harvest_before = registry.conn.execute("SELECT COUNT(*) FROM harvested_payloads").fetchone()[0]
    first = fetch_observations(registry, STRANDSONE_ID, table_id="ignored", http=KlassHttp())
    assert first.http_status == 200
    assert first.request_url == KLASS_URL
    assert first.table_id == "klass:1168"
    assert first.counts.listed == 2
    assert first.counts.inserted == 2
    assert registry.observation_count() == 0
    assert registry.conn.execute("SELECT COUNT(*) FROM harvested_payloads").fetchone()[0] == harvest_before
    records = registry.list_records(STRANDSONE_ID)
    assert {row["kind"] for row in records} == {"entity"}
    assert {row["subject_code"] for row in records} == {"030101", "030102"}
    assert {row["subject_label"] for row in records} == {"Gamle Oslo", "Grünerløkka"}
    assert all(row["value_json"] is None for row in records)
    assert all(row["publisher_name"] for row in records)
    assert all(row["request_url"] == KLASS_URL for row in records)
    second = fetch_observations(registry, STRANDSONE_ID, table_id="ignored", http=KlassHttp())
    assert second.counts.unchanged == 2
    assert second.counts.inserted == 0
    assert len(registry.list_records(STRANDSONE_ID)) == 2
    registry.close()
