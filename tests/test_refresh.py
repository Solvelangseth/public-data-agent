from __future__ import annotations

import json
from pathlib import Path

from public_data_agent.cli import main
from public_data_agent.harvest import harvest
from public_data_agent.registry import Registry
from public_data_agent.sources.fixture import FixtureSource

FIXTURES = Path(__file__).parent / "fixtures"


def _payloads() -> list[dict]:
    names = ("ssb-strandsone.json", "helsedata-ssb.json", "sparse.json")
    return [json.loads((FIXTURES / name).read_text(encoding="utf-8")) for name in names]


def test_second_run_upserts_without_wiping_and_skips_unchanged(tmp_path: Path) -> None:
    db = tmp_path / "registry.sqlite"
    payloads = _payloads()
    source = FixtureSource(payloads)
    registry = Registry(db)

    first = harvest(registry, source)
    assert first.listed == 3
    assert first.inserted == 3
    assert first.updated == 0
    assert first.unchanged == 0
    assert first.failed == 0
    assert registry.dataset_count() == 3

    first_id = "fixture:b2864e84-b474-31ae-97b1-8b94a71f5b0f"
    before = registry.get_dataset(first_id)
    assert before is not None
    original_payload = registry.get_payload(first_id)
    assert original_payload["title"]["no"] == "Potensielt tilgjengelig strandsone"
    assert "publisher_name" not in original_payload

    second = harvest(registry, source)
    assert second.listed == 3
    assert second.inserted == 0
    assert second.updated == 0
    assert second.unchanged == 3
    assert registry.dataset_count() == 3
    after = registry.get_dataset(first_id)
    assert after is not None
    assert after["payload_hash"] == before["payload_hash"]
    assert after["first_ingested_at"] == before["first_ingested_at"]
    assert after["last_seen_at"] >= before["last_seen_at"]

    runs = registry.list_runs()
    assert len(runs) == 2
    assert runs[0]["status"] == "completed"
    assert runs[1]["unchanged"] == 3
    registry.close()


def test_changed_payload_updates_row_and_leaves_others(tmp_path: Path) -> None:
    db = tmp_path / "registry.sqlite"
    payloads = _payloads()
    registry = Registry(db)
    harvest(registry, FixtureSource(payloads))

    changed = json.loads(json.dumps(payloads[0]))
    changed["title"]["en"] = "Potentially accessible coastal zone"
    changed["harvest"]["modified"] = "2026-08-01T00:00:00Z"
    harvest(registry, FixtureSource([changed, payloads[1], payloads[2]]))

    updated = registry.get_dataset("fixture:b2864e84-b474-31ae-97b1-8b94a71f5b0f")
    assert updated is not None
    assert updated["title"] == "Potensielt tilgjengelig strandsone"
    title_i18n = json.loads(updated["title_i18n_json"])
    assert title_i18n["en"] == "Potentially accessible coastal zone"
    stored = registry.get_payload("fixture:b2864e84-b474-31ae-97b1-8b94a71f5b0f")
    assert stored["title"]["en"] == "Potentially accessible coastal zone"

    untouched = registry.get_dataset("fixture:66c8fb46-da24-35a0-83b8-930cf175339d")
    assert untouched is not None
    assert untouched["title"] == "Data fra SSB"
    assert registry.dataset_count() == 3

    runs = registry.list_runs()
    assert runs[-1]["updated"] == 1
    assert runs[-1]["unchanged"] == 2
    assert runs[-1]["inserted"] == 0
    registry.close()


def test_partial_batch_failure_leaves_rows_for_resume(tmp_path: Path) -> None:
    payloads = _payloads()
    source = FixtureSource(payloads)

    class BoomOnSecondBatch(FixtureSource):
        def __init__(self) -> None:
            super().__init__(payloads)

        def fetch_dataset(self, ref):
            if ref.source_native_uri != payloads[0]["uri"]:
                raise RuntimeError("resource service dropped")
            return super().fetch_dataset(ref)

        def fetch_many(self, refs):
            refs = list(refs)
            if any(ref.source_native_uri != payloads[0]["uri"] for ref in refs):
                raise RuntimeError("resource service dropped")
            return super().fetch_many(refs)

    db = tmp_path / "registry.sqlite"
    registry = Registry(db)
    first = harvest(registry, BoomOnSecondBatch(), batch_size=1)
    assert first.inserted == 1
    assert first.failed == 2
    assert registry.dataset_count() == 1

    second = harvest(registry, source, batch_size=1)
    assert second.inserted == 2
    assert second.failed == 0
    assert registry.dataset_count() == 3
    registry.close()


def test_cli_fixture_ingest_writes_registry(tmp_path: Path) -> None:
    db = tmp_path / "registry.sqlite"
    code = main(["ingest", "--source", "fixture", "--fixtures", str(FIXTURES), "--db", str(db)])
    assert code == 0
    registry = Registry(db)
    assert registry.dataset_count() == 3
    sparse = registry.get_dataset("fixture:00000000-0000-4000-8000-000000000001")
    assert sparse is not None
    assert sparse["publisher_name"] is None
    missing = json.loads(sparse["missing_fields_json"])
    assert "publisher" in missing
    assert "license" in missing
    assert "access_path" in missing
    payload = registry.get_payload(sparse["id"])
    assert payload["publisher"] is None
    registry.close()
