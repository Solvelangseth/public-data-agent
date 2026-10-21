"""Write resolved Geonorge distributions into the registry.

`resolve_geonorge.py` asks the publisher what is behind each catalogue page
and writes JSON lines. This is the only step that writes to the registry, and
it writes to one table: `distributions`. It does not touch `datasets`,
`observations`, `records` or `resource_capability`.

That separation is the point. A `queryable-api` tier is the publisher saying
what it offers; a capability is a verdict earned by fetching rows. Letting the
first write the second is how a registry starts claiming things nobody checked
-- the mistake that put 840 ArcGIS field definitions in as verified entities.

The licence is recorded here too, but deliberately not copied onto
`datasets.license`. Comparing the raw strings reported 668 disagreements and
every one was the same permission in a different vocabulary -- the datanorge
harvest writes EU publications-office URIs, Geonorge writes the canonical
licence URL. `licences.same_licence` compares families instead, so what is
reported as a disagreement is one. Where they genuinely differ neither is
overwritten: preferring one harvest over the other without saying why is not
a decision a script should make.

    scripts/apply_geonorge.py --dry-run
    scripts/apply_geonorge.py --apply
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from public_data_agent.licences import licence_family, same_licence
from public_data_agent.registry import Registry

RESOLVED_FROM = "https://kartkatalog.geonorge.no/api/getdata/{uuid}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/registry.sqlite")
    parser.add_argument("--jsonl", default="discovery/geonorge_resolved.jsonl")
    parser.add_argument("--apply", action="store_true", help="without this, nothing is written")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    lines = Path(args.jsonl).read_text(encoding="utf-8").splitlines()
    rows: dict[str, dict] = {}
    for line in lines:
        if not line.strip():
            continue
        entry = json.loads(line)
        rows[entry["dataset_id"]] = entry  # a later resolution wins
    print(f"{len(lines):,} line(s), {len(rows):,} distinct dataset(s)")

    registry = Registry(Path(args.db))
    known = {row["id"] for row in registry.conn.execute("SELECT id FROM datasets")}
    missing = sorted(set(rows) - known)
    if missing:
        print(f"  {len(missing):,} resolved dataset(s) are not in the registry; skipping them")
        for dataset_id in missing[:5]:
            print(f"      {dataset_id}")

    tiers: Counter[str] = Counter()
    licence_new = licence_same = licence_differ = 0
    disagreements: list[tuple[str, str, str]] = []
    resolved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for dataset_id, entry in rows.items():
        if dataset_id not in known:
            continue
        tiers[entry["tier"]] += 1
        current = registry.get_dataset(dataset_id) or {}
        declared = entry.get("license_url")
        existing = current.get("license")
        if declared and not existing:
            licence_new += 1
        elif declared and existing and same_licence(existing, declared):
            licence_same += 1
        elif declared and existing:
            licence_differ += 1
            if len(disagreements) < 5:
                disagreements.append((dataset_id, existing, declared))
        if args.apply:
            registry.set_distribution(dataset_id, {**entry,
                                                   "resolved_from": RESOLVED_FROM,
                                                   "resolved_at": resolved_at})

    print("\ntiers " + ("written" if args.apply else "that would be written") + ":")
    for tier, count in sorted(tiers.items(), key=lambda kv: -kv[1]):
        print(f"  {tier:16} {count:>6,}")
    print("\nlicence, compared with what the harvest already carried:")
    print(f"  only the resolver has one   {licence_new:>6,}")
    print(f"  both agree                  {licence_same:>6,}")
    print(f"  they disagree               {licence_differ:>6,}  (neither is overwritten)")
    for dataset_id, existing, declared in disagreements:
        print(f"      {dataset_id}")
        print(f"        datasets.license {existing}  [{licence_family(existing)}]")
        print(f"        resolver         {declared}  [{licence_family(declared)}]")
    families = Counter(licence_family(e.get("license_url")) or "(unrecognised)"
                       for e in rows.values())
    print("\nlicence families the publishers point at:")
    for family, count in families.most_common():
        print(f"  {family:30} {count:>6,}")
    if args.apply:
        print(f"\nwritten. distributions now holds {sum(registry.distribution_counts().values()):,} row(s)")
    else:
        print("\nnothing written; pass --apply")
    registry.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
