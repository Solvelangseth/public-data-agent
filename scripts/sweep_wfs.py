"""Fetch the layers of every WFS a dataset has to itself.

116 datasets in this registry declare a WFS and none had been asked, because
`fetch_observations` refused the protocol outright until the GetFeature door
was opened. This walks them through it.

**Which layers belong to a dataset is the whole problem**, and it is answered
by ownership rather than by matching names:

    85 datasets have their WFS address to themselves -> every layer on it is
       theirs. `wfs.aktsomhetskartforkvikkleireskred` serves
       `AktsomhetsOmrKvikkleireskred` and `KvikkleireskredAktsomhetDekning`,
       the areas and their coverage, and both are that dataset's.
    27 share an address with another dataset -> skipped. 5 Hornkoraller
       species datasets point at one layer that holds all species, and 5
       Fiskeridirektoratet datasets share a server holding 44 layers. The
       catalogue declares no layer for any of them -- checked, the field is
       null -- so attributing one would be a guess wearing a fetch's clothes.

Bounded: `--count` features per layer. What is stored is a verified sample,
which is what `verified_sample_count` has always meant here.

The layer's **true** size is not recorded yet, and saying so matters:
`wfs.geonorge.no` answers every GetFeature with `numberMatched="unknown"`
while returning features, so the only honest total comes from a separate
`resultType=hits` request. `sources/wfs.py` builds that URL and nothing calls
it. A first draft of this script had the function and never called it either,
which is the same dead-code shape as the `hierarchy_level` skip that claimed
to answer 34 of 45 download failures and never ran.

Retries matter. `kart.hi.no` layers time out on first contact and answer on
the second, twice observed, so a single failure is not a verdict.

    scripts/sweep_wfs.py --limit 3
    scripts/sweep_wfs.py
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from public_data_agent.fetch import _fetch_wfs
from public_data_agent.registry import Registry
from public_data_agent.sources.wfs import getfeature_url

DECLARATIONS = Path("discovery/geonorge_wfs.jsonl")


def plan(registry: Registry, caps_path: Path) -> tuple[list[dict[str, Any]], Counter[str]]:
    caps = {
        json.loads(line)["address"]: json.loads(line)
        for line in caps_path.read_text(encoding="utf-8").splitlines()
    }
    declarations = [
        json.loads(line)
        for line in DECLARATIONS.read_text(encoding="utf-8").splitlines()
    ]
    by_address: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for declaration in declarations:
        row = registry.conn.execute(
            "SELECT id FROM datasets WHERE access_path LIKE ?", (f"%{declaration['uuid']}",)
        ).fetchone()
        if row is None:
            continue
        declaration["dataset_id"] = row["id"]
        by_address[declaration["wfs_url"].split("?")[0]].append(declaration)

    work: list[dict[str, Any]] = []
    why: Counter[str] = Counter()
    for address, group in by_address.items():
        capability = caps.get(address)
        layers = (capability or {}).get("layers") or []
        if not capability or capability.get("error") or not layers:
            why["address did not answer"] += len(group)
            continue
        if len(group) > 1:
            why["address shared, no declared layer"] += len(group)
            continue
        work.append({
            "dataset_id": group[0]["dataset_id"],
            "title": group[0]["title"],
            "address": address,
            "layers": [layer["name"] for layer in layers if layer.get("name")],
        })
    return work, why


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/registry.sqlite")
    parser.add_argument("--caps", required=True, help="the GetCapabilities probe jsonl")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--count", type=int, default=500, help="features per layer")
    parser.add_argument("--pause", type=float, default=0.5)
    args = parser.parse_args()

    registry = Registry(Path(args.db))
    try:
        work, why = plan(registry, Path(args.caps))
        if args.limit:
            work = work[: args.limit]
        layers = sum(len(item["layers"]) for item in work)
        print(f"{len(work):,} dataset(s) own their address, {layers:,} layer(s) to read")
        for reason, n in why.most_common():
            print(f"  skipped {n:>3}: {reason}")
        print()

        stats: Counter[str] = Counter()
        stored = 0
        for index, item in enumerate(work, start=1):
            dataset = registry.get_dataset(item["dataset_id"])
            if dataset is None:
                stats["dataset vanished"] += 1
                continue
            got = 0
            empty: list[str] = []
            for layer in item["layers"]:
                url = getfeature_url(item["address"], layer, count=args.count)
                filled = {**dict(dataset), "access_path": url}
                for attempt in (1, 2, 3):
                    try:
                        result = _fetch_wfs(registry, filled)
                        got += result.counts.listed
                        stats["layer read"] += 1
                        break
                    except ValueError as error:
                        # An empty layer is a fact about the publisher, not a
                        # failure of ours, and counting it as one hides what
                        # it is. 40 of the first run's 41 "failures" were
                        # INSPIRE stub layers -- SpatialDataSet,
                        # AccessRestriction, MaintenanceAuthority, MarkerPost
                        # -- which these services publish empty by the
                        # schema's requirement. Retrying them is pointless and
                        # reporting them as broken sends someone to debug a
                        # service behaving exactly as specified.
                        if "no members" in str(error):
                            stats["layer empty"] += 1
                            empty.append(layer)
                        else:
                            stats[f"layer refused: {str(error)[:40]}"] += 1
                        break
                    except Exception as error:
                        if attempt == 3:
                            stats[f"layer failed: {type(error).__name__}"] += 1
                        else:
                            # kart.hi.no times out on first contact and
                            # answers afterwards, observed three times today.
                            time.sleep(args.pause * 6 * attempt)
                time.sleep(args.pause)
            stored += got
            stats["dataset read" if got else "dataset empty"] += 1
            if empty and got:
                # Said on the dataset, not only in the totals: a reader of
                # this registry should be able to see that a service offers
                # layers it serves nothing from.
                print(f"     {item['dataset_id']}: {len(empty)} empty layer(s): "
                      + ", ".join(name.split(":")[-1] for name in empty[:4]), flush=True)
            if index % 10 == 0 or index == len(work):
                print(f"  {index:,}/{len(work):,}  {stored:,} features  "
                      + ", ".join(f"{k}={v}" for k, v in sorted(stats.items())), flush=True)
            if index % 20 == 0:
                registry.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        print(f"\n{stored:,} feature record(s) stored")
        for key, value in sorted(stats.items()):
            print(f"  {key:34} {value:>5,}")
    finally:
        registry.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
