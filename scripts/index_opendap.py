"""Index what each THREDDS grid holds, so a search can find it by variable.

151 datasets in the registry resolve to `thredds.met.no` and the registry
knows nothing about them but a title. A search for "fordampning" or
"snømengde" cannot reach them, which is the whole breadth problem in one
source: the data is public, reachable, and invisible.

Two requests per dataset, no data transferred. The variables land in
`resource_fields`, which is the index retrieval already reads, with
`field_role` set to `measure` for the quantities and `period` or `geometry`
for the axes.

**No `observations` row is written for any of it.** These are 1 km climate
*projections* -- 1.85M cells per variable per time step -- and a projection is
not a measurement. Making them findable is the job; ingesting them would be
wrong twice over.

The resolved `best_url` ends in `.nc.html`, which is OPeNDAP's own HTML form
and returns HTML. Stripping that suffix gives the dataset, and `.dds` and
`.das` hang off it. All 151 end that way, so this is a rule rather than a
guess at one.

    scripts/index_opendap.py --limit 5
    scripts/index_opendap.py --apply
"""

from __future__ import annotations

import argparse
import sqlite3
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

from public_data_agent.opendap import (
    attributes_from_das,
    measured_variables,
    variables_from_dds,
)
from public_data_agent.registry import Registry

USER_AGENT = "public-data-agent (https://github.com/Solvelangseth/public-data-agent)"


def _get(url: str, cap: int = 400_000) -> str | None:
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=60
        ) as response:
            return response.read(cap).decode("utf-8", "replace")
    except urllib.error.HTTPError:
        return None
    except Exception:
        return None


def dataset_url(best_url: str) -> str:
    """The OPeNDAP dataset behind the form the catalogue pointed at."""

    return best_url[: -len(".html")] if best_url.endswith(".html") else best_url


def fields_for(dds: str, das: str) -> list[dict[str, object]]:
    """Variables as registry fields, with the role each one actually plays."""

    declared = variables_from_dds(dds)
    attributes = attributes_from_das(das)
    measured = {entry["name"]: entry for entry in measured_variables(declared, attributes)}
    fields: list[dict[str, object]] = []
    for variable in declared:
        name = str(variable["name"])
        attrs = attributes.get(name) or {}
        entry = measured.get(name)
        if entry is not None:
            role = "measure"
            label = entry.get("long_name") or attrs.get("units") or None
        elif attrs.get("axis") == "T" or attrs.get("standard_name") == "time":
            role = "period"
            label = attrs.get("units") or None
        else:
            # Everything else a grid declares is where the value sits: a
            # coordinate axis, a lat/lon array, or the CRS scalar.
            role = "geometry"
            label = attrs.get("long_name") or attrs.get("standard_name") or None
        fields.append({
            "field_code": name,
            "field_label": label,
            "field_role": role,
        })
    return fields


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/registry.sqlite")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--pause", type=float, default=0.5)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    read = sqlite3.connect(f"file:{Path(args.db)}?mode=ro", uri=True)
    read.row_factory = sqlite3.Row
    rows = [
        dict(row)
        for row in read.execute(
            "SELECT dataset_id, best_url FROM distributions "
            "WHERE best_url LIKE '%thredds.met.no%' ORDER BY dataset_id"
        )
    ]
    read.close()
    if args.limit:
        rows = rows[: args.limit]
    print(f"{len(rows):,} THREDDS dataset(s)")

    registry = Registry(Path(args.db)) if args.apply else None
    stats: Counter[str] = Counter()
    measures: Counter[str] = Counter()
    for index, row in enumerate(rows, start=1):
        base = dataset_url(row["best_url"])
        dds = _get(base + ".dds")
        if dds is None:
            stats["no .dds"] += 1
            time.sleep(args.pause)
            continue
        time.sleep(args.pause)
        das = _get(base + ".das") or "Attributes {\n}\n"
        try:
            fields = fields_for(dds, das)
        except ValueError as error:
            stats[f"unparsed: {error}"[:60]] += 1
            time.sleep(args.pause)
            continue
        named = [f for f in fields if f["field_role"] == "measure"]
        stats["indexed"] += 1
        stats["measures"] += len(named)
        for field in named:
            measures[str(field["field_code"])] += 1
        if registry is not None:
            registry.set_resource_shape(row["dataset_id"], fields=fields, keys=[])
        if index % 25 == 0 or index == len(rows):
            print(f"  {index:,}/{len(rows):,}  " +
                  ", ".join(f"{k}={v}" for k, v in sorted(stats.items()))[:140], flush=True)
        time.sleep(args.pause)

    print()
    for key, value in sorted(stats.items(), key=lambda kv: -kv[1]):
        print(f"  {key:46} {value:>6,}")
    print("\n  the most common measured variables:")
    for name, count in measures.most_common(12):
        print(f"    {count:>4}  {name}")
    if registry is not None:
        registry.close()
    else:
        print("\nnothing written; pass --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
