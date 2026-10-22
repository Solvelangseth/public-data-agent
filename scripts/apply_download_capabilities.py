"""Write resolved download capabilities into the registry.

The only step here that writes. `resolve_download_capabilities.py` asks the
publisher what can be ordered; this records it on the `distributions` row the
catalogue resolution already created, and the kommuner and fylker it covers
into `dataset_coverage`.

It will not create a `distributions` row. Capabilities are details of a
distribution, and a dataset nobody has resolved should not acquire an access
tier from a side door.

    scripts/apply_download_capabilities.py --dry-run
    scripts/apply_download_capabilities.py --apply
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from public_data_agent.registry import Registry

DECLARED_BY = "https://nedlasting.geonorge.no/api/codelists/area/{uuid}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/registry.sqlite")
    parser.add_argument("--jsonl", default="discovery/download_capabilities.jsonl")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows: dict[str, dict] = {}
    for line in Path(args.jsonl).read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            rows[entry["dataset_id"]] = entry
    print(f"{len(rows):,} resolved dataset(s)")

    registry = Registry(Path(args.db))
    resolved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    stats: Counter[str] = Counter()
    coverage_rows = 0

    for dataset_id, entry in rows.items():
        if entry.get("error"):
            stats["errored"] += 1
            continue
        # A decided non-answer is not an answer of zero. 34 series parents, one
        # offline distribution and 10 datasets the download service has no
        # entry for carry no formats, no projections and no areas -- and
        # writing those through would publish "offers nothing, covers nowhere"
        # as the publisher's statement, when the publisher never made one.
        if entry.get("skipped"):
            stats[entry["skipped"].split(":", 1)[0]] += 1
            continue
        if entry.get("unregistered_download"):
            stats["declared but unregistered"] += 1
            continue
        if registry.get_distribution(dataset_id) is None:
            stats["no distributions row"] += 1
            continue
        stats["applied"] += 1
        formats = entry.get("formats") or []
        if "CSV" in formats:
            stats["offers CSV"] += 1
        if entry.get("access_constraint_required_role"):
            stats["needs a role"] += 1
        areas = entry.get("areas") or []
        if any(a.get("type") == "kommune" for a in areas):
            stats["lists kommuner"] += 1
        coverage_rows += len(areas)
        if args.apply:
            registry.set_download_options(dataset_id, {
                "formats": formats,
                "projections": entry.get("projections") or [],
                "nationwide": entry.get("nationwide"),
                "required_role": entry.get("access_constraint_required_role"),
                "grid_cell_count": (entry.get("area_types") or {}).get("celle"),
            })
            registry.set_coverage(dataset_id, areas,
                                  declared_by=DECLARED_BY, resolved_at=resolved_at)

    print("\n" + ("applied" if args.apply else "would apply") + ":")
    for key, value in sorted(stats.items(), key=lambda kv: -kv[1]):
        print(f"  {key:22} {value:>6,}")
    print(f"  {'coverage rows':22} {coverage_rows:>6,}")
    if args.apply:
        total = registry.conn.execute("SELECT COUNT(*) FROM dataset_coverage").fetchone()[0]
        places = registry.conn.execute(
            "SELECT COUNT(DISTINCT area_code) FROM dataset_coverage WHERE area_type='kommune'"
        ).fetchone()[0]
        print(f"\ndataset_coverage holds {total:,} row(s) over {places:,} kommune(r)")
    else:
        print("\nnothing written; pass --apply")
    registry.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
