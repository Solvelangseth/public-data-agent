"""Re-fetch the SSB Klass code lists so their items land in `records`.

Klass items were stored as observation cells -- 7,127 occupation titles, 358
municipality names and 42 Oslo bydeler counted as published measurements. The
connector now writes them as entity records, and these three datasets still
hold the old shape.

Re-fetching rather than rewriting the rows in place is deliberate: three HTTP
calls buy real provenance, and the rows then match byte for byte what the
connector produces today instead of a reconstruction that drifts from it.
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from public_data_agent.fetch import fetch_observations
from public_data_agent.registry import Registry
from public_data_agent.verify import demonstrated_capability

SERIES = "fetch:klass:%"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/registry.sqlite")
    parser.add_argument("--apply", action="store_true", help="write; otherwise report only")
    parser.add_argument("--backup", default="data/klass_observations_backup.json.gz")
    args = parser.parse_args()

    registry = Registry(Path(args.db))
    rows = registry.conn.execute(
        "SELECT dataset_id, COUNT(*) AS n FROM observations WHERE series LIKE ? "
        "GROUP BY dataset_id ORDER BY n DESC",
        (SERIES,),
    ).fetchall()
    if not rows:
        print("no klass observation rows left to move")
        return 0
    for row in rows:
        print(f"{row['dataset_id']}  {row['n']} observation cells")
    if not args.apply:
        print(f"\ndry run; {sum(r['n'] for r in rows)} cells would move. Pass --apply.")
        return 0

    stale = [
        dict(r)
        for r in registry.conn.execute(
            "SELECT * FROM observations WHERE series LIKE ?", (SERIES,)
        )
    ]
    Path(args.backup).parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.backup, "wt", encoding="utf-8") as handle:
        json.dump(stale, handle, ensure_ascii=False)
    print(f"backed up {len(stale)} rows to {args.backup}")

    for row in rows:
        dataset_id = row["dataset_id"]
        result = fetch_observations(registry, dataset_id, table_id="klass")
        print(
            f"{dataset_id}: HTTP {result.http_status}, {result.counts.listed} items "
            f"({result.counts.inserted} inserted, {result.counts.unchanged} unchanged)"
        )
        if result.http_status != 200 or result.counts.listed == 0:
            print("  refusing to delete the old cells: the re-fetch did not return items")
            continue
        deleted = registry.conn.execute(
            "DELETE FROM observations WHERE dataset_id = ? AND series LIKE ?",
            (dataset_id, SERIES),
        ).rowcount
        registry.conn.commit()
        print(f"  removed {deleted} observation cells")
        derived = demonstrated_capability(registry, dataset_id)
        print(f"  capability now reads: {derived}")
    registry.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
