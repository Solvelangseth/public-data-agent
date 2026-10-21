"""Find the door that returns rows, and write down what was behind it.

This is the crawl lane's tool. It is deliberately separate from the registry:
it opens `registry.sqlite` **read-only**, writes nothing to it, and appends
its findings to a JSONL file that the registry lane reads and decides on. Two
sessions can therefore run at once without a write conflict on a 2 GB SQLite
file, and a mistake here cannot corrupt anything.

The job is not "discover APIs" in the abstract. It is the problem this project
keeps meeting:

    the registry lists 8,416 datasets with no licence and 78 with a verdict
    that is not `observations`, and a large share of those are not closed --
    they are a landing page, a service descriptor or a capabilities document
    sitting where an endpoint should be. The data is public, reachable, and
    one declared link away.

So the default mode walks those rows, reads **what the payload itself
declares**, and follows it. An ArcGIS service lists its layers; an OGC API
lists its collections and gives each an `items` link; an OpenAPI document
lists its paths and its servers. Following a declared link is reading. The
second mode guesses at well-known paths (`/swagger/v1/swagger.json` and
friends), which is not reading, so every candidate records `how` and a guess
is never presented as a declaration.

What it never does: store anything in the registry, fetch at more than the
configured rate, or decide that a candidate is worth a connector. The last one
is a judgement for whoever reads the file.

    scripts/discover.py --source vegvesen              # one source
    scripts/discover.py --unreadable --limit 200       # every dataset with no verdict
    scripts/discover.py --catalogues                   # seed catalogues, new hosts only
    scripts/discover.py --url https://example.no/api   # one url, nothing stored
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
import urllib.error
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

USER_AGENT = "public-data-agent discovery (https://github.com/Solvelangseth/public-data-agent)"
DEFAULT_OUT = Path("discovery/candidates.jsonl")

# Paths a publisher very often serves but rarely links to. Trying these is a
# guess, and candidates found this way are marked `probed:` so a reader can
# weigh them differently from a link the payload declared.
WELL_KNOWN = (
    "swagger/v1/swagger.json",
    "openapi.json",
    "api-docs",
    "v3/api-docs",
    "?f=json",
    "collections?f=json",
)

# Keys that mean "this is the service describing itself", borrowed from
# scripts/preflight.py so the two tools agree on what a catalogue looks like.
CATALOGUE_KEYS = ("layers", "services", "collections")

SEED_CATALOGUES = {
    "elhub": "https://api.elhub.no/energy-data/v0/price-areas",
    "vannmiljo": "https://vannmiljowebapi.miljodirektoratet.no/api/Public/GetWaterLocations",
    "mattilsynet-lakselus": "https://www.mattilsynet.no/api/v1/lakselus",
    "artsdatabanken": "https://data.artsdatabanken.no/",
    "kulturminnesok": "https://kulturminnesok.no/api/",
    "doffin": "https://api.doffin.no/public/v2/search",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- fetching ---------------------------------------------------------------


class Fetcher:
    """One GET at a polite rate, with the body capped and never stored."""

    def __init__(self, *, pause: float = 1.0, timeout: float = 30.0, cap: int = 2_000_000) -> None:
        self.pause = pause
        self.timeout = timeout
        self.cap = cap
        self._last = 0.0
        self.count = 0

    def get(self, url: str) -> tuple[int, Any, str]:
        wait = self.pause - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        self.count += 1
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(self.cap)
                try:
                    return response.status, json.loads(raw), ""
                except ValueError:
                    # A body larger than the cap lands mid-token. Calling that
                    # "not JSON" buries exactly the endpoints worth finding:
                    # a FeatureCollection of 88,861 rows reads as a failure.
                    return response.status, None, raw.decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            return error.code, None, ""
        except Exception as error:
            return 0, None, type(error).__name__


# --- classifying ------------------------------------------------------------


def classify(status: int, payload: Any, url: str, note: str) -> tuple[str, str]:
    """A verdict and its evidence. Same vocabulary as scripts/preflight.py."""

    if status in (401, 403):
        return "restricted", f"HTTP {status}: real data, not authorised"
    if status == 404:
        return "withdrawn", "HTTP 404"
    if status == 0:
        return "unreachable", note or "the request did not complete"
    if status != 200:
        return "unclear", f"HTTP {status}"
    lowered = url.casefold()
    if "service=wms" in lowered or "getcapabilities" in lowered:
        return "catalogue", "a capabilities document: imagery, not rows"
    if payload is None:
        body = note.lstrip()
        if body[:1] in ("{", "["):
            counted = _counts_in_prefix(body)
            if counted:
                return "rows", f"{counted} (read from a prefix; the body exceeds the cap)"
            return "rows-truncated", (
                "the body is JSON and larger than the read cap, so it could not be "
                f"parsed here: {' '.join(body.split())[:70]}"
            )
        return "unclear", f"not JSON: {' '.join(body.split())[:80]!r}"
    if isinstance(payload, list):
        if not payload:
            return "empty", "an empty JSON array"
        first = payload[0] if isinstance(payload[0], dict) else None
        return "rows", f"{len(payload)} member(s)" + (
            f", keys {sorted(first)[:8]}" if first else ""
        )
    if not isinstance(payload, dict):
        return "unclear", f"a bare {type(payload).__name__}"
    # ArcGIS answers HTTP 200 and puts the failure in the body. Reporting that
    # as "unclear" hides the reason, which is usually actionable: a layer that
    # does not support query says so in words.
    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message") or error.get("description") or ""
        details = error.get("details")
        if isinstance(details, list) and details:
            message = f"{message} {details[0]}".strip()
        return "service-error", f"HTTP 200 with an error body: {str(message)[:90]!r}"
    if "paths" in payload and isinstance(payload.get("paths"), dict):
        return "openapi", f"{len(payload['paths'])} documented path(s)"
    for key in CATALOGUE_KEYS:
        listed = payload.get(key)
        if isinstance(listed, list) and listed:
            return "catalogue", f"{len(listed)} {key}: a table of contents"
    if isinstance(payload.get("fields"), list) and "features" not in payload:
        return "catalogue", f"{len(payload['fields'])} field definitions"
    if "features" not in payload and {"capabilities", "currentVersion"} <= set(payload):
        return "catalogue", "an ArcGIS service descriptor"
    features = payload.get("features")
    if isinstance(features, list):
        if not features:
            return "empty", "a feature collection with no feature in it"
        first = features[0] if isinstance(features[0], dict) else {}
        # GeoJSON puts the fields under `properties`; ArcGIS `f=json` puts them
        # under `attributes`. Reading only the first reported every ArcticSDI
        # layer as "0 properties", which reads like an empty service and would
        # have had a reader skip eight queryable layers.
        fields = first.get("properties")
        if not isinstance(fields, dict) or not fields:
            fields = first.get("attributes")
        fields = fields if isinstance(fields, dict) else {}
        named = ", ".join(sorted(fields)[:6])
        return "rows", (
            f"{len(features)} feature(s), {len(fields)} published field(s)"
            + (f": {named}" if named else " -- geometry only, no attributes")
        )
    for key, value in payload.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return "rows", f"{key}[{len(value)}], keys {sorted(value[0])[:8]}"
    return "unclear", f"keys {sorted(payload)[:8]}"


# Counts a publisher prints near the top of a long response. Reading them
# from a truncated prefix is not parsing the document; it is reading the one
# number the document leads with, and the verdict says where it came from.
_COUNT_KEYS = ("numberMatched", "numberReturned", "totalItemCount", "itemCount", "totalFeatures")


def _counts_in_prefix(body: str) -> str:
    found = []
    for key in _COUNT_KEYS:
        match = re.search(rf'"{key}"\s*:\s*(\d+)', body[:4000])
        if match:
            found.append(f"{key}={match.group(1)}")
    return ", ".join(found)


def declared_license(payload: Any) -> str | None:
    """A licence the payload states about itself. Never inferred."""

    if not isinstance(payload, dict):
        return None
    for key in ("license", "licence", "licenseUrl", "rights"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip().startswith("http"):
            return value.strip()
        if isinstance(value, dict):
            inner = value.get("url") or value.get("href")
            if isinstance(inner, str) and inner.strip().startswith("http"):
                return inner.strip()
    return None


# --- following what a payload declares --------------------------------------


def declared_doors(payload: Any, url: str) -> list[tuple[str, str]]:
    """(candidate url, how) for every next step the payload itself names.

    Only links the response prints. Composing an ArcGIS layer query from a
    declared layer id is the one construction here, and it is the documented
    form for a resource the service just told us it has.
    """

    doors: list[tuple[str, str]] = []
    if not isinstance(payload, dict):
        return doors
    base = url.split("?")[0].rstrip("/")

    collections = payload.get("collections")
    if isinstance(collections, list):
        for collection in collections[:40]:
            if not isinstance(collection, dict):
                continue
            for link in collection.get("links") or []:
                if not isinstance(link, dict):
                    continue
                if link.get("rel") == "items" and str(link.get("type", "")).startswith(
                    "application/geo+json"
                ) or (link.get("rel") == "items" and link.get("type") == "application/json"):
                    href = link.get("href")
                    if isinstance(href, str) and href.startswith("http"):
                        joiner = "&" if "?" in href else "?"
                        doors.append((f"{href}{joiner}limit=5", "declared:ogc-items"))
                        break

    layers = payload.get("layers")
    if isinstance(layers, list):
        for layer in layers[:40]:
            if not isinstance(layer, dict):
                continue
            layer_id = layer.get("id")
            if layer_id is None:
                continue
            # A group layer holds other layers and cannot be queried. It
            # declares that by printing subLayerIds, so skipping it is reading
            # the descriptor rather than learning from an error.
            if layer.get("subLayerIds"):
                continue
            # No resultRecordCount. Older ArcGIS servers answer
            # "Pagination is not supported" to it and the whole layer then
            # looks broken -- npolar's ArcticSDI did, for every layer, until
            # the parameter came off. Size is handled by the read cap and the
            # rows-truncated verdict instead.
            doors.append((
                f"{base}/{layer_id}/query?where=1%3D1&outFields=*&returnGeometry=false&f=json",
                "declared:arcgis-layer",
            ))

    services = payload.get("services")
    if isinstance(services, list):
        for service in services[:20]:
            if isinstance(service, dict) and isinstance(service.get("name"), str):
                kind = service.get("type", "MapServer")
                doors.append((f"{base}/{service['name']}/{kind}?f=json", "declared:arcgis-service"))

    paths = payload.get("paths")
    if isinstance(paths, dict):
        servers = payload.get("servers")
        origin = ""
        if isinstance(servers, list) and servers and isinstance(servers[0], dict):
            declared = servers[0].get("url")
            if isinstance(declared, str) and declared.startswith("http"):
                origin = declared.rstrip("/")
        if not origin:
            parts = urllib.parse.urlsplit(url)
            origin = f"{parts.scheme}://{parts.netloc}"
        for path, item in list(paths.items())[:40]:
            if not isinstance(path, str) or "{" in path or not isinstance(item, dict):
                continue
            if "get" not in item:
                continue
            doors.append((origin + path, "declared:openapi-path"))

    for link in payload.get("links") or []:
        if isinstance(link, dict) and link.get("rel") in ("items", "data"):
            href = link.get("href")
            if isinstance(href, str) and href.startswith("http"):
                doors.append((href, "declared:link"))

    seen: set[str] = set()
    unique = []
    for candidate, how in doors:
        if candidate not in seen:
            seen.add(candidate)
            unique.append((candidate, how))
    return unique


def probed_doors(url: str) -> list[tuple[str, str]]:
    """Well-known paths nobody linked to. A guess, and labelled one."""

    parts = urllib.parse.urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    base = url.split("?")[0].rstrip("/")
    out = []
    for suffix in WELL_KNOWN:
        if suffix.startswith("?"):
            out.append((base + suffix, f"probed:{suffix}"))
        else:
            out.append((f"{origin}/{suffix}", f"probed:{suffix}"))
            if base != origin:
                out.append((f"{base}/{suffix}", f"probed:{suffix}"))
    seen: set[str] = set()
    return [(u, h) for u, h in out if not (u in seen or seen.add(u))]


# --- the registry, read-only ------------------------------------------------


def open_registry(path: Path) -> sqlite3.Connection:
    """Read-only, so this tool cannot write to a registry another session owns."""

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def unreadable_rows(conn: sqlite3.Connection, *, source: str | None, limit: int) -> list[sqlite3.Row]:
    """Datasets the registry cannot currently read a row from."""

    sql = """
        SELECT d.id, d.title, d.access_path,
               substr(d.id, 1, instr(d.id, ':') - 1) AS source_id,
               rc.capability
        FROM datasets d
        LEFT JOIN resource_capability rc ON rc.dataset_id = d.id
        WHERE d.access_path IS NOT NULL
          AND (rc.capability IS NULL
               OR rc.capability NOT IN ('observations','entities','features','documents'))
    """
    args: list[Any] = []
    if source:
        sql += " AND d.id LIKE ?"
        args.append(f"{source}:%")
    # One dataset per host is enough to learn what a host does, and it is the
    # difference between 200 requests and 8,000.
    sql += " GROUP BY source_id, rc.capability ORDER BY d.id LIMIT ?"
    args.append(limit)
    return list(conn.execute(sql, args))


def known_hosts(conn: sqlite3.Connection) -> set[str]:
    hosts = set()
    for row in conn.execute(
        "SELECT DISTINCT access_path FROM datasets WHERE access_path LIKE 'http%'"
    ):
        hosts.add(urllib.parse.urlsplit(row["access_path"]).netloc.casefold())
    return hosts


# --- the walk ---------------------------------------------------------------


def investigate(
    fetcher: Fetcher,
    url: str,
    *,
    dataset_id: str | None,
    source_id: str | None,
    depth: int,
    probe: bool,
) -> Iterator[dict[str, Any]]:
    """Report what `url` is, then what the doors it declares are."""

    status, payload, note = fetcher.get(url)
    verdict, evidence = classify(status, payload, url, note)
    yield {
        "found_at": utc_now(),
        "dataset_id": dataset_id,
        "source_id": source_id,
        "url": url,
        "how": "registry:access_path" if depth == 0 else "followed",
        "verdict": verdict,
        "evidence": evidence,
        "license_declared": declared_license(payload),
        "depth": depth,
    }
    if depth >= 2 or verdict in ("rows", "rows-truncated", "restricted", "withdrawn", "unreachable"):
        return
    doors = declared_doors(payload, url)
    if probe and not doors and verdict in ("unclear", "empty", "catalogue"):
        doors = probed_doors(url)
    for candidate, how in doors[:8]:
        status, inner, note = fetcher.get(candidate)
        inner_verdict, inner_evidence = classify(status, inner, candidate, note)
        yield {
            "found_at": utc_now(),
            "dataset_id": dataset_id,
            "source_id": source_id,
            "url": candidate,
            "how": how,
            "verdict": inner_verdict,
            "evidence": inner_evidence,
            "license_declared": declared_license(inner),
            "depth": depth + 1,
            "behind": url,
        }
        if inner_verdict in ("catalogue", "openapi") and depth + 1 < 2:
            yield from investigate(
                fetcher, candidate, dataset_id=dataset_id, source_id=source_id,
                depth=depth + 2, probe=False,
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/registry.sqlite")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--source", help="one registry source id, e.g. vegvesen")
    parser.add_argument("--unreadable", action="store_true",
                        help="walk datasets the registry cannot read a row from")
    parser.add_argument("--catalogues", action="store_true",
                        help="walk the seed list, skipping hosts the registry already knows")
    parser.add_argument("--url", help="investigate one url and write nothing to the registry")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--pause", type=float, default=1.0)
    parser.add_argument("--probe", action="store_true",
                        help="also try well-known paths nobody linked to; marked probed:")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fetcher = Fetcher(pause=args.pause)
    written = 0
    verdicts: dict[str, int] = {}

    with out_path.open("a", encoding="utf-8") as sink:
        def record(entry: dict[str, Any]) -> None:
            nonlocal written
            sink.write(json.dumps(entry, ensure_ascii=False) + "\n")
            sink.flush()
            written += 1
            verdicts[entry["verdict"]] = verdicts.get(entry["verdict"], 0) + 1
            mark = "  <-- rows" if entry["verdict"].startswith("rows") else ""
            print(f"  {entry['verdict']:12} {entry['how']:24} {entry['url'][:78]}{mark}")

        if args.url:
            for entry in investigate(fetcher, args.url, dataset_id=None, source_id=None,
                                     depth=0, probe=args.probe):
                record(entry)
        elif args.catalogues:
            conn = open_registry(Path(args.db))
            already = known_hosts(conn)
            conn.close()
            for name, url in SEED_CATALOGUES.items():
                host = urllib.parse.urlsplit(url).netloc.casefold()
                if host in already:
                    print(f"  skipped      already a known host      {name} ({host})")
                    continue
                print(f"=== {name}")
                for entry in investigate(fetcher, url, dataset_id=None, source_id=name,
                                         depth=0, probe=args.probe):
                    record(entry)
        else:
            conn = open_registry(Path(args.db))
            rows = unreadable_rows(conn, source=args.source, limit=args.limit)
            conn.close()
            print(f"{len(rows)} dataset(s) with no readable verdict\n")
            for row in rows:
                print(f"=== {row['id']}  ({row['capability'] or 'no capability row'})")
                for entry in investigate(fetcher, row["access_path"], dataset_id=row["id"],
                                         source_id=row["source_id"], depth=0, probe=args.probe):
                    record(entry)

    print(f"\n{written} line(s) appended to {out_path}, {fetcher.count} request(s)")
    print("verdicts: " + ", ".join(f"{k}={v}" for k, v in sorted(verdicts.items())))
    rows_found = verdicts.get("rows", 0) + verdicts.get("rows-truncated", 0)
    print(f"\n{rows_found} candidate(s) returned rows. Review them with:")
    print(f"    jq -c 'select(.verdict|startswith(\"rows\"))' {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
