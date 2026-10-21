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

A resource with no capability row is included: that is 11,564 of 17,505
datasets, and selecting only rows already in `resource_capability` hid every
one of them from the tool meant to probe them.

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
    # A dataset with no capability row at all is the common case, not the edge
    # one: 11,564 of 17,505 have never been probed, and selecting only rows
    # already in `resource_capability` made every one of them invisible to the
    # tool built to probe them.
    rows = registry.conn.execute(
        "SELECT d.id AS dataset_id FROM datasets d "
        "LEFT JOIN resource_capability rc ON rc.dataset_id = d.id "
        "WHERE d.id LIKE ? AND (rc.dataset_id IS NULL OR rc.verified_at IS NULL) "
        "ORDER BY d.id",
        (f"{args.source}:%",),
    ).fetchall()
    if not rows:
        print(f"nothing left to probe for {args.source}")
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
        if existing is not None and existing["verified_at"]:
            continue
        note = f"{verdict} {utc_now()[:10]}: {REASON[verdict]}"
        if existing is None:
            # First verdict this resource has ever had. The endpoint is the
            # access path the probe actually used, so the row records what was
            # asked rather than what might be asked.
            dataset = registry.get_dataset(dataset_id) or {}
            merged = {"endpoint": dataset.get("access_path"), "notes": note}
        else:
            merged = {key: existing[key] for key in existing.keys() if key != "dataset_id"}
            merged["notes"] = f"{existing['notes']}; {note}" if existing["notes"] else note
        merged["capability"] = capability
        registry.set_capability(dataset_id, merged)
        written += 1
    registry.conn.commit()
    print(f"recorded {written} capability rows")
    registry.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
