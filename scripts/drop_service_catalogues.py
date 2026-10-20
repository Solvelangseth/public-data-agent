"""Remove rows that describe a service rather than report anything.

An ArcGIS MapServer root prints its `layers` array -- id, parent, visibility,
scale range, geometry type -- and the connectors stored each entry as an
observation. `defaultVisibility` and `parentLayerId` became published figures,
and the datasets were marked verified on the strength of them.

The connectors refuse this now. These rows were stored before that, and
deleting them is not enough on its own: the capability they were counted
towards has to stop claiming a verification they never supported. It is
cleared back to unverified with the reason recorded, which is what the
registry would have said if the fetch had refused in the first place.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path

from public_data_agent.registry import Registry, utc_now

SOURCES = ("fiskerigis", "arcticsdi")
REASON = (
    "unverified 2026-10-20: the stored rows were the map service's own layer "
    "list, not data. Each layer needs a <service>/<layer id>/query request, "
    "which has never been made."
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/registry.sqlite")
    parser.add_argument("--sources", default=",".join(SOURCES))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", default="data/service_catalogue_backup.json.gz")
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
        print("no service-catalogue rows left")
        return 0
    counts = Counter(row["dataset_id"].split(":")[0] for row in rows)
    for source, count in counts.most_common():
        print(f"{source}: {count} rows describing the service")
    datasets = sorted({row["dataset_id"] for row in rows})
    print(f"total {len(rows)} rows in {len(datasets)} datasets")
    if not args.apply:
        print("\ndry run; pass --apply to delete and unverify.")
        return 0

    Path(args.backup).parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.backup, "wt", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False)
    print(f"backed up {len(rows)} rows to {args.backup}")

    deleted = 0
    for source in sources:
        deleted += registry.conn.execute(
            "DELETE FROM observations WHERE dataset_id LIKE ?", (f"{source}:%",)
        ).rowcount
    print(f"removed {deleted} rows")

    cleared = 0
    for dataset_id in datasets:
        existing = registry.get_capability(dataset_id)
        if existing is None or not existing["verified_at"]:
            continue
        merged = {key: existing[key] for key in existing.keys() if key != "dataset_id"}
        merged.update(
            {
                "verified_at": None,
                "verified_sample_count": None,
                "notes": f"{existing['notes']}; {REASON}" if existing["notes"] else REASON,
            }
        )
        registry.set_capability(dataset_id, merged)
        cleared += 1
    registry.conn.commit()
    print(f"cleared the verification on {cleared} capability rows ({utc_now()[:10]})")
    registry.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
