"""Fetch every completed lice week BarentsWatch publishes, one at a time.

773 `bwfish:*` datasets exist and three of them hold rows: the ingest source
listed the weeks, and nothing has asked for them. That makes the registry's
deepest-by-design vertical its thinnest in practice -- one weekly count of
adult female lice per locality, 2012 to now, is the series this whole source
was built for.

**Single-threaded on purpose.** BarentsWatch asks third parties not to run
parallel downloads and to use one thread, and warns that high load degrades
the service for everyone else. `--pause` is the gap between requests, not a
throttle to tune down.

Resumable: a week that already holds observations is skipped, so an
interrupted run continues where it stopped rather than refetching. Nothing is
deleted and nothing is retried in a loop -- a week that fails is reported with
its status and left for a human to look at, because a failure that repeats
silently is how a gap gets mistaken for an empty week.

    scripts/backfill_bwfish.py --limit 5        # try a handful first
    scripts/backfill_bwfish.py
"""

from __future__ import annotations

import argparse
import time
from collections import Counter
from pathlib import Path

from public_data_agent.fetch import fetch_observations
from public_data_agent.registry import Registry


def pending(registry: Registry, include_done: bool) -> list[str]:
    rows = registry.conn.execute(
        "SELECT d.id, (SELECT COUNT(*) FROM observations o WHERE o.dataset_id = d.id) n "
        "FROM datasets d WHERE d.source_id = 'bwfish' AND d.id LIKE 'bwfish:locality-%' "
        "ORDER BY d.id"
    ).fetchall()
    return [row["id"] for row in rows if include_done or not row["n"]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/registry.sqlite")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--pause", type=float, default=0.6)
    parser.add_argument("--refetch", action="store_true",
                        help="ask again for weeks that already hold rows")
    parser.add_argument("--checkpoint-every", type=int, default=25,
                        help="weeks between WAL checkpoints; 0 turns it off")
    args = parser.parse_args()

    registry = Registry(Path(args.db))
    try:
        weeks = pending(registry, args.refetch)
        if args.limit:
            weeks = weeks[: args.limit]
        print(f"{len(weeks):,} week(s) to ask for, {args.pause}s apart, one at a time")

        stats: Counter[str] = Counter()
        stored = 0
        failures: list[tuple[str, str]] = []
        for index, dataset_id in enumerate(weeks, start=1):
            try:
                result = fetch_observations(registry, dataset_id, table_id="")
            except Exception as error:  # noqa: BLE001 - reported, never swallowed
                stats["error"] += 1
                failures.append((dataset_id, f"{type(error).__name__}: {error}"))
                time.sleep(args.pause)
                continue
            written = result.counts.inserted + result.counts.updated
            stored += written
            if written:
                stats["stored"] += 1
            elif result.counts.listed == 0:
                # A week the publisher has no rows for. Real: lice reporting
                # has gaps, and an empty week is a fact about the week.
                stats["empty"] += 1
            else:
                stats["unchanged"] += 1
            if args.checkpoint_every and index % args.checkpoint_every == 0:
                # Measured, not precautionary. An unrelated 264,033-row write
                # left a 167 MB write-ahead log, and with it every commit here
                # slowed until the run stopped advancing entirely -- 65 weeks
                # in, no error, no output, the process asleep in a socket read
                # so it read as the publisher throttling us. BarentsWatch was
                # answering in 0.4s throughout. After one checkpoint the same
                # ten weeks took 11.8s.
                registry.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            if index % 25 == 0 or index == len(weeks):
                print(f"  {index:,}/{len(weeks):,}  {stored:,} rows  "
                      + ", ".join(f"{k}={v}" for k, v in sorted(stats.items())), flush=True)
            time.sleep(args.pause)

        print(f"\n{stored:,} observation row(s) stored")
        for key, value in sorted(stats.items()):
            print(f"  {key:10} {value:>5,}")
        if failures:
            print(f"\n{len(failures)} week(s) failed, first few:")
            for dataset_id, why in failures[:10]:
                print(f"  {dataset_id:28} {why[:90]}")
    finally:
        registry.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
