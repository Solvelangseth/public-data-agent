from __future__ import annotations

import json

from public_data_agent.brreg_sync import MIRRORS, MirrorResult
from public_data_agent.cli import main
from public_data_agent.models import HarvestCounts


def test_mirror_brreg_snapshot_command_prints_scheduler_friendly_result(
    tmp_path, monkeypatch, capsys
) -> None:
    called = {}

    def fake_snapshot(registry, kind, **options):
        called.update(kind=kind, **options)
        return MirrorResult(
            pipeline_id=MIRRORS[kind].pipeline_id,
            dataset_id=MIRRORS[kind].dataset_id,
            request_url=MIRRORS[kind].snapshot_url,
            status="sampled",
            counts=HarvestCounts(listed=2, inserted=2),
            sha256="abc",
            storage_path=str(options["storage_dir"] / "enheter-1.csv.gz"),
        )

    monkeypatch.setattr("public_data_agent.cli.sync_snapshot", fake_snapshot)
    db = tmp_path / "registry.sqlite"
    raw = tmp_path / "raw"
    assert main([
        "mirror-brreg", "enheter", "snapshot", "--db", str(db),
        "--storage-dir", str(raw), "--limit", "2",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["phase"] == "snapshot"
    assert payload["listed"] == 2
    assert payload["storage_path"].endswith("enheter-1.csv.gz")
    assert called == {
        "kind": "enheter",
        "storage_dir": raw,
        "limit": 2,
        "batch_size": 1000,
        "force": False,
    }


def test_mirror_brreg_updates_command_passes_durable_event_limit(
    tmp_path, monkeypatch, capsys
) -> None:
    called = {}

    def fake_updates(registry, kind, **options):
        called.update(kind=kind, **options)
        return MirrorResult(
            pipeline_id=MIRRORS[kind].pipeline_id,
            dataset_id=MIRRORS[kind].dataset_id,
            request_url=MIRRORS[kind].update_url,
            status="completed",
            counts=HarvestCounts(listed=3, updated=3),
            cursor="123",
        )

    monkeypatch.setattr("public_data_agent.cli.sync_updates", fake_updates)
    db = tmp_path / "registry.sqlite"
    assert main([
        "mirror-brreg", "underenheter", "updates", "--db", str(db),
        "--limit", "3", "--batch-size", "50",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["cursor"] == "123"
    assert called == {
        "kind": "underenheter",
        "batch_size": 50,
        "max_events": 3,
    }
