"""Give each of the five Hornkoraller datasets its own species.

They share one WFS layer. The catalogue declares no layer, no filter and no
species for any of them, so this looked like a guess -- and it is not, because
the correspondence can be checked rather than assumed:

    the layer holds                 1,993 features
    distinct `art` values               5
    datasets on the layer               5
    title suffixes matching a value     5 of 5, exactly
    left over on either side            0

and the per-species counts match a **second, independent service**: the HI
GeoServer gives Paragorgia 853, Primnoa 453, Isidella 316, Paramuricea 252,
Radicipes 119, and so does `wfs.geonorge.no`.

**The filter must be the OGC form.** `CQL_FILTER=art='Radicipes'` returns
HTTP 200 and all 1,993 features -- accepted and ignored. Using it would store
the whole layer under each of the five datasets with a verified capability on
every one. So each request is checked before it is stored: the filtered count
must be smaller than the unfiltered total, and it must equal the tally taken
from the features themselves.

    scripts/apply_species_filters.py --dry-run
    scripts/apply_species_filters.py --apply
"""

from __future__ import annotations

import argparse
import re
import time
import urllib.request
from pathlib import Path

from public_data_agent.fetch import _fetch_wfs
from public_data_agent.registry import Registry
from public_data_agent.sources.wfs import (
    filtered_count_is_credible,
    hits_url_for,
    property_filter_url,
)

ADDRESS = "https://wfs.geonorge.no/skwms1/wfs.hornkoraller"
LAYER = "app:Hornkoraller"
FIELD = "art"
TITLE_PREFIX = "Hornkoraller - "
USER_AGENT = "public-data-agent (https://github.com/Solvelangseth/public-data-agent)"

# Counted from the features, and independently from the HI GeoServer. Held
# here so a filter that silently stops filtering is caught by the number
# rather than by someone noticing later.
EXPECTED = {
    "Paragorgia arborea": 853,
    "Primnoa resedaeformis": 453,
    "Isidella lofotensis": 316,
    "Paramuricea placomus": 252,
    "Radicipes": 119,
}
UNFILTERED_TOTAL = 1993


def _hits(url: str) -> int | None:
    request = urllib.request.Request(hits_url_for(url), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=90) as response:
        found = re.search(rb'numberMatched="(\d+)"', response.read(4000))
    return int(found.group(1)) if found else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/registry.sqlite")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--count", type=int, default=1000)
    args = parser.parse_args()

    registry = Registry(Path(args.db))
    try:
        rows = registry.conn.execute(
            "SELECT id, title FROM datasets WHERE title LIKE ? ORDER BY title",
            (TITLE_PREFIX + "%",),
        ).fetchall()
        if len(rows) != len(EXPECTED):
            raise SystemExit(
                f"{len(rows)} datasets titled '{TITLE_PREFIX}…' but {len(EXPECTED)} species "
                "are known; the bijection this rests on no longer holds"
            )
        for row in rows:
            species = row["title"][len(TITLE_PREFIX):].strip()
            if species not in EXPECTED:
                raise SystemExit(f"{row['title']!r} names no species this script knows")
            url = property_filter_url(ADDRESS, LAYER, FIELD, species, count=args.count)
            total = _hits(url)
            credible = filtered_count_is_credible(total, UNFILTERED_TOTAL)
            agrees = total == EXPECTED[species]
            mark = "ok" if (credible and agrees) else "REFUSED"
            print(f"  {species:24} filter -> {total!s:>5}  expected {EXPECTED[species]:>4}  {mark}")
            if not (credible and agrees):
                print("      not stored: a filter that does not reduce the count, or "
                      "reduces it to the wrong number, is not addressing this dataset")
                continue
            if not args.apply:
                continue
            dataset = {**dict(registry.get_dataset(row["id"])), "access_path": url}
            result = _fetch_wfs(registry, dataset)
            print(f"      stored {result.counts.listed} feature(s)")
            time.sleep(0.6)
        if not args.apply:
            print("\nnothing written; pass --apply")
    finally:
        registry.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
