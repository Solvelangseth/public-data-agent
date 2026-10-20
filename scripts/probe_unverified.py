"""Ask each unverified resource what it actually does, and record the answer.

An unverified capability row says only that nobody checked. Probing them one
source at a time turned up six different situations hiding under that one
word, and they need different answers from the registry:

  verified    rows came back and the capability is read off them
  catalogue   the endpoint answers with the service describing itself; the
              data needs a different request, which is a wrong door rather
              than an empty room
  empty       the endpoint answers correctly and holds nothing
  restricted  the endpoint answers HTTP 401; the data is real, we are not
              authorised, and that is not the resource being broken
  withdrawn   the publisher reports the resource does not exist
  too large   the request works but exceeds a cell budget or the source's own
              limit; this needs a narrower selection, not a label
  unchanged   anything else, left alone rather than guessed at

Nothing is written for the last two. A probe that did not get a clear answer
must not leave one behind.
"""

from __future__ import annotations

import argparse
import time
from collections import Counter
from pathlib import Path

from public_data_agent.fetch import (
    CAPABILITY_CATALOGUE,
    CAPABILITY_EMPTY,
    CAPABILITY_RESTRICTED,
    CAPABILITY_WITHDRAWN,
    ServiceCatalogue,
    fetch_observations,
)
from public_data_agent.registry import Registry, utc_now

# Phrases the sources use for each situation, matched on the error a fetch
# raised rather than on a guess about the URL.
GONE_MARKS = ("ikke funnet", "not found", "non-existent", "does not exist")
EMPTY_MARKS = ("returned no objects", "printed no", "no rows", "returned no rows")
TOO_LARGE_MARKS = ("over the", "selection is", "cell budget")


def _verdict(error: Exception) -> str:
    # The catalogue case has its own exception type, so it is read from the
    # type rather than from the wording of a message.
    if isinstance(error, ServiceCatalogue):
        return "catalogue"
    message = str(error).casefold()
    if "http 401" in message or "http 403" in message:
        return "restricted"
    if any(mark in message for mark in EMPTY_MARKS):
        return "empty"
    if "http 404" in message or any(mark in message for mark in GONE_MARKS):
        return "withdrawn"
    if any(mark in message for mark in TOO_LARGE_MARKS):
        return "too large"
    return "unchanged"


CAPABILITY_FOR = {
    "catalogue": CAPABILITY_CATALOGUE,
    "empty": CAPABILITY_EMPTY,
    "restricted": CAPABILITY_RESTRICTED,
    "withdrawn": CAPABILITY_WITHDRAWN,
}

REASON = {
    "catalogue": (
        "the endpoint answered with the service describing itself; the data "
        "behind it needs a request no connector makes yet"
    ),
    "empty": "the endpoint answered and held no objects",
    "restricted": "the endpoint answered HTTP 401; the data is real and we are not authorised",
    "withdrawn": "the publisher reports this resource does not exist",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/registry.sqlite")
    parser.add_argument("--source", required=True, help="source prefix, e.g. nvdb")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--pause", type=float, default=1.5)
    parser.add_argument("--max-cells", type=int, default=500)
    args = parser.parse_args()

    registry = Registry(Path(args.db))
    rows = registry.conn.execute(
        "SELECT dataset_id FROM resource_capability WHERE verified_at IS NULL "
        "AND dataset_id LIKE ? ORDER BY dataset_id",
        (f"{args.source}:%",),
    ).fetchall()
    if not rows:
        print(f"no unverified {args.source} capability rows")
        return 0

    verdicts: dict[str, str] = {}
    for index, row in enumerate(rows):
        dataset_id = row["dataset_id"]
        try:
            result = fetch_observations(
                registry,
                dataset_id,
                table_id=dataset_id.split(":", 1)[1],
                max_cells=args.max_cells,
            )
        except Exception as error:  # the error is the evidence
            verdicts[dataset_id] = _verdict(error)
        else:
            # A fetch that stored rows records its own evidence now, so there
            # is nothing to write here beyond saying what happened.
            verdicts[dataset_id] = "verified" if result.counts.listed else "empty"
        if index + 1 < len(rows):
            time.sleep(args.pause)

    for verdict, count in Counter(verdicts.values()).most_common():
        named = " ".join(d for d, v in verdicts.items() if v == verdict)
        print(f"{verdict} ({count}): {named}")
    if not args.apply:
        print("\ndry run; pass --apply to record the decided verdicts.")
        return 0

    written = 0
    for dataset_id, verdict in verdicts.items():
        capability = CAPABILITY_FOR.get(verdict)
        if capability is None:
            continue
        existing = registry.get_capability(dataset_id)
        if existing is None or existing["verified_at"]:
            continue
        merged = {key: existing[key] for key in existing.keys() if key != "dataset_id"}
        note = f"{verdict} {utc_now()[:10]}: {REASON[verdict]}"
        merged.update(
            {
                "capability": capability,
                "notes": f"{existing['notes']}; {note}" if existing["notes"] else note,
            }
        )
        registry.set_capability(dataset_id, merged)
        written += 1
    registry.conn.commit()
    print(f"recorded {written} capability rows")
    registry.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
