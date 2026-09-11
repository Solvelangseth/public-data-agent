"""Prove what each Norges Bank dataflow returns, one bounded request each.

A dataflow classifies as `unverified` from its URL, which keeps it out of the
fetchable lane and is the right default. This discharges that by reading one
period from each flow and recording the capability from what came back.

Bounded on purpose: `lastNObservations=1` is the smallest request that still
proves the flow yields numeric cells. No history is imported.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from public_data_agent.fetch import fetch_observations
from public_data_agent.registry import Registry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("data/registry.sqlite"))
    args = parser.parse_args()

    registry = Registry(args.db)
    try:
        rows = registry.conn.execute(
            "SELECT id, title FROM datasets WHERE id LIKE 'norgesbank:%' ORDER BY id"
        ).fetchall()
        proved = failed = 0
        for row in rows:
            try:
                result = fetch_observations(
                    registry, row["id"], table_id="", select={"observations": ["1"]}
                )
            except Exception as exc:
                failed += 1
                print(f"  {row['id']:32} FAILED {type(exc).__name__}: {str(exc)[:60]}", flush=True)
                continue
            proved += 1
            print(
                f"  {row['id']:32} {result.counts.listed:4} cell(s)  "
                f"{(row['title'] or '')[:40]}",
                flush=True,
            )
            time.sleep(0.5)
        print(f"\n{proved} dataflows proved, {failed} failed")
    finally:
        registry.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
