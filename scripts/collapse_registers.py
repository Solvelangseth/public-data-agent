"""Collapse a per-instance source into one register dataset.

A register holding a million subjects filed as a million datasets makes the
catalogue the thing being searched rather than the index over it: search reads
every dataset row per query, 1.8s at 13,744 rows and about 146s at a million.
One dataset addressed by subject keeps the catalogue small and loses nothing --
the subjects are still reachable, by name rather than by enumeration.

Idempotent. Run it again and it reports what is already collapsed.
"""

from __future__ import annotations

import argparse
import sys

REGISTERS = {
    "brenheter": {
        "dataset_id": "brreg:enhetsregisteret",
        "title": "Enhetsregisteret — alle norske foretak og organisasjoner",
        "publisher": "Brønnøysundregistrene",
        "endpoint": "https://data.brreg.no/enhetsregisteret/api/enheter",
        "template": "https://data.brreg.no/enhetsregisteret/api/enheter/{subject}",
        "scheme": "brreg:orgnr",
        "count": 1_100_000,
    },
    "brunder": {
        "dataset_id": "brreg:underenheter",
        "title": "Enhetsregisteret — underenheter",
        "publisher": "Brønnøysundregistrene",
        "endpoint": "https://data.brreg.no/enhetsregisteret/api/underenheter",
        "template": "https://data.brreg.no/enhetsregisteret/api/underenheter/{subject}",
        "scheme": "brreg:orgnr",
        "count": 400_000,
    },
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/registry.sqlite")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from public_data_agent.registry import Registry, utc_now

    registry = Registry(args.db)
    try:
        for source_id, spec in REGISTERS.items():
            # The register carries the same source_id, so it must be excluded or
            # a second run would try to collapse it into itself.
            instances = [
                row["id"]
                for row in registry.conn.execute(
                    "SELECT id FROM datasets WHERE source_id = ? AND id != ?",
                    (source_id, spec["dataset_id"]),
                )
            ]
            print(f"{source_id}: {len(instances)} per-instance dataset(s) -> {spec['dataset_id']}")
            if args.dry_run:
                continue

            registry.conn.execute(
                """
                INSERT INTO datasets (id, source_id, ingest_reason, source_name,
                    source_endpoints_json, missing_fields_json, payload_hash,
                    first_ingested_at, last_ingested_at, last_seen_at, last_changed_at,
                    title, access_path, publisher_name)
                VALUES (?, ?, ?, ?, '[]', '{}', 'register', ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title, access_path = excluded.access_path,
                    last_seen_at = excluded.last_seen_at
                """,
                (spec["dataset_id"], source_id,
                 "one register addressed by subject, not one dataset per subject",
                 source_id, utc_now(), utc_now(), utc_now(), utc_now(),
                 spec["title"], spec["endpoint"], spec["publisher"]),
            )
            registry.set_capability(spec["dataset_id"], {
                "capability": "entities", "record_kind": "entity",
                "endpoint": spec["endpoint"], "request_method": "GET",
                "subject_scheme": spec["scheme"], "subject_template": spec["template"],
                "subject_count": spec["count"],
                "notes": f"collapsed from {len(instances)} per-instance dataset(s)",
            })
            # Records keep their subject, so nothing fetched is lost -- only the
            # catalogue row per subject goes.
            # Lineage moves with the records. A fetch run and its payload are the
            # proof of where a record came from, so they are re-pointed rather
            # than deleted -- dropping them would leave records whose provenance
            # names a dataset that no longer exists.
            CARRY = ("records", "fetch_runs", "harvested_payloads", "observations",
                     "enrichments", "raw_snapshots", "record_tombstones",
                     "crawl_checkpoints", "printed_table_urls")
            # The per-instance shape of these describes one subject and says
            # nothing about the register, so they are dropped and re-derived.
            DROP = ("resource_field_values", "resource_fields", "resource_keys",
                    "resource_capability", "embeddings")
            existing = {
                row["name"]
                for row in registry.conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            moved = 0
            for old in instances:
                for table in CARRY:
                    if table not in existing:
                        continue
                    try:
                        n = registry.conn.execute(
                            f"UPDATE {table} SET dataset_id = ? WHERE dataset_id = ?",
                            (spec["dataset_id"], old),
                        ).rowcount
                    except Exception:
                        continue
                    if table == "records":
                        moved += n
                for table in DROP:
                    if table in existing:
                        registry.conn.execute(
                            f"DELETE FROM {table} WHERE dataset_id = ?", (old,)
                        )
                registry.conn.execute("DELETE FROM datasets WHERE id = ?", (old,))
            registry.conn.commit()
            print(f"  moved {moved} record(s), removed {len(instances)} catalogue row(s)")
    finally:
        registry.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
