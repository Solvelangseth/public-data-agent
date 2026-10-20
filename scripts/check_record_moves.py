"""Re-derive every moved row and compare it with what is stored.

Each migration converted stored cells through the same function the connector
calls. That function has since been corrected twice -- once for which field is
a row's identity, once for which side of the cell it may come from -- and a
correction made after a move leaves the rows that moved earlier in the old
shape, silently.

So the check: read each backup, convert it with today's rules, and compare
against the records in the registry. A mismatch names the dataset and what
differs, and is not repaired here -- re-running the move for that source is
the repair, and it should be a decision rather than a side effect.
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from public_data_agent.registry import Registry

from move_name_cards_to_records import SHAPES
from public_data_agent.entity_records import records_from_cells

BACKUPS = (
    "data/cristin_observations_backup.json.gz",
    "data/entur_grep_observations_backup.json.gz",
    "data/hi_observations_backup.json.gz",
    "data/brreg_env_observations_backup.json.gz",
    "data/norgesbank_observations_backup.json.gz",
    "data/tail_observations_backup.json.gz",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/registry.sqlite")
    parser.add_argument("--backups", nargs="*", default=list(BACKUPS))
    args = parser.parse_args()

    registry = Registry(Path(args.db))
    checked = 0
    stale: dict[str, int] = {}
    missing: dict[str, int] = {}
    for path in args.backups:
        if not Path(path).exists():
            print(f"missing backup {path}")
            continue
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            rows = json.load(handle)
        groups: dict[tuple[str, str], list[dict]] = {}
        for row in rows:
            groups.setdefault((row["dataset_id"], row["table_id"]), []).append(row)
        for (dataset_id, table_id), group in groups.items():
            shape = SHAPES.get(dataset_id.split(":")[0])
            if shape is None:
                continue
            id_fields, label_fields, prefix, kind = shape
            cells = [
                (
                    row["measure"],
                    json.loads(row["value_json"]) if row["value_json"] is not None else None,
                    json.loads(row["dimensions_json"] or "{}"),
                )
                for row in group
            ]
            expected = records_from_cells(
                cells,
                dataset_id=dataset_id,
                table_id=table_id,
                id_fields=id_fields,
                label_fields=label_fields,
                prefix=prefix,
                kind=kind,
            )
            stored = {
                row["id"]: row
                for row in registry.list_records(dataset_id)
            }
            for record in expected:
                checked += 1
                found = stored.get(record["id"])
                if found is None:
                    missing[dataset_id] = missing.get(dataset_id, 0) + 1
                elif (
                    found["subject_code"] != record["subject_code"]
                    or found["subject_label"] != record["subject_label"]
                    or found["kind"] != record["kind"]
                ):
                    stale[dataset_id] = stale.get(dataset_id, 0) + 1
    registry.close()

    print(f"checked {checked} moved rows")
    for dataset_id, count in sorted(missing.items(), key=lambda kv: -kv[1]):
        print(f"  no record with the id today's rules give: {dataset_id} ({count})")
    for dataset_id, count in sorted(stale.items(), key=lambda kv: -kv[1]):
        print(f"  stored record differs from today's rules: {dataset_id} ({count})")
    if missing or stale:
        print("\nre-run the move for those sources to bring them up to date")
        return 1
    print("every moved row matches what the current rules would write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
