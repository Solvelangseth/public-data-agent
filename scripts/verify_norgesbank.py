"""Prove what each Norges Bank dataflow returns, one bounded request each.

Observation flows (IR, EXR, SHORT_RATES, and the other leftover SDMX
series that print measure names) classify as `observations` from the URL.
Calendars and wide dumps stay `unverified` until a bounded fetch records
cells. This script still reads one period from each flow and records the
capability from what came back.

Every flow's series dimensions are indexed first, from `detail=serieskeysonly`,
which lists the codes that occur without any observations. That is what makes a
flow too wide to read whole still provable: MONEY_MARKET answers a one-period
request with 34,906 cells, so it is narrowed to one real series -- the first one
the flow lists -- and read that way instead. Dimensions whose codes cannot sit in
an SDMX key (GOVT_PRIMARY_MARKET's COUPON is "0.00000000") are left as
wildcards.

Bounded throughout. No history is imported.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

from public_data_agent.fetch import SelectionTooLarge, fetch_observations
from public_data_agent.http_util import HttpClient
from public_data_agent.registry import Registry
from public_data_agent.resource_index import index_dataset

KEY_SAFE = re.compile(r"^[A-Za-z0-9_-]+$")


def first_series_selection(client: HttpClient, access_path: str) -> dict[str, list[str]]:
    """Per-dimension codes of the first series a flow lists, key-safe codes only."""

    separator = "&" if "?" in access_path else "?"
    body = client.get_json(f"{access_path}{separator}detail=serieskeysonly")
    data = body["data"]
    dims = data["structure"]["dimensions"]["series"]
    first = next(iter(data["dataSets"][0].get("series") or {}))
    selection: dict[str, list[str]] = {}
    for dim, index in zip(dims, first.split(":")):
        code = dim["values"][int(index)]["id"]
        if KEY_SAFE.match(code):
            selection[dim["id"]] = [code]
    return selection


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("data/registry.sqlite"))
    args = parser.parse_args()

    client = HttpClient(timeout=60.0, max_retries=3)
    registry = Registry(args.db)
    try:
        rows = registry.conn.execute(
            "SELECT id, title, access_path FROM datasets WHERE id LIKE 'norgesbank:%' ORDER BY id"
        ).fetchall()
        whole = narrowed = failed = 0
        for row in rows:
            try:
                shape = index_dataset(registry, row["id"], http=client)
            except Exception as exc:
                failed += 1
                print(f"  {row['id']:32} SHAPE FAILED {type(exc).__name__}: {str(exc)[:56]}", flush=True)
                continue
            try:
                result = fetch_observations(
                    registry, row["id"], table_id="", select={"observations": ["1"]}
                )
                whole += 1
                how = "whole flow"
            except SelectionTooLarge:
                selection = first_series_selection(client, row["access_path"])
                try:
                    result = fetch_observations(
                        registry, row["id"], table_id="",
                        select={**selection, "observations": ["1"]},
                    )
                except Exception as exc:
                    failed += 1
                    print(f"  {row['id']:32} NARROWED READ FAILED {type(exc).__name__}: {str(exc)[:48]}", flush=True)
                    continue
                narrowed += 1
                how = f"narrowed on {len(selection)} of {shape['fields']} dimensions"
            except Exception as exc:
                failed += 1
                print(f"  {row['id']:32} FAILED {type(exc).__name__}: {str(exc)[:60]}", flush=True)
                continue
            print(
                f"  {row['id']:32} {result.counts.listed:4} cell(s)  {how:34} "
                f"{(row['title'] or '')[:30]}",
                flush=True,
            )
            time.sleep(0.5)
        print(f"\n{whole} read whole, {narrowed} proved by narrowing, {failed} failed")
    finally:
        registry.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
