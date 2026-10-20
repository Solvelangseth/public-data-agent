"""Move name cards out of `observations` and into `records`.

The connectors now write entity records. These rows were written before that
and still carry a name as the value of a measurement, which is what made
institutions, people, projects, biobanks, scooter models and curriculum codes
count as published statistics.

They are converted in place rather than re-fetched: the conversion reads the
stored cell through the same `records_from_cells` the connector now calls, so
the result is identical to what a re-fetch would write, and the provenance
stays the provenance of the fetch that actually happened -- its run, its
timestamp, its HTTP status -- instead of being restamped with today's.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path

from public_data_agent.entity_records import (
    CRISTIN_ID_FIELDS,
    ENTUR_ID_FIELDS,
    FEATURE_ID_FIELDS,
    GREP_ID_FIELDS,
    records_from_cells,
)
from public_data_agent.registry import Registry, utc_now
from public_data_agent.verify import demonstrated_capability

# Each source's identifier vocabulary, the same one its connector now passes.
# A source converted with the wrong one would key its records differently from
# what a re-fetch writes, which is the one thing this script must not do.
SHAPES = {
    "cristin": (CRISTIN_ID_FIELDS, "cristin", "entity"),
    "crinst": (CRISTIN_ID_FIELDS, "cristin", "entity"),
    "crunit": (CRISTIN_ID_FIELDS, "cristin", "entity"),
    "crperson": (CRISTIN_ID_FIELDS, "cristin", "entity"),
    "crproj": (CRISTIN_ID_FIELDS, "cristin", "entity"),
    "crresult": (CRISTIN_ID_FIELDS, "cristin", "entity"),
    "crbio": (CRISTIN_ID_FIELDS, "cristin", "entity"),
    "entur": (ENTUR_ID_FIELDS, "entur", "entity"),
    "grep": (GREP_ID_FIELDS, "grep", "entity"),
    "hi": (FEATURE_ID_FIELDS, "hi", "feature"),
}
SOURCES = tuple(SHAPES)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/registry.sqlite")
    parser.add_argument("--sources", default=",".join(SOURCES))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", default="data/name_card_observations_backup.json.gz")
    args = parser.parse_args()

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    registry = Registry(Path(args.db))
    rows: list[dict] = []
    for source in sources:
        rows.extend(
            dict(r)
            for r in registry.conn.execute(
                "SELECT * FROM observations WHERE dataset_id LIKE ?", (f"{source}:%",)
            )
        )
    if not rows:
        print("no name-card observation rows left to move")
        return 0

    by_source = Counter(row["dataset_id"].split(":")[0] for row in rows)
    for source, count in by_source.most_common():
        print(f"{source}: {count} observation cells")
    print(f"total {len(rows)} cells in {len({r['dataset_id'] for r in rows})} datasets")
    if not args.apply:
        print("\ndry run; pass --apply to convert.")
        return 0

    Path(args.backup).parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.backup, "wt", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False)
    print(f"backed up {len(rows)} rows to {args.backup}")

    # Converted a dataset at a time, not a row at a time. A member that printed
    # no identifier is keyed by its position in the response, and one row at a
    # time every such member is position zero and they overwrite each other.
    by_dataset: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        by_dataset.setdefault((row["dataset_id"], row["table_id"]), []).append(row)

    written = 0
    for (dataset_id, table_id), group in by_dataset.items():
        cells = [
            (
                row["measure"],
                json.loads(row["value_json"]) if row["value_json"] is not None else None,
                json.loads(row["dimensions_json"] or "{}"),
            )
            for row in group
        ]
        id_fields, prefix, kind = SHAPES[dataset_id.split(":")[0]]
        records = records_from_cells(
            cells,
            dataset_id=dataset_id,
            table_id=table_id,
            id_fields=id_fields,
            prefix=prefix,
            kind=kind,
        )
        if len(records) != len(group):
            raise SystemExit(
                f"{dataset_id}: {len(group)} cells became {len(records)} records; "
                "the provenance of each row could not be carried across"
            )
        for record, row in zip(records, group):
            registry.upsert_record(
                {
                    **record,
                    "dataset_id": dataset_id,
                    "series": row["series"],
                    "retrieved_at": row["retrieved_at"],
                    "request_url": row["request_url"],
                    "http_status": row["http_status"],
                    "publisher_name": row["publisher_name"],
                    "license": row["license"],
                },
                row["fetch_run_id"],
            )
            written += 1
    registry.conn.commit()
    print(f"wrote {written} entity records")

    deleted = 0
    for source in sources:
        deleted += registry.conn.execute(
            "DELETE FROM observations WHERE dataset_id LIKE ?", (f"{source}:%",)
        ).rowcount
    registry.conn.commit()
    print(f"removed {deleted} observation cells")

    # The rows these datasets are judged on have just changed table, so the
    # capability is re-read from where they now live. What it was is appended
    # to the notes rather than replaced, so the move stays auditable.
    changes: Counter[str] = Counter()
    for dataset_id in sorted({row["dataset_id"] for row in rows}):
        derived = demonstrated_capability(registry, dataset_id)
        existing = registry.get_capability(dataset_id)
        was = existing["capability"] if existing else None
        now = derived[0] if derived else None
        changes[f"{was} -> {now}"] += 1
        if derived is None or existing is None or was == now:
            continue
        merged = {key: existing[key] for key in existing.keys() if key != "dataset_id"}
        stored = registry.conn.execute(
            "SELECT COUNT(*) FROM records WHERE dataset_id = ?", (dataset_id,)
        ).fetchone()[0]
        note = f"re-read {utc_now()[:10]} after the rows moved to records: was {was}"
        merged.update(
            {
                "capability": now,
                "record_kind": derived[1],
                "verified_sample_count": stored,
                "notes": f"{existing['notes']}; {note}" if existing["notes"] else note,
            }
        )
        registry.set_capability(dataset_id, merged)
    registry.conn.commit()
    for change, count in changes.most_common():
        print(f"  capability {change}: {count}")
    registry.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
