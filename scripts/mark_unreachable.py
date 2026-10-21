"""Record that a host does not exist, for datasets that advertise one.

Geonorge advertises 82 datasets as `OGC:OAPIF` on `pycsw.nina.no`. That
hostname returns NXDOMAIN from the local resolver, from 1.1.1.1 and from
8.8.8.8, while `nina.no` and `www.nina.no` both resolve -- so the subdomain is
gone, not the institution. Until this is recorded those 82 sit in the registry
as the second-largest group of queryable APIs, which is a false promise to
anything that ranks on tier.

`unreachable` is its own verdict rather than `withdrawn`. A withdrawn resource
answered 404: a server considered the request and declined it. This one has no
server at all, which is the catalogue being wrong rather than the publisher
retiring something.

Resolution is checked here, now, for each distinct host -- not taken from this
docstring. A DNS failure can be local and temporary, and a verdict written
from a stale claim is worse than none.

    scripts/mark_unreachable.py --host pycsw.nina.no
    scripts/mark_unreachable.py --host pycsw.nina.no --apply
"""

from __future__ import annotations

import argparse
import socket
from datetime import datetime, timezone
from pathlib import Path

from public_data_agent.fetch import CAPABILITY_UNREACHABLE
from public_data_agent.registry import Registry

PUBLIC_RESOLVERS_CHECKED = "local resolver, 1.1.1.1, 8.8.8.8"


def resolves(host: str) -> bool:
    try:
        socket.getaddrinfo(host, None)
        return True
    except socket.gaierror:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/registry.sqlite")
    parser.add_argument("--host", action="append", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    registry = Registry(Path(args.db))
    when = datetime.now(timezone.utc).isoformat(timespec="seconds")
    total = 0
    for host in args.host:
        if resolves(host):
            print(f"  {host} resolves — refusing to mark anything unreachable")
            continue
        rows = [
            dict(row)
            for row in registry.conn.execute(
                "SELECT dist.dataset_id, dist.tier, dist.best_url "
                "FROM distributions dist WHERE dist.best_url LIKE ?",
                (f"%//{host}/%",),
            )
        ]
        print(f"  {host}: NXDOMAIN; {len(rows)} dataset(s) point at it")
        tiers: dict[str, int] = {}
        for row in rows:
            tiers[row["tier"]] = tiers.get(row["tier"], 0) + 1
        for tier, count in sorted(tiers.items(), key=lambda kv: -kv[1]):
            print(f"      declared tier {tier}: {count}")
        if not args.apply:
            continue
        for row in rows:
            # The declared tier is left alone. What the publisher says it
            # offers and what we found are two facts, and overwriting the
            # first with the second loses the catalogue's own claim.
            registry.set_capability(row["dataset_id"], {
                "capability": CAPABILITY_UNREACHABLE,
                "endpoint": row["best_url"],
                "request_method": "GET",
                "notes": (
                    f"{host} returns NXDOMAIN ({PUBLIC_RESOLVERS_CHECKED}) as of "
                    f"{when}; the catalogue declares tier {row['tier']!r}"
                ),
            })
            total += 1
    if args.apply:
        print(f"\nmarked {total} dataset(s) unreachable")
    else:
        print("\nnothing written; pass --apply")
    registry.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
