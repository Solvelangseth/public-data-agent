"""Ask the Geonorge download service what each dataset offers, download nothing.

608 of the 704 bulk-download rows share one `best_url`: the download service's
own root. The per-dataset address is `api/capabilities/{metadataUuid}`, and the
uuid is already in the registry -- so 608 rows that looked like one service are
608 individually addressable resources.

What that endpoint and its codelists publish, without transferring a single
data file:

    format        GML, SOSI, FGDB, PostGIS, **CSV**
    projection    EPSG codes the dataset can be delivered in
    area          the kommuner and fylker it covers, with their codes

The third is the find. `FKB-Lufthavn` lists 101 kommuner by number;
`Matrikkelen Adresse` lists 423 kommuner and 19 fylker and offers CSV.
Nothing in this registry could previously answer "which datasets cover
Alstahaug", and the catalogue these rows were harvested from cannot either.
It is also a fourth publisher-declared kommune key, and the first that is
*coverage* rather than a single location.

Grid-cell areas are counted, not listed. A raster dataset can offer 1,335
cells named `0001`..`1335`, which join to nothing and would be most of the
rows written.

Writes JSON lines; `apply_download_capabilities.py` is what touches the
registry. Nothing here downloads a data file, which also matters because the
machine this runs on has under a gigabyte free.

    scripts/resolve_download_capabilities.py --limit 30
    scripts/resolve_download_capabilities.py
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

USER_AGENT = "public-data-agent (https://github.com/Solvelangseth/public-data-agent)"
DEFAULT_OUT = Path("discovery/download_capabilities.jsonl")

# Area types that join to something. A `celle` is a tile in a raster grid and
# joins to nothing; `landsdekkende` means the whole country, which is a fact
# worth keeping but not a list of places.
JOINABLE_AREA_TYPES = frozenset({"kommune", "fylke"})

REL_PREFIX = "http://rel.geonorge.no/download/"


def _get(url: str, cap: int = 4_000_000) -> tuple[int, Any]:
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            raw = response.read(cap)
            try:
                return response.status, json.loads(raw)
            except ValueError:
                return response.status, None
    except urllib.error.HTTPError as error:
        return error.code, None
    except Exception:
        return 0, None


def _codelist(links: list[dict[str, Any]], name: str) -> str | None:
    for link in links:
        if isinstance(link, dict) and link.get("rel") == REL_PREFIX + name:
            href = link.get("href")
            if isinstance(href, str) and href.startswith("http"):
                return href
    return None


CATALOGUE = "https://kartkatalog.geonorge.no/api/getdata/"


def _ask_the_catalogue(dataset_id: str, uuid: str, status: int) -> dict[str, Any]:
    """Why a download service has no entry for a uuid its catalogue advertises.

    One request, only on a 404, to the catalogue the uuid came from. Three
    answers come back, and all three are decided rather than failures:

        series    a parent record grouping versions, with no download of its
                  own. 34 of the 45 first-run failures, and the reason the
                  download service is right to 404.
        offline   `GEONORGE:OFFLINE`: the publisher says the distribution is
                  not online at all, so there is nothing to ask for.
        declared  `GEONORGE:DOWNLOAD` with formats listed in the catalogue
                  record but no entry in the download service. The formats
                  are real -- the catalogue states them -- and they are kept
                  here; what is missing is the service's selection flags and
                  its area list, which cannot be recovered.

    What does *not* work, measured: `codelists/format/{uuid}` and
    `codelists/area/{uuid}` answer `200 []` for these uuids, and answer
    `200 []` for `00000000-0000-0000-0000-000000000000` as well. The status
    code says the route exists, not that the dataset does, so a fallback to
    the codelists would have recorded "no formats, no coverage" as a finding
    for every one of them.
    """

    _status, meta = _get(CATALOGUE + uuid)
    entry: dict[str, Any] = {"dataset_id": dataset_id, "uuid": uuid}
    if not isinstance(meta, dict):
        entry["error"] = f"capabilities HTTP {status}"
        return entry
    level = meta.get("HierarchyLevel")
    protocol = meta.get("DistributionProtocol")
    if level == "series":
        entry["skipped"] = "series: a parent record grouping versions, with no download of its own"
        return entry
    if protocol == "GEONORGE:OFFLINE":
        entry["skipped"] = "offline: the publisher declares the distribution is not online"
        return entry
    # The catalogue's own format list, which is a different statement from the
    # download service's: Name plus Version, so `GML 3.2.1` rather than `GML`.
    formats = [
        " ".join(part for part in (f.get("Name"), f.get("Version")) if part).strip()
        for f in meta.get("DistributionFormats") or []
        if isinstance(f, dict) and f.get("Name")
    ]
    entry["unregistered_download"] = (
        f"declares {protocol} but the download service has no entry (HTTP {status})"
    )
    if formats:
        entry["catalogue_formats"] = sorted(set(formats))
    # A view service on the same record is a live endpoint, and a GeoServer
    # WMS layer usually answers WFS at the same address. Recorded, not probed.
    view_url = meta.get("ServiceDistributionUrlForDataset")
    if isinstance(view_url, str) and view_url.startswith("http"):
        entry["view_service"] = {
            "protocol": meta.get("ServiceDistributionProtocolForDataset"),
            "layer": meta.get("ServiceDistributionNameForDataset"),
            "url": view_url,
        }
    return entry


def resolve(
    dataset_id: str,
    uuid: str,
    service_root: str,
    pause: float,
) -> dict[str, Any]:
    status, capabilities = _get(f"{service_root.rstrip('/')}/{uuid}")
    if not isinstance(capabilities, dict):
        if status == 404:
            time.sleep(pause)
            return _ask_the_catalogue(dataset_id, uuid, status)
        return {"dataset_id": dataset_id, "uuid": uuid, "error": f"capabilities HTTP {status}"}

    links = capabilities.get("_links")
    links = links if isinstance(links, list) else []
    entry: dict[str, Any] = {
        "dataset_id": dataset_id,
        "uuid": uuid,
        "service_root": service_root,
        "supports_area_selection": bool(capabilities.get("supportsAreaSelection")),
        "supports_format_selection": bool(capabilities.get("supportsFormatSelection")),
        "supports_projection_selection": bool(capabilities.get("supportsProjectionSelection")),
        # The publisher's own statement that a role is required. It is how the
        # Norge digitalt gate shows up in the download API, and it agrees with
        # what ACCESS.md recorded from the licence side.
        "access_constraint_required_role": capabilities.get("accessConstraintRequiredRole"),
        "distributed_by": capabilities.get("distributedBy"),
    }

    formats_url = _codelist(links, "format")
    if formats_url:
        time.sleep(pause)
        _status, formats = _get(formats_url)
        if isinstance(formats, list):
            # The publisher's own list carries 52 spellings of 34 formats:
            # trailing spaces on most of them, plus GeoJSON/GEOJSON and
            # Shape/SHAPE. A consumer matching "CSV" exactly misses the three
            # datasets that say "CSV " -- which my first count of this did.
            # The publisher's spelling is kept beside the normal form, because
            # it is theirs and a normalisation is a reading.
            seen: dict[str, str] = {}
            for item in formats:
                if not isinstance(item, dict) or not item.get("name"):
                    continue
                printed = str(item["name"])
                seen.setdefault(printed.strip().upper(), printed.strip())
            entry["formats"] = sorted(seen.values())
            entry["formats_as_printed"] = sorted({
                str(f.get("name")) for f in formats
                if isinstance(f, dict) and f.get("name")
            })

    projection_url = _codelist(links, "projection")
    if projection_url:
        time.sleep(pause)
        _status, projections = _get(projection_url)
        if isinstance(projections, list):
            entry["projections"] = sorted({
                str(p.get("code")) for p in projections
                if isinstance(p, dict) and p.get("code")
            })

    area_url = _codelist(links, "area")
    if area_url:
        time.sleep(pause)
        _status, areas = _get(area_url)
        if isinstance(areas, list):
            types: Counter[str] = Counter()
            joinable: list[dict[str, str]] = []
            for area in areas:
                if not isinstance(area, dict):
                    continue
                kind = str(area.get("type") or "")
                types[kind] += 1
                code = str(area.get("code") or "")
                name = str(area.get("name") or "")
                if kind not in JOINABLE_AREA_TYPES or not code:
                    continue
                # An area whose name is its own code is not a place. One
                # dataset -- N50 Raster historiske 2022 (UTM32) -- files 737
                # raster tiles under type "kommune", each named after its
                # number, and they were 737 of the 1,538 distinct kommune
                # codes in the table. A kommune has a name; a tile has a
                # number. Same reasoning as excluding `celle`, met one layer
                # further in.
                if name == code:
                    types["kommune-shaped tile"] += 1
                    continue
                joinable.append({"type": kind, "code": code, "name": name})
            entry["area_types"] = dict(types)
            entry["areas"] = joinable
            entry["nationwide"] = "landsdekkende" in types
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/registry.sqlite")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--pause", type=float, default=0.3)
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
        (row["dataset_id"], row["access_path"].rstrip("/").split("/")[-1], row["best_url"])
        for row in conn.execute(
            "SELECT dist.dataset_id, dist.best_url, d.access_path "
            "FROM distributions dist JOIN datasets d ON d.id = dist.dataset_id "
            "WHERE dist.best_url LIKE '%/api/capabilities/' "
            "  AND d.access_path LIKE '%/metadata/uuid/%' "
            "ORDER BY dist.dataset_id"
        )
        if row["dataset_id"] not in done
    ]
    conn.close()
    if args.limit:
        pending = pending[: args.limit]
    print(f"{len(done):,} done, {len(pending):,} to go")

    stats: Counter[str] = Counter()
    with out_path.open("a", encoding="utf-8") as sink:
        for index, (dataset_id, uuid, service_root) in enumerate(pending, start=1):
            entry = resolve(dataset_id, uuid, service_root, args.pause)
            sink.write(json.dumps(entry, ensure_ascii=False) + "\n")
            sink.flush()
            if entry.get("error"):
                stats["error"] += 1
            elif entry.get("skipped"):
                stats[entry["skipped"].split(":", 1)[0]] += 1
            elif entry.get("unregistered_download"):
                stats["unregistered_download"] += 1
                stats["with_catalogue_formats"] += 1 if entry.get("catalogue_formats") else 0
                stats["with_view_service"] += 1 if entry.get("view_service") else 0
            else:
                stats["resolved"] += 1
                stats["with_kommune"] += 1 if any(
                    a["type"] == "kommune" for a in entry.get("areas") or []
                ) else 0
                stats["with_csv"] += 1 if "CSV" in (entry.get("formats") or []) else 0
                stats["role_required"] += 1 if entry.get("access_constraint_required_role") else 0
            if index % 50 == 0 or index == len(pending):
                print(f"  {index:,}/{len(pending):,}  " +
                      ", ".join(f"{k}={v}" for k, v in sorted(stats.items())), flush=True)
            time.sleep(args.pause)

    print(f"\nwrote {out_path} at {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    for key, value in sorted(stats.items()):
        print(f"  {key:18} {value:>6,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
