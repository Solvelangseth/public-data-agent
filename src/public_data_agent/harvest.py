from __future__ import annotations

from public_data_agent.mapping import map_harvested_record
from public_data_agent.models import DatasetRef, HarvestCounts
from public_data_agent.registry import Registry, utc_now
from public_data_agent.sources.base import CatalogSource


def harvest(
    registry: Registry,
    source: CatalogSource,
    *,
    limit: int | None = None,
    offset: int = 0,
    refresh_all: bool = False,
    notes: str | None = None,
) -> HarvestCounts:
    """Ingest catalog metadata. Upserts by stable id. Does not wipe the registry."""

    counts = HarvestCounts()
    run_id = registry.start_run(
        source_id=source.source_id,
        source_name=source.source_name,
        source_endpoints=source.endpoints,
        limit_applied=limit,
        notes=notes,
    )
    status = "failed"
    try:
        refs = source.list_dataset_refs(limit=limit, offset=offset)
        counts.listed = len(refs)
        to_fetch, skipped = _split_unchanged(registry, source.source_id, refs, refresh_all)
        now = utc_now()
        for ref in skipped:
            registry.mark_seen(source.source_id, ref.source_native_uri, run_id, now)
            counts.unchanged += 1

        try:
            records = source.fetch_many(to_fetch)
        except Exception as exc:
            # If the batch path fails entirely, try one-by-one so a harvest run
            # can still finish the page it listed.
            records = []
            for ref in to_fetch:
                try:
                    records.append(source.fetch_dataset(ref))
                except Exception as one_exc:
                    counts.failed += 1
                    counts.errors.append(_error(ref, one_exc))
            if not records and to_fetch and not counts.errors:
                raise exc

        fetched_uris = {record.source_native_uri for record in records}
        for ref in to_fetch:
            if ref.source_native_uri not in fetched_uris:
                # fetch_many may have dropped a ref; try once more.
                try:
                    records.append(source.fetch_dataset(ref))
                    fetched_uris.add(ref.source_native_uri)
                except Exception as exc:
                    counts.failed += 1
                    counts.errors.append(_error(ref, exc))

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
        status = "completed"
    finally:
        registry.finish_run(run_id, counts, status=status)
    return counts


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
