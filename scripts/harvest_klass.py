"""Download every Klass classification version, one file each.

Klass is SSB's own classification service, and it keeps every historical version
of each standard. The same code carries different names in different versions --
`2342` was "Førskolelærere" and is now "Førskole-/barnehagelærere" -- which makes
it a record of what SSB has called things, maintained by SSB, owing nothing to
any question set. That is the property that makes it usable as a vocabulary
source without spending the held-out set.

Meant to run unattended. Each version is written as its own file and an existing
file is never refetched, so a crash costs one request. The service answers in
roughly four seconds, so a full run is about an hour; that is why this is a
separate step and not part of an ingest.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from public_data_agent.http_util import HttpClient, RateLimiter

BASE = "https://data.ssb.no/api/klass/v1"


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("data/klass"))
    parser.add_argument("--rate", type=float, default=2.0)
    parser.add_argument("--db", type=Path, default=None,
                        help="Also build the alias vocabulary into this registry")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    versions_dir = args.out / "versions"
    versions_dir.mkdir(exist_ok=True)
    client = HttpClient(limiter=RateLimiter(rate=args.rate, burst=2))

    index_path = args.out / "classifications.json"
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
        log(f"reusing the classification index: {len(index)} classifications")
    else:
        listing = client.get_json(f"{BASE}/classifications?size=1000")
        index = {}
        entries = listing.get("_embedded", {}).get("classifications", [])
        for position, entry in enumerate(entries, 1):
            href = ((entry.get("_links") or {}).get("self") or {}).get("href", "")
            cid = href.rstrip("/").split("/")[-1]
            if not cid:
                continue
            detail = client.get_json(f"{BASE}/classifications/{cid}")
            index[cid] = {
                "name": entry.get("name"),
                "family": detail.get("classificationFamilyId"),
                "versions": [
                    {"id": v.get("id"), "name": v.get("name"), "validFrom": v.get("validFrom")}
                    for v in (detail.get("versions") or [])
                ],
            }
            if position % 25 == 0:
                index_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
                log(f"  index {position}/{len(entries)}")
        index_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")

    wanted = [
        (cid, str(version["id"]))
        for cid, entry in index.items()
        for version in entry.get("versions", [])
        if version.get("id") is not None
    ]
    todo = [(c, v) for c, v in wanted if not (versions_dir / f"{v}.json").exists()]
    log(f"{len(wanted)} versions, {len(wanted) - len(todo)} already on disk, {len(todo)} to fetch")

    started = time.time()
    failed = 0
    for position, (cid, version_id) in enumerate(todo, 1):
        try:
            payload = client.get_json(f"{BASE}/versions/{version_id}")
        except Exception as exc:  # a withdrawn version 404s; that is data, not a crash
            failed += 1
            log(f"  {version_id}: {type(exc).__name__}: {str(exc)[:80]}")
            (versions_dir / f"{version_id}.json").write_text(
                json.dumps({"classification_id": cid, "error": str(exc)[:200]}),
                encoding="utf-8",
            )
            continue
        payload["classification_id"] = cid
        (versions_dir / f"{version_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        if position % 20 == 0:
            rate = position / max(time.time() - started, 1)
            log(f"  {position}/{len(todo)}  {rate:.2f}/s  eta {(len(todo)-position)/max(rate,0.01)/60:.0f}m")
    log(f"done: {len(todo) - failed} fetched, {failed} failed")

    if args.db is not None:
        from public_data_agent.klass_vocabulary import build_vocabulary
        from public_data_agent.registry import Registry

        registry = Registry(args.db)
        try:
            log(str(build_vocabulary(registry, args.out, progress=log)))
        finally:
            registry.close()
        log("note: this vocabulary measured no change in retrieval; see the module docstring")
    return 0


if __name__ == "__main__":
    sys.exit(main())
