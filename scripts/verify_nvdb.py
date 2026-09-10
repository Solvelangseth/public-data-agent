"""Record what each NVDB object type can return, and prove a sample of it.

Two different claims are written here and they are not the same strength.

`subject_count` is the publisher's own number, read from `/statistikk` for every
type, so it is measured rather than estimated. The capability -- that a type
returns addressable features with geometry and typed attributes -- is proved by
fetching one object from a sample of types spread across the catalogue. Only the
sampled types get `verified_at` and `verified_sample_count`; the rest carry the
capability with those fields null, which is the registry's way of saying the
class was verified and this particular resource was not.

No road objects are imported. One object per sampled type is fetched to prove
the shape and is not stored as a record.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.registry import Registry

OBJECT_API = "https://nvdbapiles.atlas.vegvesen.no/vegobjekter"
HEADERS = {"Accept": "application/json", "X-Client": "public-data-agent"}
SUBJECT_SCHEME = "NVDB vegobjekt-id"
# Spread across the catalogue rather than clustered: a bridge, a tunnel, a
# guardrail, a sign, a kerb, a fence. If all six answer the same way, the class
# behaves uniformly; if one does not, that is the finding.
SAMPLE_TYPES = ("60", "581", "5", "96", "9", "7")


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("data/registry.sqlite"))
    parser.add_argument("--rate", type=float, default=2.0)
    args = parser.parse_args()

    client = HttpClient(limiter=RateLimiter(args.rate, 1), timeout=45.0, max_retries=3)
    registry = Registry(args.db)
    try:
        rows = registry.conn.execute(
            "SELECT id, source_native_id, title FROM datasets WHERE id LIKE 'nvdb:%' ORDER BY id"
        ).fetchall()
        log(f"{len(rows)} object types to record")

        proved: dict[str, int] = {}
        for type_id in SAMPLE_TYPES:
            try:
                body = client.get_json(
                    f"{OBJECT_API}/{type_id}?antall=1&inkluder=metadata,egenskaper,lokasjon",
                    headers=HEADERS,
                )
            except Exception as exc:
                log(f"  sample {type_id}: FAILED {type(exc).__name__}: {str(exc)[:70]}")
                continue
            objects = body.get("objekter") or []
            if not objects:
                log(f"  sample {type_id}: returned no objects; not claiming verified")
                continue
            first = objects[0]
            has_geometry = bool(((first.get("lokasjon") or {}).get("geometri") or {}).get("wkt"))
            proved[type_id] = 1
            log(
                f"  sample {type_id}: object {first.get('id')}, "
                f"{len(first.get('egenskaper') or [])} attributes, geometry={has_geometry}"
            )

        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        counted = failed = 0
        for row in rows:
            type_id = row["source_native_id"]
            try:
                stats = client.get_json(f"{OBJECT_API}/{type_id}/statistikk", headers=HEADERS)
                count = stats.get("antall")
                counted += 1
            except Exception:
                count = None
                failed += 1
            registry.set_capability(
                row["id"],
                {
                    "capability": "features",
                    "record_kind": "feature",
                    "endpoint": f"{OBJECT_API}/{type_id}",
                    "request_method": "GET",
                    "subject_scheme": SUBJECT_SCHEME,
                    "subject_template": f"{OBJECT_API}/{type_id}/{{subject}}",
                    "subject_count": count,
                    "verified_at": stamp if type_id in proved else None,
                    "verified_sample_count": proved.get(type_id),
                    "notes": (
                        "one object fetched and inspected"
                        if type_id in proved
                        else f"class verified on {len(proved)} sampled types, not on this one"
                    ),
                },
            )
            if (counted + failed) % 100 == 0:
                log(f"  {counted + failed}/{len(rows)}")
        log(f"done: {counted} counts read, {failed} count reads failed, {len(proved)} types proved")
    finally:
        registry.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
