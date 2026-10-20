"""Move Cristin name cards out of `observations` and into `records`.

The connectors now write entity records. These rows were written before that
and still carry a name as the value of a measurement, which is what made 1,413
institutions, people, projects, results, biobanks and units count as published
statistics.

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

from public_data_agent.cristin_records import records_from_cells
from public_data_agent.registry import Registry
from public_data_agent.verify import demonstrated_capability

SOURCES = ("cristin", "crinst", "crunit", "crperson", "crproj", "crresult", "crbio")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/registry.sqlite")
    parser.add_argument("--sources", default=",".join(SOURCES))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", default="data/cristin_observations_backup.json.gz")
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
        print("no cristin observation rows left to move")
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

    written = 0
    for row in rows:
        cells = [
            (
                row["measure"],
                json.loads(row["value_json"]) if row["value_json"] is not None else None,
                json.loads(row["dimensions_json"] or "{}"),
            )
        ]
        for record in records_from_cells(
            cells, dataset_id=row["dataset_id"], table_id=row["table_id"]
        ):
            registry.upsert_record(
                {
                    **record,
                    "dataset_id": row["dataset_id"],
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

    changes: Counter[str] = Counter()
    for dataset_id in sorted({row["dataset_id"] for row in rows}):
        derived = demonstrated_capability(registry, dataset_id)
        existing = registry.get_capability(dataset_id)
        was = existing["capability"] if existing else None
        now = derived[0] if derived else None
        changes[f"{was} -> {now}"] += 1
    for change, count in changes.most_common():
        print(f"  capability {change}: {count}")
    registry.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
