"""Continuously mirror Brønnøysundregistrene's complete public registers.

The item connectors prove that one company can be fetched. This module follows
the publisher's copy-maintenance contract: stream the nightly complete CSV
gzip, record its ETag/Last-Modified/hash, and write all entities under one
dataset. Incremental update events use the same record identities.
"""

from __future__ import annotations

import csv
import gzip
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlencode, urlsplit
from zoneinfo import ZoneInfo

from public_data_agent.http_util import (
    FileResponse,
    HttpClient,
    JsonResponse,
    RateLimiter,
    SourceHttpError,
)
from public_data_agent.models import HarvestCounts
from public_data_agent.registry import Registry, utc_now
from public_data_agent.sources.brenheter import ORGNR_SCHEME, valid_orgnr

BRREG_MIRROR_RPS = 2.0
BRREG_MIRROR_BURST = 4
BRREG_UPDATE_OVERLAP = timedelta(days=1)
BRREG_LICENSE = "https://data.norge.no/nlod/no/2.0"
BRREG_PUBLISHER = "Brønnøysundregistrene"


@dataclass(frozen=True)
class MirrorSpec:
    kind: str
    pipeline_id: str
    dataset_id: str
    title: str
    snapshot_url: str
    update_url: str
    item_prefix: str


MIRRORS = {
    "enheter": MirrorSpec(
        kind="enheter",
        pipeline_id="brreg-mirror:enheter",
        dataset_id="brenheter:all",
        title="Enhetsregisteret — komplett kopi av enheter",
        snapshot_url="https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv",
        update_url="https://data.brreg.no/enhetsregisteret/api/oppdateringer/enheter",
        item_prefix="https://data.brreg.no/enhetsregisteret/api/enheter/",
    ),
    "underenheter": MirrorSpec(
        kind="underenheter",
        pipeline_id="brreg-mirror:underenheter",
        dataset_id="brunder:all",
        title="Enhetsregisteret — komplett kopi av underenheter",
        snapshot_url="https://data.brreg.no/enhetsregisteret/api/underenheter/lastned/csv",
        update_url="https://data.brreg.no/enhetsregisteret/api/oppdateringer/underenheter",
        item_prefix="https://data.brreg.no/enhetsregisteret/api/underenheter/",
    ),
}


class SnapshotHttp(Protocol):
    def head(self, url: str, *, headers: dict[str, str] | None = None) -> FileResponse: ...

    def download(
        self,
        url: str,
        destination: Path,
        *,
        headers: dict[str, str] | None = None,
        chunk_size: int = 1024 * 1024,
    ) -> FileResponse: ...


class UpdateHttp(Protocol):
    def get_json_response(
        self, url: str, *, headers: dict[str, str] | None = None
    ) -> JsonResponse: ...


@dataclass
class MirrorResult:
    pipeline_id: str
    dataset_id: str
    request_url: str
    status: str
    counts: HarvestCounts = field(default_factory=HarvestCounts)
    snapshot_id: int | None = None
    storage_path: str | None = None
    sha256: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    cursor: str | None = None
    tombstoned: int = 0


def mirror_spec(kind: str) -> MirrorSpec:
    try:
        return MIRRORS[kind]
    except KeyError as exc:
        raise ValueError(f"unknown Brreg mirror {kind!r}; choose {sorted(MIRRORS)}") from exc


def sync_snapshot(
    registry: Registry,
    kind: str,
    *,
    storage_dir: Path,
    http: SnapshotHttp | None = None,
    limit: int | None = None,
    batch_size: int = 1000,
    force: bool = False,
) -> MirrorResult:
    """Download and stream one complete Brreg CSV snapshot into entity records.

    `limit` exists only for live smoke checks. A limited run never advances the
    durable snapshot checkpoint because it is not a complete copy.
    """

    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    spec = mirror_spec(kind)
    client = http or HttpClient(
        limiter=RateLimiter(BRREG_MIRROR_RPS, BRREG_MIRROR_BURST),
        timeout=120.0,
        max_retries=6,
    )
    _ensure_mirror_dataset(registry, spec)
    remote = client.head(spec.snapshot_url)
    if remote.status >= 400:
        raise ValueError(f"Brreg snapshot HEAD returned HTTP {remote.status}: {spec.snapshot_url}")
    etag = _header(remote, "etag")
    last_modified = _header(remote, "last-modified")
    checkpoint = registry.get_crawl_checkpoint(spec.pipeline_id)
    if not force and limit is None and etag and checkpoint and checkpoint.get("etag") == etag:
        return MirrorResult(
            pipeline_id=spec.pipeline_id,
            dataset_id=spec.dataset_id,
            request_url=spec.snapshot_url,
            status="unchanged",
            etag=etag,
            last_modified=last_modified,
            storage_path=checkpoint.get("snapshot_path"),
            sha256=checkpoint.get("snapshot_sha256"),
        )

    snapshot_id = registry.start_raw_snapshot(
        pipeline_id=spec.pipeline_id,
        dataset_id=spec.dataset_id,
        request_url=spec.snapshot_url,
        http_status=remote.status,
        etag=etag,
        last_modified=last_modified,
        content_type=_header(remote, "content-type"),
        content_length=_integer_header(remote, "content-length"),
    )
    storage_dir.mkdir(parents=True, exist_ok=True)
    destination = storage_dir / f"{kind}-{snapshot_id}.csv.gz"
    conditional = None
    if checkpoint and checkpoint.get("etag") and not force:
        conditional = {"If-None-Match": str(checkpoint["etag"])}
    counts = HarvestCounts()
    fetch_run_id: int | None = None
    downloaded: FileResponse | None = None
    try:
        downloaded = client.download(spec.snapshot_url, destination, headers=conditional)
        if downloaded.status == 304:
            registry.finish_raw_snapshot(snapshot_id, status="unchanged", records_seen=0)
            return MirrorResult(
                pipeline_id=spec.pipeline_id,
                dataset_id=spec.dataset_id,
                request_url=spec.snapshot_url,
                status="unchanged",
                snapshot_id=snapshot_id,
                etag=etag,
                last_modified=last_modified,
            )
        if downloaded.status >= 400 or downloaded.path is None:
            raise ValueError(
                f"Brreg snapshot download returned HTTP {downloaded.status}: {spec.snapshot_url}"
            )
        # Prefer validators that accompanied the bytes. The snapshot can rotate
        # between HEAD and GET, and a checkpoint must describe what we stored.
        etag = _header(downloaded, "etag") or etag
        last_modified = _header(downloaded, "last-modified") or last_modified
        fetch_run_id = registry.start_fetch_run(
            dataset_id=spec.dataset_id,
            table_id=kind,
            request_url=spec.snapshot_url,
            request_method="GET",
        )
        registry.set_fetch_request(
            fetch_run_id,
            request_url=spec.snapshot_url,
            request_body={"method": "GET", "format": "csv+gzip", "etag": etag},
        )
        tombstoned = _ingest_snapshot_rows(
            registry,
            spec,
            downloaded.path,
            fetch_run_id=fetch_run_id,
            http_status=downloaded.status,
            counts=counts,
            limit=limit,
            batch_size=batch_size,
        )
        registry.finish_fetch_run(
            fetch_run_id, counts, status="completed", http_status=downloaded.status
        )
        registry.finish_raw_snapshot(
            snapshot_id,
            status="completed" if limit is None else "sampled",
            records_seen=counts.listed,
            sha256=downloaded.sha256,
            storage_path=str(downloaded.path),
        )
        _write_snapshot_shape(registry, spec, downloaded.path, counts.listed)
        verified_at = utc_now()
        registry.set_capability(
            spec.dataset_id,
            {
                "capability": "entities",
                "record_kind": "entity",
                "endpoint": spec.snapshot_url,
                "request_method": "GET",
                "source_modified_at": last_modified,
                "verified_at": verified_at,
                "verified_sample_count": counts.listed,
                "notes": "complete CSV snapshot" if limit is None else "bounded snapshot sample",
            },
        )
        if limit is None:
            registry.set_crawl_checkpoint(
                spec.pipeline_id,
                {
                    "source_id": "brreg",
                    "dataset_id": spec.dataset_id,
                    # A complete snapshot supersedes the old event position.
                    # Resume from the timestamp of these bytes, not a cursor
                    # that can replay pre-snapshot changes and regress rows.
                    "cursor": None,
                    "cursor_time": last_modified,
                    "etag": etag,
                    "last_modified": last_modified,
                    "snapshot_sha256": downloaded.sha256,
                    "snapshot_path": str(downloaded.path),
                    "extra": {"snapshot_id": snapshot_id, "records": counts.listed},
                },
            )
        return MirrorResult(
            pipeline_id=spec.pipeline_id,
            dataset_id=spec.dataset_id,
            request_url=spec.snapshot_url,
            status="completed" if limit is None else "sampled",
            counts=counts,
            snapshot_id=snapshot_id,
            storage_path=str(downloaded.path),
            sha256=downloaded.sha256,
            etag=etag,
            last_modified=last_modified,
            tombstoned=tombstoned,
        )
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": spec.snapshot_url})
        if fetch_run_id is not None:
            registry.finish_fetch_run(
                fetch_run_id,
                counts,
                status="failed",
                http_status=downloaded.status if downloaded else remote.status,
            )
        registry.finish_raw_snapshot(
            snapshot_id,
            status="failed",
            records_seen=counts.listed,
            sha256=downloaded.sha256 if downloaded else None,
            storage_path=str(downloaded.path) if downloaded and downloaded.path else None,
            error=str(exc),
        )
        raise


def sync_updates(
    registry: Registry,
    kind: str,
    *,
    http: UpdateHttp | None = None,
    batch_size: int = 100,
    max_events: int | None = None,
) -> MirrorResult:
    """Apply Brreg update events and advance the publisher cursor after commit.

    The update feed is only a change notice. For Ny/Endring/Ukjent events the
    printed item link is fetched and the whole entity replaces the old version,
    as Brreg recommends. Sletting/Fjernet events remove the current row and
    leave a tombstone. A complete snapshot checkpoint is required first.
    """

    if batch_size < 1 or batch_size > 10000:
        raise ValueError("batch_size must be between 1 and 10000")
    if max_events is not None and max_events < 1:
        raise ValueError("max_events must be positive")
    spec = mirror_spec(kind)
    checkpoint = registry.get_crawl_checkpoint(spec.pipeline_id)
    if checkpoint is None or not checkpoint.get("snapshot_sha256"):
        raise ValueError(
            f"{spec.pipeline_id} has no complete snapshot checkpoint; run the snapshot first"
        )
    client = http or HttpClient(
        limiter=RateLimiter(BRREG_MIRROR_RPS, BRREG_MIRROR_BURST),
        timeout=60.0,
        max_retries=6,
    )
    counts = HarvestCounts()
    tombstoned = 0
    current_cursor = _integer_cursor(checkpoint.get("cursor"))
    first_url = _update_request_url(spec, checkpoint, current_cursor, batch_size)
    run_id = registry.start_fetch_run(
        dataset_id=spec.dataset_id,
        table_id=f"{kind}-updates",
        request_url=first_url,
        request_method="GET",
    )
    registry.set_fetch_request(
        run_id,
        request_url=first_url,
        request_body={"method": "GET", "cursor": current_cursor, "batch_size": batch_size},
    )
    status = "failed"
    http_status = 0
    try:
        while max_events is None or counts.listed < max_events:
            remaining = batch_size
            if max_events is not None:
                remaining = min(remaining, max_events - counts.listed)
            request_url = _update_request_url(spec, checkpoint, current_cursor, remaining)
            response = client.get_json_response(request_url)
            http_status = response.status
            if response.status >= 400:
                raise ValueError(
                    f"Brreg updates returned HTTP {response.status}: {request_url}"
                )
            events = _update_events(response.body)
            if not events:
                break
            if len(events) > remaining:
                raise ValueError(
                    f"Brreg updates returned {len(events)} events for requested size {remaining}"
                )
            prepared = _prepare_update_page(client, spec, events, current_cursor)
            retrieved_at = utc_now()
            with registry.deferred_commit():
                for event, entity in prepared:
                    event_id = int(event["oppdateringsid"])
                    orgnr = str(event["organisasjonsnummer"])
                    change = str(event.get("endringstype") or "Ukjent")
                    if event.get("_item_not_found"):
                        change = f"{change}:item_not_found"
                    if entity is None:
                        removed = registry.tombstone_record(
                            dataset_id=spec.dataset_id,
                            kind="entity",
                            subject_scheme=ORGNR_SCHEME,
                            subject_code=orgnr,
                            reason=change,
                            event_id=str(event_id),
                            request_url=request_url,
                            retrieved_at=retrieved_at,
                        )
                        tombstoned += 1
                        if removed:
                            counts.updated += 1
                        else:
                            counts.unchanged += 1
                    else:
                        item_url = str(event["_item_url"])
                        action = registry.upsert_record(
                            _entity_record(
                                spec,
                                entity,
                                retrieved_at=retrieved_at,
                                request_url=item_url,
                                http_status=int(event["_item_status"]),
                            ),
                            run_id,
                        )
                        registry.clear_record_tombstone(
                            dataset_id=spec.dataset_id,
                            kind="entity",
                            subject_code=orgnr,
                        )
                        if action == "inserted":
                            counts.inserted += 1
                        elif action == "updated":
                            counts.updated += 1
                        else:
                            counts.unchanged += 1
                    counts.listed += 1
                    current_cursor = event_id
                    checkpoint = {
                        **checkpoint,
                        "cursor": str(current_cursor),
                        "cursor_time": event.get("dato") or checkpoint.get("cursor_time"),
                        "extra": {
                            **(checkpoint.get("extra") or {}),
                            "last_update_event": str(current_cursor),
                        },
                    }
                registry.set_crawl_checkpoint(spec.pipeline_id, checkpoint)
            registry.checkpoint_fetch_run(run_id, counts)
            if len(events) < remaining:
                break
        registry.finish_fetch_run(run_id, counts, status="completed", http_status=http_status)
        status = "completed"
        return MirrorResult(
            pipeline_id=spec.pipeline_id,
            dataset_id=spec.dataset_id,
            request_url=first_url,
            status="completed" if counts.listed else "unchanged",
            counts=counts,
            etag=checkpoint.get("etag"),
            last_modified=checkpoint.get("last_modified"),
            cursor=str(current_cursor) if current_cursor is not None else None,
            tombstoned=tombstoned,
        )
    except Exception as exc:
        counts.failed += 1
        counts.errors.append({"error": str(exc), "url": first_url})
        raise
    finally:
        if status != "completed":
            registry.finish_fetch_run(
                run_id, counts, status="failed", http_status=http_status
            )


def _prepare_update_page(
    client: UpdateHttp,
    spec: MirrorSpec,
    events: list[dict[str, Any]],
    current_cursor: int | None,
) -> list[tuple[dict[str, Any], dict[str, Any] | None]]:
    prepared: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
    previous = current_cursor
    for raw in events:
        event = dict(raw)
        try:
            event_id = int(event["oppdateringsid"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Brreg update event has no integer oppdateringsid") from exc
        if previous is not None and event_id <= previous:
            raise ValueError(
                f"Brreg update ids are not strictly ascending: {event_id} after {previous}"
            )
        previous = event_id
        orgnr = str(event.get("organisasjonsnummer") or "").strip()
        if not valid_orgnr(orgnr):
            raise ValueError(f"Brreg update event printed invalid organisasjonsnummer {orgnr!r}")
        event["organisasjonsnummer"] = orgnr
        change = str(event.get("endringstype") or "").casefold()
        if change in {"sletting", "fjernet"}:
            prepared.append((event, None))
            continue
        item_url = _printed_event_item_url(event, spec, orgnr)
        try:
            response = client.get_json_response(item_url)
        except SourceHttpError as exc:
            if exc.status == 404:
                event["_item_not_found"] = True
                prepared.append((event, None))
                continue
            raise
        if response.status >= 400:
            if response.status == 404:
                event["_item_not_found"] = True
                prepared.append((event, None))
                continue
            raise ValueError(
                f"Brreg item refetch returned HTTP {response.status}: {item_url}"
            )
        entity = _entity_from_item(response.body)
        if entity["subject_code"] != orgnr:
            raise ValueError(
                f"Brreg update item printed organisasjonsnummer {entity['subject_code']!r}, "
                f"not event subject {orgnr!r}"
            )
        event["_item_url"] = item_url
        event["_item_status"] = response.status
        prepared.append((event, entity))
    return prepared


def _entity_record(
    spec: MirrorSpec,
    entity: dict[str, Any],
    *,
    retrieved_at: str,
    request_url: str,
    http_status: int,
) -> dict[str, Any]:
    orgnr = entity["subject_code"]
    return {
        "id": f"entity:{spec.dataset_id}:{orgnr}",
        "dataset_id": spec.dataset_id,
        "kind": "entity",
        "series": f"brreg-mirror:{spec.kind}",
        "subject_scheme": ORGNR_SCHEME,
        "subject_code": orgnr,
        "subject_label": entity["subject_label"],
        "period": None,
        "measure": None,
        "value": None,
        "attributes": entity["attributes"],
        "retrieved_at": retrieved_at,
        "request_url": request_url,
        "http_status": http_status,
        "publisher_name": BRREG_PUBLISHER,
        "license": BRREG_LICENSE,
    }


def _update_request_url(
    spec: MirrorSpec,
    checkpoint: dict[str, Any],
    cursor: int | None,
    size: int,
) -> str:
    params: list[tuple[str, str]] = []
    if cursor is not None:
        params.append(("oppdateringsid", str(cursor + 1)))
    else:
        cursor_time = checkpoint.get("cursor_time") or checkpoint.get("last_modified")
        if not cursor_time:
            raise ValueError("snapshot checkpoint has neither cursor nor source timestamp")
        params.append(("dato", _initial_update_time(str(cursor_time))))
    params.extend((("size", str(size)), ("sort", "id,ASC")))
    return f"{spec.update_url}?{urlencode(params)}"


def _update_events(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("Brreg update response is not a JSON object")
    embedded = payload.get("_embedded")
    if embedded is None:
        return []
    if not isinstance(embedded, dict):
        raise ValueError("Brreg update response has invalid _embedded")
    lists = [value for value in embedded.values() if isinstance(value, list)]
    if not lists:
        return []
    events = [item for item in lists[0] if isinstance(item, dict)]
    if len(events) != len(lists[0]):
        raise ValueError("Brreg update response contains a non-object event")
    return events


def _printed_event_item_url(event: dict[str, Any], spec: MirrorSpec, orgnr: str) -> str:
    links = event.get("_links")
    if not isinstance(links, dict):
        raise ValueError(f"Brreg update {event.get('oppdateringsid')} has no printed _links")
    hrefs = []
    for link in links.values():
        if isinstance(link, dict) and isinstance(link.get("href"), str):
            hrefs.append(link["href"].strip())
    expected_path = urlsplit(spec.item_prefix + orgnr).path
    for href in hrefs:
        parsed = urlsplit(href)
        if (
            parsed.scheme == "https"
            and parsed.netloc.casefold() == "data.brreg.no"
            and parsed.path == expected_path
        ):
            return href
    raise ValueError(
        f"Brreg update {event.get('oppdateringsid')} has no valid printed item URL for {orgnr}"
    )


def brreg_time_to_iso(value: str) -> str:
    """Normalize Brreg's Last-Modified or an existing ISO timestamp for `dato`."""

    text = value.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}T", text):
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    else:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError):
            parsed = None
        if parsed is None:
            for zone in ("CEST", "CET"):
                try:
                    naive = datetime.strptime(text, f"%a %b %d %H:%M:%S {zone} %Y")
                    parsed = naive.replace(tzinfo=ZoneInfo("Europe/Oslo"))
                    break
                except ValueError:
                    continue
        if parsed is None:
            raise ValueError(f"cannot parse Brreg source timestamp {value!r}")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("Europe/Oslo"))
    return parsed.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _initial_update_time(value: str) -> str:
    # Brreg explicitly recommends beginning comfortably before the snapshot was
    # produced. Replaying a day is safe because event IDs and record upserts are
    # idempotent, and it closes the snapshot/publication race window.
    normalized = brreg_time_to_iso(value)
    parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    return (parsed - BRREG_UPDATE_OVERLAP).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _integer_cursor(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid stored Brreg cursor {value!r}") from exc


def _ensure_mirror_dataset(registry: Registry, spec: MirrorSpec) -> None:
    registry.ensure_dataset_identity(
        dataset_id=spec.dataset_id,
        title=spec.title,
        publisher_name=BRREG_PUBLISHER,
        access_path=spec.snapshot_url,
        license=BRREG_LICENSE,
        ingest_reason="brreg_complete_copy",
    )


def _ingest_snapshot_rows(
    registry: Registry,
    spec: MirrorSpec,
    path: Path,
    *,
    fetch_run_id: int,
    http_status: int,
    counts: HarvestCounts,
    limit: int | None,
    batch_size: int,
) -> int:
    retrieved_at = utc_now()
    pending: list[dict[str, str]] = []
    tombstoned = 0
    # The complete file is one logical replacement. Keeping its writes in one
    # transaction means a corrupt/truncated row cannot leave a half-new mirror.
    with registry.deferred_commit():
        if limit is None:
            registry.begin_record_reconciliation()
        with gzip.open(path, mode="rt", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if not reader.fieldnames or "organisasjonsnummer" not in reader.fieldnames:
                raise ValueError("Brreg CSV snapshot has no organisasjonsnummer column")
            for row in reader:
                pending.append(row)
                if len(pending) >= batch_size:
                    _store_snapshot_batch(
                        registry, spec, pending, fetch_run_id, http_status, retrieved_at, counts,
                        reconcile=limit is None,
                    )
                    pending = []
                    registry.checkpoint_fetch_run(fetch_run_id, counts)
                if limit is not None and counts.listed + len(pending) >= limit:
                    break
            if pending:
                _store_snapshot_batch(
                    registry, spec, pending, fetch_run_id, http_status, retrieved_at, counts,
                    reconcile=limit is None,
                )
                registry.checkpoint_fetch_run(fetch_run_id, counts)
        if limit is None:
            missing = registry.records_missing_from_reconciliation(
                dataset_id=spec.dataset_id,
                kind="entity",
                series=f"brreg-mirror:{spec.kind}",
            )
            for row in missing:
                registry.tombstone_record(
                    dataset_id=spec.dataset_id,
                    kind="entity",
                    subject_scheme=row.get("subject_scheme"),
                    subject_code=str(row["subject_code"]),
                    reason="absent_from_complete_snapshot",
                    event_id=None,
                    request_url=spec.snapshot_url,
                    retrieved_at=retrieved_at,
                )
                tombstoned += 1
    return tombstoned


def _store_snapshot_batch(
    registry: Registry,
    spec: MirrorSpec,
    rows: list[dict[str, str]],
    fetch_run_id: int,
    http_status: int,
    retrieved_at: str,
    counts: HarvestCounts,
    *,
    reconcile: bool,
) -> None:
    for row in rows:
            orgnr = str(row.get("organisasjonsnummer") or "").strip()
            if not valid_orgnr(orgnr):
                raise ValueError(
                    f"Brreg snapshot printed invalid organisasjonsnummer {orgnr!r}"
                )
            label = str(row.get("navn") or "").strip() or None
            attributes = {
                _canonical_field(str(key)): _csv_value(value)
                for key, value in row.items()
                if key not in {"organisasjonsnummer", "navn"} and value not in {None, ""}
            }
            record_id = f"entity:{spec.dataset_id}:{orgnr}"
            action = registry.upsert_record(
                {
                    "id": record_id,
                    "dataset_id": spec.dataset_id,
                    "kind": "entity",
                    "series": f"brreg-mirror:{spec.kind}",
                    "subject_scheme": ORGNR_SCHEME,
                    "subject_code": orgnr,
                    "subject_label": label,
                    "period": None,
                    "measure": None,
                    "value": None,
                    "attributes": attributes,
                    "retrieved_at": retrieved_at,
                    "request_url": spec.snapshot_url,
                    "http_status": http_status,
                    "publisher_name": BRREG_PUBLISHER,
                    "license": BRREG_LICENSE,
                },
                fetch_run_id,
            )
            if reconcile:
                registry.mark_record_seen(record_id)
            registry.clear_record_tombstone(
                dataset_id=spec.dataset_id, kind="entity", subject_code=orgnr
            )
            counts.listed += 1
            if action == "inserted":
                counts.inserted += 1
            elif action == "updated":
                counts.updated += 1
            else:
                counts.unchanged += 1


def _write_snapshot_shape(
    registry: Registry, spec: MirrorSpec, path: Path, record_count: int
) -> None:
    with gzip.open(path, mode="rt", encoding="utf-8-sig", newline="") as source:
        fields = next(csv.reader(source), None)
    if not fields or "organisasjonsnummer" not in fields:
        raise ValueError("Brreg CSV snapshot has no usable header")
    shape = [
        {
            "field_code": _canonical_field(code),
            "field_label": code,
            "field_role": "key" if code == "organisasjonsnummer" else "attribute",
            "value_count": record_count if code == "organisasjonsnummer" else None,
            "values": [],
        }
        for code in fields
    ]
    registry.set_resource_shape(
        spec.dataset_id,
        shape,
        keys=[
            {
                "scheme": ORGNR_SCHEME,
                "field_code": "organisasjonsnummer",
                "coverage_count": record_count,
            }
        ],
    )


def _entity_from_item(payload: Any) -> dict[str, Any]:
    """Project item JSON into the same flat field namespace as snapshot CSV."""

    if not isinstance(payload, dict):
        raise ValueError("Brreg item response is not a JSON object")
    orgnr = str(payload.get("organisasjonsnummer") or "").strip()
    if not valid_orgnr(orgnr):
        raise ValueError(f"Brreg item printed invalid organisasjonsnummer {orgnr!r}")
    label = str(payload.get("navn") or "").strip() or None
    attributes: dict[str, Any] = {}
    for key, value in payload.items():
        if key in {"organisasjonsnummer", "navn", "_links"}:
            continue
        _flatten_item_value(attributes, _canonical_field(str(key)), value)
    return {"subject_code": orgnr, "subject_label": label, "attributes": attributes}


def _flatten_item_value(target: dict[str, Any], prefix: str, value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "_links":
                continue
            _flatten_item_value(target, f"{prefix}.{_canonical_field(str(key))}", child)
        return
    target[prefix] = value


def _canonical_field(value: str) -> str:
    # Brreg's CSV output lowercases camelCase JSON property names. Case-folding
    # both sides gives snapshot rows and item refetches one stable field schema.
    return value.strip().casefold()


def _csv_value(value: str) -> Any:
    """Restore unambiguous scalar types without turning codes such as 0301 numeric."""

    stripped = value.strip()
    lowered = stripped.casefold()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if re.fullmatch(r"-?(?:0|[1-9]\d*)", stripped):
        return int(stripped)
    if re.fullmatch(r"-?(?:0|[1-9]\d*)\.\d+", stripped):
        return float(stripped)
    return value


def _header(response: FileResponse, name: str) -> str | None:
    value = response.headers.get(name.casefold())
    return value.strip() if value and value.strip() else None


def _integer_header(response: FileResponse, name: str) -> int | None:
    value = _header(response, name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
