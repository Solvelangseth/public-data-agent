"""Resolve Geonorge metadata pages into what is actually behind them.

7,429 datasets in the registry point at `kartkatalog.geonorge.no/metadata/uuid/...`,
which is a page describing someone else's dataset, not an endpoint. That is
74% of everything the registry has never verified, and leaving it unresolved
is the single largest gap between this project and data.norge -- which shows
the same page and stops there.

One call to `api/getdata/{uuid}` returns everything that page is hiding: the
real distribution URLs, the protocols, the formats, the licence and the access
constraint. This walks them, classifies each dataset by the **best** access it
has, and writes one JSON line per dataset. It opens the registry read-only and
writes nothing to it.

What the classification is for, measured on a 399-dataset sample:

    1 queryable API     4%   a connector can read it
    2 bulk download     8%   a file we could hold
    3 map service       0%
    4 web page only    86%   of which 71% is aerial imagery and most of the
                             rest is LiDAR elevation. None of 344 carried a
                             tabular format, so there is nothing to scrape
                             into a table -- but the resolved download URL,
                             licence and format are still worth holding,
                             because the catalogue page does not show them.
    5 offline / none    1%

The tiers are a judgement and the protocol strings in them are the
publisher's own words, so a reader can disagree with the ordering without
re-fetching anything.

    scripts/resolve_geonorge.py --limit 50          # a taste
    scripts/resolve_geonorge.py                     # all of them, ~45 min
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

USER_AGENT = "public-data-agent (https://github.com/Solvelangseth/public-data-agent)"
API = "https://kartkatalog.geonorge.no/api/getdata/"
DEFAULT_OUT = Path("discovery/geonorge_resolved.jsonl")

# Best access first. A dataset is filed under the first tier it reaches.
TIERS: tuple[tuple[str, frozenset[str]], ...] = (
    ("queryable-api", frozenset({
        "OGC:OAPIF", "OGC API-Features", "REST-API", "OPeNDAP",
        "WFS-tjeneste", "OGC:WFS", "WCS-tjeneste", "SOS-tjeneste",
    })),
    ("bulk-download", frozenset({
        "Geonorge nedlastning", "Atom Feed", "Egen nedlastningsside",
        "GEONORGE:DOWNLOAD", "Nedlasting", "GEONORGE:FILEDOWNLOAD",
    })),
    ("map-service", frozenset({
        "WMS-tjeneste", "OGC:WMS", "WMTS-tjeneste", "Karttjeneste",
    })),
    ("web-page", frozenset({"Webside", "WWW:LINK"})),
    ("offline", frozenset({"Ingen online tilgang", "GEONORGE:OFFLINE"})),
)

IMAGERY_FORMATS = frozenset({
    "GeoTIFF", "TIFF", "Tiled TIFF", "Tiled GeoTIFF", "Jpeg", "Jpeg2000",
    "PNG", "ECW", "JPEG", "JPG", "MrSID",
})
ELEVATION_FORMATS = frozenset({"LAZ", "ZLAS", "LAS", "USGS DEM", "DTED", "XYZ"})
TABULAR_FORMATS = frozenset({
    "CSV", "JSON", "GeoJSON", "XLSX", "XLS", "SOSI", "GML", "FGDB", "PostGIS",
    "GeoPackage", "GPKG", "NetCDF-CF", "NetCDF", "XML", "Parquet", "DBF",
})


def classify(protocols: set[str]) -> str:
    for name, members in TIERS:
        if protocols & members:
            return name
    return "unrecognised"


def resolve(uuid: str, dataset_id: str) -> dict[str, Any]:
    request = urllib.request.Request(API + uuid, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read(1_500_000))
    except urllib.error.HTTPError as error:
        return {"dataset_id": dataset_id, "uuid": uuid, "tier": "unresolved",
                "error": f"HTTP {error.code}"}
    except Exception as error:
        return {"dataset_id": dataset_id, "uuid": uuid, "tier": "unresolved",
                "error": type(error).__name__}

    distributions = payload.get("DistributionsFormats")
    distributions = distributions if isinstance(distributions, list) else []
    protocols = {str(d.get("ProtocolName") or "") for d in distributions if isinstance(d, dict)}
    protocols.discard("")
    if not protocols and payload.get("DistributionProtocol"):
        protocols = {str(payload["DistributionProtocol"])}
    formats = {str(d.get("FormatName") or "") for d in distributions if isinstance(d, dict)}
    formats.discard("")
    tier = classify(protocols)

    # The URL that actually serves the data for the tier it landed in, taken
    # from the distribution that put it there. Never composed.
    best_url = None
    tier_protocols = next((m for name, m in TIERS if name == tier), frozenset())
    for distribution in distributions:
        if not isinstance(distribution, dict):
            continue
        if str(distribution.get("ProtocolName") or "") in tier_protocols:
            url = distribution.get("URL")
            if isinstance(url, str) and url.startswith("http"):
                best_url = url
                break
    if best_url is None:
        url = payload.get("DistributionUrl")
        best_url = url if isinstance(url, str) and url.startswith("http") else None

    constraints = payload.get("Constraints") if isinstance(payload.get("Constraints"), dict) else {}
    return {
        "dataset_id": dataset_id,
        "uuid": uuid,
        "title": payload.get("Title"),
        "tier": tier,
        "protocols": sorted(protocols),
        "formats": sorted(formats),
        "best_url": best_url,
        # The publisher's own words for whether it is open, and the licence
        # link it points at. Neither is inferred.
        # `series` means a parent record grouping versions, and it is why 34 of
        # the 45 capabilities 404s are 404s: a Datasettserie has no download of
        # its own, so the download service is right to have no entry. Captured
        # here so the next run can skip them rather than record a failure.
        "hierarchy_level": payload.get("HierarchyLevel"),
        "parent_identifier": payload.get("ParentIdentifier"),
        "access_constraint": constraints.get("AccessConstraints"),
        "license_url": constraints.get("OtherConstraintsLink"),
        "use_constraint": constraints.get("UseConstraints"),
        "owner": (payload.get("ContactOwner") or {}).get("Organization")
                 if isinstance(payload.get("ContactOwner"), dict) else None,
        "imagery_only": bool(formats) and formats <= IMAGERY_FORMATS,
        "elevation_only": bool(formats) and formats <= ELEVATION_FORMATS,
        "has_tabular": bool(formats & TABULAR_FORMATS),
        "date_published": payload.get("DatePublished"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/registry.sqlite")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--pause", type=float, default=0.35)
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done: set[str] = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["dataset_id"])
            except Exception:
                continue

    conn = sqlite3.connect(f"file:{Path(args.db)}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    pending = [
        (row["id"], urllib.parse.urlsplit(row["access_path"]).path.rstrip("/").split("/")[-1])
        for row in conn.execute(
            "SELECT id, access_path FROM datasets "
            "WHERE access_path LIKE 'https://kartkatalog.geonorge.no/metadata/uuid/%' "
            "ORDER BY id"
        )
        if row["id"] not in done
    ]
    conn.close()
    if args.limit:
        pending = pending[: args.limit]
    print(f"{len(done):,} already resolved, {len(pending):,} to go")

    tiers: dict[str, int] = {}
    with out_path.open("a", encoding="utf-8") as sink:
        for index, (dataset_id, uuid) in enumerate(pending, start=1):
            entry = resolve(uuid, dataset_id)
            sink.write(json.dumps(entry, ensure_ascii=False) + "\n")
            sink.flush()
            tiers[entry["tier"]] = tiers.get(entry["tier"], 0) + 1
            if index % 100 == 0 or index == len(pending):
                summary = ", ".join(f"{k}={v}" for k, v in sorted(tiers.items()))
                print(f"  {index:,}/{len(pending):,}  {summary}", flush=True)
            time.sleep(args.pause)

    print(f"\nwrote {out_path}")
    for name, count in sorted(tiers.items(), key=lambda kv: -kv[1]):
        print(f"  {name:16} {count:>6,}")

    # One url standing for hundreds of datasets is the single most misleading
    # thing this file can contain. 608 bulk-download rows resolved to
    # `nedlasting.geonorge.no/api/capabilities/`, which is the download
    # service's root, and reading that as one resource nearly cost the
    # per-dataset endpoint behind it. The url is still the publisher's own
    # declaration and is kept; what was missing was saying so.
    shared: dict[str, int] = {}
    for line in out_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            url = json.loads(line).get("best_url")
        except ValueError:
            continue
        if url:
            shared[url] = shared.get(url, 0) + 1
    repeated = sorted(
        ((url, n) for url, n in shared.items() if n > 1), key=lambda kv: -kv[1]
    )
    if repeated:
        print(f"\n{sum(n for _u, n in repeated):,} row(s) share a best_url with another "
              f"row, over {len(repeated)} url(s). A url standing for many datasets is a "
              "service root, not a resource -- the per-dataset address is elsewhere:")
        for url, count in repeated[:6]:
            print(f"  {count:>5}  {url[:88]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
