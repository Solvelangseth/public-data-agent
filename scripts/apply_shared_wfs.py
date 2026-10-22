"""The shared-address datasets that a publisher statement can resolve.

27 datasets share a WFS address with another dataset, so "every layer on this
address is this dataset's" does not hold. Five were the Hornkoraller species,
settled by a verified bijection. These are the rest, and the honest answer for
most of them is no.

Two kinds of publisher statement resolve a dataset, and nothing else is
accepted:

    an exact layer title   `ogc.dsb.no` names its layers `ms:layer_183` and
                           titles them `Brannstasjoner`. The title is the
                           publisher's own name for the layer and it equals
                           the dataset's title exactly. 3 datasets.
    a declared layer       `ServiceDistributionNameForDataset` in the
                           catalogue. Null on 19 of 22 records, and on the 3
                           where it is set it names a layer on a DIFFERENT
                           service -- the Mareanoprøver datasets point at
                           `kart.hi.no`, not at the Geonorge WFS they share.
                           Worth following: a declaration about another
                           service is still a declaration. 3 datasets.

The other 16 get nothing. The Sårbare marine bunndyr group is the painful
one: 7 datasets and 8 layers whose titles nearly match -- six do, and the
seventh is `Bløtbunnkorallskog` against a layer called
`Bløtbunnskorallskog`, one letter apart. Almost certainly the same thing and
nothing says so, and a rule loose enough to join them is loose enough to join
things that are not. They stay unresolved until a publisher says otherwise.

    scripts/apply_shared_wfs.py --dry-run
    scripts/apply_shared_wfs.py --apply
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from public_data_agent.fetch import _fetch_wfs
from public_data_agent.registry import Registry
from public_data_agent.sources.wfs import getfeature_url, normalise_layer

# dataset title -> (service address, layer). Every row here is a publisher
# statement, named in the docstring above; none is a resemblance.
BY_EXACT_LAYER_TITLE = {
    "Brannstasjoner": ("https://ogc.dsb.no/wfs.ashx", "ms:layer_183"),
    "Interkommunale brannvesen": ("https://ogc.dsb.no/wfs.ashx", "ms:layer_179"),
    "Sivilforsvarsdistrikter": ("https://ogc.dsb.no/wfs.ashx", "ms:layer_185"),
}

BY_CATALOGUE_DECLARATION = {
    "Mareanoprøver Bomtrål - artsmangfold, individer og biomasse": (
        "https://kart.hi.no/mareano/mareano_biologi/bomtraal_arter/ows",
        "mareano_biologi/bomtraal_arter",
    ),
    "Mareanoprøver Grabb - artsmangfold, individer og biomasse": (
        "https://kart.hi.no/mareano/mareano_biologi/grabb_biomasse/ows",
        "mareano_biologi:grabb_biomasse",
    ),
    "Mareanoprøver Slede - artsmangfold, individer og biomasse": (
        "https://kart.hi.no/mareano/mareano_biologi/slede_individer/ows",
        "mareano_biologi/slede_individer",
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/registry.sqlite")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--count", type=int, default=1000)
    args = parser.parse_args()

    registry = Registry(Path(args.db))
    try:
        stored = failed = 0
        for basis, table in (("exact layer title", BY_EXACT_LAYER_TITLE),
                             ("catalogue declaration", BY_CATALOGUE_DECLARATION)):
            print(f"\n=== resolved by {basis}")
            for title, (address, layer) in table.items():
                row = registry.conn.execute(
                    "SELECT id FROM datasets WHERE title = ?", (title,)
                ).fetchone()
                if row is None:
                    print(f"  {title[:48]:50} no such dataset title; skipped")
                    continue
                url = getfeature_url(address, normalise_layer(layer), count=args.count)
                print(f"  {title[:48]:50} -> {normalise_layer(layer)}")
                if not args.apply:
                    continue
                dataset = {**dict(registry.get_dataset(row["id"])), "access_path": url}
                # kart.hi.no answers on the second attempt; it has done so
                # every one of the five times it failed on the first.
                for attempt in (1, 2, 3):
                    try:
                        result = _fetch_wfs(registry, dataset)
                        print(f"      stored {result.counts.listed} feature(s)")
                        stored += result.counts.listed
                        break
                    except Exception as error:
                        if attempt == 3:
                            failed += 1
                            print(f"      failed: {type(error).__name__}: {str(error)[:70]}")
                        else:
                            time.sleep(5 * attempt)
                time.sleep(0.6)
        if args.apply:
            print(f"\n{stored:,} feature(s) stored, {failed} dataset(s) failed")
        else:
            print("\nnothing written; pass --apply")
    finally:
        registry.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
