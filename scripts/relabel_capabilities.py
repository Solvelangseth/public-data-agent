"""Re-derive a verified capability from the rows its probe actually stored.

`record_evidence` hardcoded `capability = "observations"` for every resource
discovered by `pda verify --discover`, so the label said "returns numeric
cells" whatever came back. `crinst:1000` holds one cell -- `institution_name =
"AOF Haugaland"` -- and was filed as an observation source, which put an
organisation's name card in the lane whose job is answering numeric questions.

This reads every verified capability against `demonstrated_capability` and
rewrites only the ones its own stored rows contradict. A resource with nothing
stored is left alone: there is no evidence either way, and a label with no
evidence is what this is cleaning up.

    python scripts/relabel_capabilities.py             # report, change nothing
    python scripts/relabel_capabilities.py --apply     # write, after a backup
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from datetime import date
from pathlib import Path

from public_data_agent.registry import Registry
from public_data_agent.verify import demonstrated_capability


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/registry.sqlite")
    parser.add_argument("--apply", action="store_true", help="Write the changes")
    parser.add_argument(
        "--backup",
        default=f"data/relabelled_capabilities_{date.today().isoformat()}.json.gz",
        help="Where the rows as they were are written before any change",
    )
    args = parser.parse_args()

    registry = Registry(args.db)
    try:
        # Only the label the bug could write is re-derived. A connector's own
        # declaration knows what the cell shape cannot: `brkommuner:0301` is
        # declared `lookup` and stores an entity record, because BRREG's
        # municipality endpoint returns a thing whose role is a join key, not a
        # fact. Re-deriving that from its rows would call it `entities` and lose
        # the distinction the connector drew on purpose.
        rows = registry.conn.execute(
            "SELECT * FROM resource_capability "
            "WHERE verified_at IS NOT NULL AND capability = 'observations' "
            "ORDER BY dataset_id"
        ).fetchall()
        moves: Counter[tuple[str, str]] = Counter()
        changed: list[dict[str, object]] = []
        by_source: Counter[str] = Counter()
        for row in rows:
            dataset_id = row["dataset_id"]
            demonstrated = demonstrated_capability(registry, dataset_id)
            if demonstrated is None:
                continue
            capability, record_kind = demonstrated
            if capability == row["capability"]:
                continue
            moves[(row["capability"], capability)] += 1
            by_source[dataset_id.split(":", 1)[0]] += 1
            changed.append({
                "dataset_id": dataset_id,
                "was": {key: row[key] for key in row.keys()},
                "now": {"capability": capability, "record_kind": record_kind},
            })

        print(f"verified capabilities labelled observations: {len(rows)}")
        print(f"contradicted by their own rows: {len(changed)}")
        for (was, now), count in moves.most_common():
            print(f"  {was:14} -> {now:14} {count:6}")
        print("by source:", ", ".join(f"{s}={c}" for s, c in by_source.most_common(12)))

        if not args.apply:
            print("\nnothing written; pass --apply")
            return 0
        if not changed:
            return 0

        backup = Path(args.backup)
        backup.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(backup, "wt", encoding="utf-8") as handle:
            json.dump(changed, handle, ensure_ascii=False, indent=1)
        print(f"\nbacked up {len(changed)} rows to {backup}")

        for entry in changed:
            was = entry["was"]
            assert isinstance(was, dict)
            now = entry["now"]
            assert isinstance(now, dict)
            # Merge, never replace: `set_capability` writes every column, so a
            # partial write erases the endpoint, the subject addressing and the
            # verification itself.
            merged = {key: value for key, value in was.items() if key != "dataset_id"}
            merged["capability"] = now["capability"]
            merged["record_kind"] = now["record_kind"]
            note = f"relabelled {date.today().isoformat()}: was {was['capability']}, by stored rows"
            merged["notes"] = f"{was['notes']}; {note}" if was.get("notes") else note
            registry.set_capability(str(entry["dataset_id"]), merged)
        registry.conn.commit()
        print(f"rewrote {len(changed)} capabilities")
        return 0
    finally:
        registry.close()


if __name__ == "__main__":
    raise SystemExit(main())
