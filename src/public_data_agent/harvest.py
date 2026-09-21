from __future__ import annotations

from urllib.parse import urlsplit

import sys
from collections.abc import Callable
from typing import TextIO

from public_data_agent.mapping import map_harvested_record
from public_data_agent.models import DatasetRef, HarvestCounts
from public_data_agent.registry import Registry, utc_now
from public_data_agent.sources.base import CatalogSource

ProgressFn = Callable[[str], None]


# Final path segments that name an API's own plumbing, not a dataset. Harvesting
# every path of an API spec catalogued 46 of these as datasets -- 30 `healthz`
# endpoints across api.met.no alone, plus `status`, `ping`, `test` and OGC
# `conformance` declarations. Against the 15,492-row registry these five
# segments matched those 46 rows and nothing else, so the filter is exact on
# the data it was measured against. It is checked on the native URI only; a
# dataset merely *titled* "Test" is left alone.
SERVICE_ENDPOINT_SEGMENTS = frozenset({"healthz", "ping", "status", "test", "conformance"})


def is_service_endpoint(uri: str | None) -> bool:
    path = urlsplit(uri or "").path.rstrip("/")
    return path.rsplit("/", 1)[-1].casefold() in SERVICE_ENDPOINT_SEGMENTS


def harvest(
    registry: Registry,
    source: CatalogSource,
    *,
    limit: int | None = None,
    offset: int = 0,
    refresh_all: bool = False,
    notes: str | None = None,
    batch_size: int | None = None,
    progress: ProgressFn | None = None,
) -> HarvestCounts:
    """Ingest catalog metadata. Upserts by stable id. Does not wipe the registry.

    Fetched records are written after each batch so a killed run can resume
    without refetching rows already stored with the same catalog-record modified.
    """

    chunk = batch_size or getattr(source, "batch_size", 25)
    counts = HarvestCounts()
    run_id = registry.start_run(
        source_id=source.source_id,
        source_name=source.source_name,
        source_endpoints=source.endpoints,
        limit_applied=limit,
        notes=notes,
    )
    status = "failed"
    log = progress or (lambda _message: None)
    try:
        refs = source.list_dataset_refs(limit=limit, offset=offset)
        counts.listed = len(refs)
        kept = [ref for ref in refs if not is_service_endpoint(ref.source_native_uri)]
        counts.ignored = len(refs) - len(kept)
        refs = kept
        to_fetch, skipped = _split_unchanged(registry, source.source_id, refs, refresh_all)
        now = utc_now()
        for ref in skipped:
            registry.mark_seen(source.source_id, ref.source_native_uri, run_id, now)
            counts.unchanged += 1
        registry.checkpoint_run(run_id, counts)
        log(
            f"listed {counts.listed}: fetch {len(to_fetch)}, "
            f"skip unchanged {len(skipped)}, ignore service endpoints {counts.ignored}, "
            f"batch {chunk}"
        )

        done = 0
        for piece in _chunks(to_fetch, chunk):
            records = _fetch_chunk(source, piece, counts)
            for record in records:
                try:
                    mapped = map_harvested_record(record)
                    action = registry.upsert(mapped, run_id)
                except Exception as exc:
                    counts.failed += 1
                    counts.errors.append(
                        {
                            "uri": record.source_native_uri,
                            "id": record.source_native_id or "",
                            "error": str(exc),
                        }
                    )
                    continue
                if action == "inserted":
                    counts.inserted += 1
                elif action == "updated":
                    counts.updated += 1
                else:
                    counts.unchanged += 1
            done += len(piece)
            registry.checkpoint_run(run_id, counts)
            if done == len(to_fetch) or done % max(chunk * 4, 100) == 0:
                log(
                    f"progress {done}/{len(to_fetch)} "
                    f"inserted={counts.inserted} updated={counts.updated} "
                    f"unchanged={counts.unchanged} failed={counts.failed}"
                )
        status = "completed"
    finally:
        registry.finish_run(run_id, counts, status=status)
        log(
            f"run {run_id} {status}: listed={counts.listed} inserted={counts.inserted} "
            f"updated={counts.updated} unchanged={counts.unchanged} failed={counts.failed}"
        )
    return counts


def stderr_progress(message: str, file: TextIO = sys.stderr) -> None:
    print(message, file=file, flush=True)


def _fetch_chunk(source: CatalogSource, chunk: list[DatasetRef], counts: HarvestCounts):
    try:
        records = source.fetch_many(chunk)
    except Exception:
        records = []
        for ref in chunk:
            try:
                records.append(source.fetch_dataset(ref))
            except Exception as exc:
                counts.failed += 1
                counts.errors.append(_error(ref, exc))
        return records

    fetched_uris = {record.source_native_uri for record in records}
    for ref in chunk:
        if ref.source_native_uri in fetched_uris:
            continue
        try:
            records.append(source.fetch_dataset(ref))
        except Exception as exc:
            counts.failed += 1
            counts.errors.append(_error(ref, exc))
    return records


def _split_unchanged(
    registry: Registry,
    source_id: str,
    refs: list[DatasetRef],
    refresh_all: bool,
) -> tuple[list[DatasetRef], list[DatasetRef]]:
    if refresh_all:
        return refs, []
    to_fetch: list[DatasetRef] = []
    skipped: list[DatasetRef] = []
    for ref in refs:
        if not ref.catalog_modified:
            to_fetch.append(ref)
            continue
        stored = registry.existing_catalog_modified(source_id, ref.source_native_uri)
        if stored == ref.catalog_modified:
            skipped.append(ref)
        else:
            to_fetch.append(ref)
    return to_fetch, skipped


def _error(ref: DatasetRef, exc: Exception) -> dict[str, str]:
    return {
        "uri": ref.source_native_uri,
        "id": ref.source_native_id or "",
        "error": str(exc),
    }


def _chunks(items: list[DatasetRef], size: int) -> list[list[DatasetRef]]:
    return [items[i : i + size] for i in range(0, len(items), size)]
