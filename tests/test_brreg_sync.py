from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from public_data_agent.brreg_sync import (
    BRREG_LICENSE,
    MIRRORS,
    brreg_time_to_iso,
    sync_snapshot,
    sync_updates,
)
from public_data_agent.http_util import FileResponse, JsonResponse
from public_data_agent.registry import Registry


CSV = """organisasjonsnummer,navn,organisasjonsform.kode,forretningsadresse.kommunenummer,konkurs
923609016,EQUINOR ASA,ASA,1103,false
933365573,- ZOTKO .NO,ENK,0301,false
"""


class SnapshotHttp:
    def __init__(self, source: Path, *, etag: str = "snapshot-v1") -> None:
        self.source = source
        self.etag = etag
        self.heads: list[str] = []
        self.downloads: list[tuple[str, dict[str, str] | None]] = []

    def head(self, url: str, *, headers=None) -> FileResponse:
        self.heads.append(url)
        return FileResponse(
            status=200,
            url=url,
            headers={
                "etag": self.etag,
                "last-modified": "Tue Sep 08 04:26:53 CEST 2026",
                "content-type": "application/vnd.brreg.enhet.v2+gzip",
                "content-length": str(self.source.stat().st_size),
            },
        )

    def download(
        self,
        url: str,
        destination: Path,
        *,
        headers=None,
        chunk_size: int = 1024 * 1024,
    ) -> FileResponse:
        self.downloads.append((url, headers))
        data = self.source.read_bytes()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return FileResponse(
            status=200,
            url=url,
            headers={"etag": self.etag},
            path=destination,
            sha256=hashlib.sha256(data).hexdigest(),
            bytes_written=len(data),
        )


class UpdateHttp:
    def __init__(self, pages: list[list[dict]], items: dict[str, dict]) -> None:
        self.pages = list(pages)
        self.items = items
        self.gets: list[str] = []

    def get_json_response(self, url: str, *, headers=None) -> JsonResponse:
        self.gets.append(url)
        if "/oppdateringer/" in url:
            events = self.pages.pop(0) if self.pages else []
            return JsonResponse(
                status=200,
                url=url,
                body={"_embedded": {"oppdaterteEnheter": events}} if events else {},
            )
        if url in self.items:
            return JsonResponse(status=200, url=url, body=self.items[url])
        raise AssertionError(f"unexpected GET {url}")


def _snapshot(tmp_path: Path, text: str = CSV) -> Path:
    path = tmp_path / "source.csv.gz"
    with gzip.open(path, "wt", encoding="utf-8", newline="") as output:
        output.write(text)
    return path


def test_complete_snapshot_streams_entities_and_records_checkpoint(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    http = SnapshotHttp(_snapshot(tmp_path))
    result = sync_snapshot(
        registry,
        "enheter",
        storage_dir=tmp_path / "raw",
        http=http,
        batch_size=1,
    )
    assert result.status == "completed"
    assert result.counts.listed == 2
    assert result.counts.inserted == 2
    assert result.counts.failed == 0
    rows = registry.list_records(MIRRORS["enheter"].dataset_id)
    assert {row["subject_code"] for row in rows} == {"923609016", "933365573"}
    equinor = next(row for row in rows if row["subject_code"] == "923609016")
    assert equinor["kind"] == "entity"
    assert equinor["subject_scheme"] == "brreg:orgnr"
    assert equinor["subject_label"] == "EQUINOR ASA"
    assert equinor["request_url"] == MIRRORS["enheter"].snapshot_url
    assert equinor["license"] == BRREG_LICENSE
    assert registry.list_observations(MIRRORS["enheter"].dataset_id) == []

    checkpoint = registry.get_crawl_checkpoint(MIRRORS["enheter"].pipeline_id)
    assert checkpoint is not None
    assert checkpoint["etag"] == "snapshot-v1"
    assert checkpoint["snapshot_sha256"] == result.sha256
    assert checkpoint["extra"]["records"] == 2
    assert Path(checkpoint["snapshot_path"]).exists()
    manifests = registry.list_raw_snapshots(MIRRORS["enheter"].pipeline_id)
    assert manifests[0]["status"] == "completed"
    assert manifests[0]["records_seen"] == 2
    assert manifests[0]["sha256"] == result.sha256
    capability = registry.get_capability(MIRRORS["enheter"].dataset_id)
    assert capability["capability"] == "entities"
    assert capability["verified_sample_count"] == 2
    fields = {field["field_code"] for field in registry.resource_fields(
        MIRRORS["enheter"].dataset_id
    )}
    assert "organisasjonsnummer" in fields
    assert "forretningsadresse.kommunenummer" in fields
    assert registry.datasets_with_key("brreg:orgnr")[0]["coverage_count"] == 2
    registry.close()


def test_unchanged_etag_skips_download_and_reingest(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    http = SnapshotHttp(_snapshot(tmp_path))
    sync_snapshot(registry, "enheter", storage_dir=tmp_path / "raw", http=http)
    result = sync_snapshot(registry, "enheter", storage_dir=tmp_path / "raw", http=http)
    assert result.status == "unchanged"
    assert len(http.downloads) == 1
    assert registry.record_count(MIRRORS["enheter"].dataset_id) == 2
    assert len(registry.list_raw_snapshots(MIRRORS["enheter"].pipeline_id)) == 1
    registry.close()


def test_changed_snapshot_conditions_get_on_previous_not_new_etag(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    source = _snapshot(tmp_path)
    sync_snapshot(registry, "enheter", storage_dir=tmp_path / "raw", http=SnapshotHttp(source))
    changed = SnapshotHttp(source, etag="snapshot-v2")
    sync_snapshot(registry, "enheter", storage_dir=tmp_path / "raw", http=changed)
    assert changed.downloads[0][1] == {"If-None-Match": "snapshot-v1"}
    assert registry.get_crawl_checkpoint(MIRRORS["enheter"].pipeline_id)["etag"] == (
        "snapshot-v2"
    )
    assert registry.get_crawl_checkpoint(MIRRORS["enheter"].pipeline_id)["cursor"] is None
    registry.close()


def test_limited_snapshot_is_verified_but_never_advances_checkpoint(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    result = sync_snapshot(
        registry,
        "underenheter",
        storage_dir=tmp_path / "raw",
        http=SnapshotHttp(_snapshot(tmp_path)),
        limit=1,
    )
    assert result.status == "sampled"
    assert result.counts.listed == 1
    assert registry.get_crawl_checkpoint(MIRRORS["underenheter"].pipeline_id) is None
    assert registry.list_raw_snapshots()[0]["status"] == "sampled"
    registry.close()


def test_invalid_orgnr_fails_snapshot_without_claiming_checkpoint(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    bad = _snapshot(tmp_path, "organisasjonsnummer,navn\n123456789,NOPE\n")
    with pytest.raises(ValueError, match="invalid organisasjonsnummer"):
        sync_snapshot(
            registry,
            "enheter",
            storage_dir=tmp_path / "raw",
            http=SnapshotHttp(bad),
        )
    assert registry.get_crawl_checkpoint(MIRRORS["enheter"].pipeline_id) is None
    assert registry.record_count(MIRRORS["enheter"].dataset_id) == 0
    assert registry.list_raw_snapshots()[0]["status"] == "failed"
    registry.close()


def test_tombstone_removes_current_record_but_preserves_deletion_provenance(
    tmp_path: Path,
) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    source = _snapshot(tmp_path)
    sync_snapshot(registry, "enheter", storage_dir=tmp_path / "raw", http=SnapshotHttp(source))
    dataset_id = MIRRORS["enheter"].dataset_id
    removed = registry.tombstone_record(
        dataset_id=dataset_id,
        kind="entity",
        subject_scheme="brreg:orgnr",
        subject_code="923609016",
        reason="Fjernet",
        event_id="25175424",
        request_url=MIRRORS["enheter"].update_url,
        retrieved_at="2026-09-08T16:00:00Z",
    )
    assert removed is True
    assert registry.list_records(dataset_id, subject_code="923609016") == []
    tombstone = registry.list_record_tombstones(dataset_id)[0]
    assert tombstone["reason"] == "Fjernet"
    assert tombstone["event_id"] == "25175424"
    assert "EQUINOR ASA" in tombstone["previous_record_json"]

    # Reappearing in a later complete snapshot restores the current entity and
    # clears the stale tombstone under the same stable identity.
    sync_snapshot(
        registry,
        "enheter",
        storage_dir=tmp_path / "raw",
        http=SnapshotHttp(source, etag="snapshot-v2"),
    )
    assert registry.list_records(dataset_id, subject_code="923609016")
    assert registry.list_record_tombstones(dataset_id) == []
    registry.close()


def test_complete_snapshot_tombstones_entities_absent_from_replacement(
    tmp_path: Path,
) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    sync_snapshot(
        registry,
        "enheter",
        storage_dir=tmp_path / "raw",
        http=SnapshotHttp(_snapshot(tmp_path)),
    )
    replacement = _snapshot(
        tmp_path,
        "organisasjonsnummer,navn,konkurs\n923609016,EQUINOR ASA,false\n",
    )
    result = sync_snapshot(
        registry,
        "enheter",
        storage_dir=tmp_path / "raw",
        http=SnapshotHttp(replacement, etag="snapshot-v2"),
    )
    assert result.tombstoned == 1
    assert registry.record_count(MIRRORS["enheter"].dataset_id) == 1
    tombstone = registry.list_record_tombstones(MIRRORS["enheter"].dataset_id)[0]
    assert tombstone["subject_code"] == "933365573"
    assert tombstone["reason"] == "absent_from_complete_snapshot"
    registry.close()


def test_failed_replacement_snapshot_rolls_back_all_record_changes(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    sync_snapshot(
        registry,
        "enheter",
        storage_dir=tmp_path / "raw",
        http=SnapshotHttp(_snapshot(tmp_path)),
    )
    corrupt = _snapshot(
        tmp_path,
        "organisasjonsnummer,navn\n923609016,CHANGED TOO EARLY\n123456789,NOPE\n",
    )
    with pytest.raises(ValueError, match="invalid organisasjonsnummer"):
        sync_snapshot(
            registry,
            "enheter",
            storage_dir=tmp_path / "raw",
            http=SnapshotHttp(corrupt, etag="snapshot-v2"),
            batch_size=1,
        )
    stored = registry.list_records(
        MIRRORS["enheter"].dataset_id, subject_code="923609016"
    )[0]
    assert stored["subject_label"] == "EQUINOR ASA"
    checkpoint = registry.get_crawl_checkpoint(MIRRORS["enheter"].pipeline_id)
    assert checkpoint["etag"] == "snapshot-v1"
    assert registry.list_raw_snapshots()[-1]["status"] == "failed"
    registry.close()


def _event(event_id: int, orgnr: str, change: str) -> dict:
    return {
        "oppdateringsid": event_id,
        "dato": f"2026-09-08T16:00:{event_id % 60:02d}.000Z",
        "organisasjonsnummer": orgnr,
        "endringstype": change,
        "_links": {
            "enhet": {"href": MIRRORS["enheter"].item_prefix + orgnr}
        },
    }


def test_updates_refetch_entities_tombstone_deletions_and_advance_cursor(
    tmp_path: Path,
) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    sync_snapshot(
        registry,
        "enheter",
        storage_dir=tmp_path / "raw",
        http=SnapshotHttp(_snapshot(tmp_path)),
    )
    equinor_url = MIRRORS["enheter"].item_prefix + "923609016"
    http = UpdateHttp(
        pages=[
            [
                _event(100, "923609016", "Endring"),
                _event(101, "933365573", "Fjernet"),
            ],
            [],
        ],
        items={
            equinor_url: {
                "organisasjonsnummer": "923609016",
                "navn": "EQUINOR ASA",
                "antallAnsatte": 22000,
            }
        },
    )
    result = sync_updates(registry, "enheter", http=http, batch_size=2)
    assert result.status == "completed"
    assert result.counts.listed == 2
    assert result.tombstoned == 1
    assert result.cursor == "101"
    dataset_id = MIRRORS["enheter"].dataset_id
    rows = registry.list_records(dataset_id)
    assert [row["subject_code"] for row in rows] == ["923609016"]
    assert rows[0]["request_url"] == equinor_url
    assert rows[0]["subject_label"] == "EQUINOR ASA"
    assert json.loads(rows[0]["attributes_json"]) == {"antallansatte": 22000}
    tombstone = registry.list_record_tombstones(dataset_id)[0]
    assert tombstone["subject_code"] == "933365573"
    assert tombstone["reason"] == "Fjernet"
    checkpoint = registry.get_crawl_checkpoint(MIRRORS["enheter"].pipeline_id)
    assert checkpoint["cursor"] == "101"
    assert checkpoint["cursor_time"] == "2026-09-08T16:00:41.000Z"
    assert "dato=2026-09-07T02%3A26%3A53.000Z" in http.gets[0]
    assert "oppdateringsid=102" in http.gets[-1]
    registry.close()


def test_failed_item_refetch_does_not_advance_update_cursor(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    sync_snapshot(
        registry,
        "enheter",
        storage_dir=tmp_path / "raw",
        http=SnapshotHttp(_snapshot(tmp_path)),
    )
    event = _event(100, "923609016", "Endring")
    wrong_url = MIRRORS["enheter"].item_prefix + "923609016"
    http = UpdateHttp(
        pages=[[event]],
        items={
            wrong_url: {
                "organisasjonsnummer": "933365573",
                "navn": "WRONG ENTITY",
            }
        },
    )
    with pytest.raises(ValueError, match="not event subject"):
        sync_updates(registry, "enheter", http=http, batch_size=1)
    checkpoint = registry.get_crawl_checkpoint(MIRRORS["enheter"].pipeline_id)
    assert checkpoint["cursor"] is None
    original = registry.list_records(
        MIRRORS["enheter"].dataset_id, subject_code="923609016"
    )[0]
    assert original["request_url"] == MIRRORS["enheter"].snapshot_url
    registry.close()


def test_updates_require_a_complete_snapshot_checkpoint(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    with pytest.raises(ValueError, match="complete snapshot"):
        sync_updates(registry, "enheter", http=UpdateHttp([], {}))
    registry.close()


def test_brreg_source_time_is_normalized_for_update_queries() -> None:
    assert brreg_time_to_iso("Tue Sep 08 04:26:53 CEST 2026") == (
        "2026-09-08T02:26:53.000Z"
    )
    assert brreg_time_to_iso("2026-09-08T16:00:00.000Z") == (
        "2026-09-08T16:00:00.000Z"
    )
