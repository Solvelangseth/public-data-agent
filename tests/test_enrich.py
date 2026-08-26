from __future__ import annotations

import json
from pathlib import Path

from public_data_agent.cli import main
from public_data_agent.enrich import enrich
from public_data_agent.harvest import harvest
from public_data_agent.registry import Registry
from public_data_agent.sources.fixture import FixtureSource

FIXTURES = Path(__file__).parent / "fixtures"
STRANDSONE_ID = "fixture:b2864e84-b474-31ae-97b1-8b94a71f5b0f"
SPARSE_ID = "fixture:00000000-0000-4000-8000-000000000001"


def _registry(tmp_path: Path) -> Registry:
    payloads = [
        json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        for name in ("ssb-strandsone.json", "helsedata-ssb.json", "sparse.json")
    ]
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FixtureSource(payloads))
    return registry


def _harvest_bytes(registry: Registry) -> list[tuple[str, str | None, str | None, str]]:
    rows = registry.conn.execute(
        """
        SELECT d.id, d.publisher_name, d.license, p.payload_json
        FROM datasets d
        JOIN harvested_payloads p ON p.dataset_id = d.id
        ORDER BY d.id
        """
    ).fetchall()
    return [(row["id"], row["publisher_name"], row["license"], row["payload_json"]) for row in rows]


def test_enrich_leaves_harvest_payload_and_columns_byte_identical(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    before = _harvest_bytes(registry)
    assert before
    first = enrich(registry)
    assert first.listed == 3
    assert first.inserted == 3
    assert first.failed == 0
    assert _harvest_bytes(registry) == before
    registry.close()


def test_second_enrich_is_unchanged_and_does_not_duplicate(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    first = enrich(registry)
    assert first.inserted == 3
    second = enrich(registry)
    assert second.unchanged == 3
    assert second.inserted == 0
    assert second.updated == 0
    assert registry.enrichment_count() == 3
    registry.close()


def test_sparse_row_records_missing_geography_time_fields(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    enrich(registry)
    row = registry.get_enrichment(SPARSE_ID)
    assert row is not None
    assert row["source"] == "system"
    assert row["method"] == "deterministic_from_stored_metadata"
    assert row["geography_json"] is None
    assert row["time_coverage_json"] is None
    assert row["fields_json"] is None
    missing = json.loads(row["missing_json"])
    assert "geography" in missing
    assert "time_coverage" in missing
    assert "fields" in missing
    assert missing["geography"]
    assert missing["time_coverage"]
    assert missing["fields"]
    registry.close()


def test_strandsone_topics_and_time_coverage_come_from_stored_harvest(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    enrich(registry)
    row = registry.get_enrichment(STRANDSONE_ID)
    assert row is not None
    topics = json.loads(row["topics_json"])
    assert "HEAL" in topics
    assert "Health" in topics
    assert "Helse" in topics
    assert "Friluftsliv" in topics
    assert "Strandsone" in topics
    coverage = json.loads(row["time_coverage_json"])
    assert coverage["issued"] == "2014-07-04"
    assert coverage["modified"] == "2014-07-04"
    assert coverage["temporal"][0]["start"] == "2014-01-01T00:00:00Z"
    registry.close()


def test_cli_enrich_uses_fixture_registry(tmp_path: Path, capsys) -> None:
    db = tmp_path / "registry.sqlite"
    assert main(["ingest", "--source", "fixture", "--fixtures", str(FIXTURES), "--db", str(db), "--quiet"]) == 0
    capsys.readouterr()
    assert main(["enrich", "--db", str(db), "--quiet"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["listed"] == 3
    assert payload["inserted"] == 3
    assert payload["updated"] == 0
    assert payload["unchanged"] == 0
    assert payload["failed"] == 0
    registry = Registry(db)
    assert registry.enrichment_count() == 3
    registry.close()
