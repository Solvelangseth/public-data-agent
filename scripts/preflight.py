"""Ask one resource per source what it returns, and store nothing.

`probe_unverified.py --apply` gates the verdict write and not the fetch, so a
"dry run" still fetched, still stored and still recorded a capability. That is
how 840 rows of Sokkeldirektoratet column definitions and 168 rows of Klass
version metadata got into the registry before anyone had read a payload.

This is the dry run that is actually dry. It fetches one sample per source
with urllib, runs the refusal rules the connectors already use, and prints a
verdict. Nothing is written anywhere, so it is safe to point at a source
nobody has looked at -- which is the whole point, because that is exactly
when the registry is at risk.

What it replaces is a person fetching a payload, printing it, reading it and
deciding. The rules below were each learned that way, one source at a time,
and every one of them is now a shape test:

    layers / services array      an ArcGIS service listing its own layers
    collections array            an OGC API listing its own collections
    fields and no features       one ArcGIS layer listing its own columns
    itemType / extent / crs      one OGC collection describing itself
    data and meta, no series     an SDMX structure message
    admin-only row keys          a change log: id, lastModified, owningSection

Usage:

    scripts/preflight.py --source sodir
    scripts/preflight.py --unprobed          # every source with no capability row
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

USER_AGENT = "public-data-agent (https://github.com/Solvelangseth/public-data-agent)"

# Keys a row carries when it is bookkeeping rather than content. A change log
# entry has an id and a timestamp and says nothing about the world.
ADMIN_KEYS = frozenset({
    "id", "uuid", "lastmodified", "last_modified", "sist-endret", "owningsection",
    "changetable", "version", "versions", "createdat", "updatedat", "modified",
    "published", "specversion", "url", "url-data", "uri", "self", "href",
})


def _get(url: str, timeout: float = 30.0) -> tuple[int, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(400_000)
            try:
                return response.status, json.loads(raw)
            except ValueError:
                return response.status, raw[:400].decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, None
    except Exception as error:  # a connection failure is not a verdict
        return 0, type(error).__name__


def classify(status: int, payload: Any, url: str) -> tuple[str, str]:
    """A verdict and the evidence for it. Nothing here writes or guesses."""

    if status in (401, 403):
        return "restricted", f"HTTP {status}: real data, not authorised"
    if status == 404:
        return "withdrawn", "HTTP 404: the publisher reports it does not exist"
    if status == 0:
        return "unreachable", f"the request did not complete ({payload})"
    if status != 200:
        return "unclear", f"HTTP {status}"
    lowered = url.casefold()
    if "service=wms" in lowered or "service=wfs" in lowered or "getcapabilities" in lowered:
        return "catalogue", "a WMS/WFS capabilities document: imagery, not rows"
    if not isinstance(payload, dict):
        if isinstance(payload, list):
            return "rows", f"a JSON array of {len(payload)} member(s)"
        # Not JSON at all. Showing the opening bytes is the difference between
        # a verdict a reader can act on and one that sends them to curl.
        snippet = " ".join(str(payload).split())[:70]
        return "unclear", f"not JSON: {snippet!r}"

    for key in ("layers", "services", "collections"):
        listed = payload.get(key)
        if isinstance(listed, list) and listed:
            return "catalogue", f"{len(listed)} {key}: the service's own table of contents"
    if isinstance(payload.get("fields"), list) and payload["fields"] and "features" not in payload:
        return "catalogue", f"{len(payload['fields'])} field definitions: its own columns"
    # An ArcGIS service descriptor with neither a layers array nor features:
    # `capabilities`, `currentVersion`, `cimVersion`, `archivingInfo`. Same
    # family as the two above, one rung up, and `hoydegis` reads this way.
    if "features" not in payload and {"capabilities", "currentVersion"} <= set(payload):
        return "catalogue", "an ArcGIS service descriptor: what it supports, not what it holds"
    if "features" not in payload and {"itemType", "storageCrs", "extent", "crs"} & set(payload):
        return "catalogue", "one collection describing itself, with no item in it"
    if set(payload) == {"data", "meta"} or ("meta" in payload and "data" in payload):
        data = payload.get("data")
        if isinstance(data, dict) and not (data.get("dataSets") or data.get("series")):
            inner = sorted(data)[:4]
            return "structure", f"an SDMX structure message, data holds {inner}"
    if url.rstrip("/").endswith("$metadata"):
        return "structure", "an OData $metadata document: the schema, not the rows"
    features = payload.get("features")
    if isinstance(features, list) and features:
        first = features[0] if isinstance(features[0], dict) else {}
        props = first.get("properties") if isinstance(first.get("properties"), dict) else {}
        if props and {str(k).casefold() for k in props} <= ADMIN_KEYS:
            return "bookkeeping", f"{len(features)} rows whose keys are all administrative"
        return "rows", f"{len(features)} feature(s) with {len(props)} published propert(y/ies)"
    return "unclear", f"keys: {sorted(payload)[:6]}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/registry.sqlite")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--unprobed", action="store_true",
                        help="every source where no dataset has a capability row")
    parser.add_argument("--pause", type=float, default=1.5)
    args = parser.parse_args()

    conn = sqlite3.connect(Path(args.db))
    conn.row_factory = sqlite3.Row
    sources = list(args.source)
    if args.unprobed:
        sources += [
            row["src"]
            for row in conn.execute(
                "SELECT substr(id, 1, instr(id, ':') - 1) AS src, "
                "SUM(CASE WHEN id IN (SELECT dataset_id FROM resource_capability) "
                "THEN 1 ELSE 0 END) AS known, COUNT(*) AS total "
                "FROM datasets GROUP BY src HAVING known = 0 AND total >= 3 "
                "ORDER BY total DESC"
            )
        ]
    if not sources:
        print("name a --source, or pass --unprobed")
        return 1

    width = max(len(s) for s in sources)
    for index, source in enumerate(sorted(set(sources))):
        row = conn.execute(
            "SELECT id, access_path FROM datasets WHERE id LIKE ? AND access_path IS NOT NULL "
            "ORDER BY id LIMIT 1",
            (f"{source}:%",),
        ).fetchone()
        total = conn.execute(
            "SELECT COUNT(*) FROM datasets WHERE id LIKE ?", (f"{source}:%",)
        ).fetchone()[0]
        if row is None:
            print(f"{source:{width}}  {total:5} datasets  no access_path to sample")
            continue
        status, payload = _get(row["access_path"])
        verdict, why = classify(status, payload, row["access_path"])
        print(f"{source:{width}}  {total:5} datasets  {verdict:12} {why}")
        print(f"{'':{width}}  sampled {row['id']}")
        if index + 1 < len(set(sources)):
            time.sleep(args.pause)
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
