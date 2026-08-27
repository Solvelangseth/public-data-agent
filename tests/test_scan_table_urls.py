from __future__ import annotations

import json
from pathlib import Path

from public_data_agent.cli import main
from public_data_agent.harvest import harvest
from public_data_agent.registry import Registry
from public_data_agent.scan_table_urls import (
    classify_table_url,
    extract_printed_table_urls,
    scan_printed_table_urls,
)
from public_data_agent.sources.fixture import FixtureSource

TABLE_URL = "https://data.ssb.no/api/v0/no/table/12345"
KLASS_URL = "https://data.ssb.no/api/klass/v1/versions/1168.json"
CSV_URL = "https://example.org/file.csv"


def _payload_with_extra_table() -> dict:
    return {
        "id": "11111111-1111-4111-8111-111111111111",
        "uri": "https://example.org/datasets/with-table",
        "type": "datasets",
        "title": {"en": "Fixture with a printed table URL"},
        "description": {"en": "Second distribution prints a PxWeb table."},
        "publisher": None,
        "distribution": [
            {
                "downloadURL": [CSV_URL],
                "accessURL": [CSV_URL],
            },
            {
                "accessURL": [TABLE_URL],
            },
        ],
        "landingPage": None,
        "issued": None,
        "modified": None,
        "temporal": None,
        "spatial": None,
        "conformsTo": None,
        "accessRights": None,
        "harvest": {
            "modified": "2026-01-01T00:00:00Z",
            "firstHarvested": "2026-01-01T00:00:00Z",
        },
    }


def test_classify_copies_printed_table_and_rejects_klass() -> None:
    assert classify_table_url(TABLE_URL) == "ssb_pxweb_table"
    assert classify_table_url(KLASS_URL) is None
    assert classify_table_url("https://www.ssb.no/statbank/") is None
    assert (
        classify_table_url(
            "https://statistikkbanken.oslo.kommune.no/statbank/api/v1/no/db1/OK-BEF008.px"
        )
        == "pxweb_api_table"
    )


def test_extract_skips_access_path_and_does_not_invent_07459() -> None:
    printed, skipped = extract_printed_table_urls(
        dataset_id="fixture:x",
        access_path=TABLE_URL,
        payload_json=json.dumps({"distribution": [{"accessURL": [TABLE_URL, KLASS_URL]}]}),
        distributions_json=None,
        landing_pages_json=None,
    )
    assert skipped == 1
    assert len(printed) == 1
    assert printed[0].already_access_path is True
    assert "07459" not in json.dumps([item.url for item in printed])


def test_scan_persists_new_url_and_leaves_harvest_bytes(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FixtureSource([_payload_with_extra_table()]))
    dataset_id = "fixture:11111111-1111-4111-8111-111111111111"
    row = registry.get_dataset(dataset_id)
    assert row is not None
    assert row["access_path"] == CSV_URL
    before = registry.conn.execute(
        "SELECT dataset_id, payload_json FROM harvested_payloads ORDER BY dataset_id"
    ).fetchall()
    access_before = row["access_path"]
    first = scan_printed_table_urls(registry, probe=False)
    assert first.counts.inserted == 1
    assert first.new_urls[0].url == TABLE_URL
    stored = registry.list_printed_table_urls(dataset_id)
    assert [item["url"] for item in stored] == [TABLE_URL]
    after = registry.conn.execute(
        "SELECT dataset_id, payload_json FROM harvested_payloads ORDER BY dataset_id"
    ).fetchall()
    assert after == before
    assert registry.get_dataset(dataset_id)["access_path"] == access_before
    second = scan_printed_table_urls(registry, probe=False)
    assert second.counts.inserted == 0
    assert second.counts.unchanged == 1
    registry.close()


def test_cli_scan_writes_proof_on_empty_harvest(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(
        registry,
        FixtureSource(
            [
                {
                    "id": "00000000-0000-4000-8000-000000000001",
                    "uri": "https://example.org/datasets/sparse",
                    "type": "datasets",
                    "title": {"en": "Sparse fixture"},
                    "description": None,
                    "publisher": None,
                    "distribution": None,
                    "landingPage": None,
                    "issued": None,
                    "modified": None,
                    "temporal": None,
                    "spatial": None,
                    "conformsTo": None,
                    "accessRights": None,
                    "harvest": {
                        "modified": "2026-01-01T00:00:00Z",
                        "firstHarvested": "2026-01-01T00:00:00Z",
                    },
                }
            ]
        ),
    )
    registry.close()
    out = tmp_path / "proof.json"
    assert (
        main(
            [
                "scan-table-urls",
                "--db",
                str(tmp_path / "registry.sqlite"),
                "--out",
                str(out),
                "--no-probe",
            ]
        )
        == 0
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["new_stored"] == 0
    assert payload["sit"] is True
    assert payload["constructed_07459"] is False
