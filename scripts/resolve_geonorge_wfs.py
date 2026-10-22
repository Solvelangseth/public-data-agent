"""Which Geonorge datasets declare a WFS, taken from the catalogue in bulk.

Found while answering the last eleven download-service 404s. Those records
carry a live view service in a field nothing here reads, and 8 of 9 turned out
to answer `GetFeature` with real rows -- 3,153 point observations of corals and
benthic samples, on datasets the registry had filed as having nothing to
download.

`ServiceWfsDistributionUrlForDataset` is the catalogue's own name for it, and
the search API returns it per hit, 500 hits a page. So the whole catalogue is
15 requests rather than 7,437, and nothing is probed here: this records what
the publisher declares. Whether the endpoint answers is a separate question
with a separate script, because a declaration that fails is a finding about
the publisher and a declaration nobody asked about is not a finding at all.

A WFS url is not yet a readable layer. Three things are known to get in the
way, and all three are left for the reader rather than guessed at here:

    the typeName      the url often carries no layer, and the layer name is
                      spelled `a:b` on some records and `a/b` on others
    the server        GeoServer answers `outputFormat=application/json`;
                      MapServer `cgi-bin` and ArcGIS `WFSServer` may not
    the shared url    many datasets point at one `wfs.geonorge.no` service
                      with a layer each, the same trap as the 608 rows that
                      shared the download-service root

    scripts/resolve_geonorge_wfs.py --limit 1000
    scripts/resolve_geonorge_wfs.py
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

USER_AGENT = "public-data-agent (https://github.com/Solvelangseth/public-data-agent)"
SEARCH = "https://kartkatalog.geonorge.no/api/search"
DEFAULT_OUT = Path("discovery/geonorge_wfs.jsonl")
PAGE = 500


def _get(url: str) -> Any:
    """Deliberately does not catch. A page is 500 records.

    One catalogue, 15 requests. A page that fails and is swallowed takes 500
    datasets out of the count with nothing in the output saying so, and the
    totals printed at the end would be quietly wrong. Better to stop.
    """

    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read(40_000_000))


def page_url(offset: int, limit: int) -> str:
    # The facet parameter names contain brackets, which have to survive
    # unencoded or the catalogue ignores the facet and returns services too.
    query = urllib.parse.urlencode({"limit": limit, "offset": offset})
    return f"{SEARCH}?{query}&facets%5B0%5Dname=type&facets%5B0%5Dvalue=dataset"


def declared_wfs(hit: dict[str, Any]) -> dict[str, Any] | None:
    """The WFS a catalogue hit declares, or None.

    The field holds one url, and the url usually carries `GetCapabilities` as
    its request. That is kept whole: rewriting it into a `GetFeature` is the
    reader's job and depends on a layer name this record may not carry.
    """

    url = hit.get("ServiceWfsDistributionUrlForDataset")
    if not isinstance(url, str) or not url.lower().startswith("http"):
        return None
    parsed = urllib.parse.urlparse(url)
    params = {k.lower(): v for k, v in urllib.parse.parse_qsl(parsed.query)}
    return {
        "uuid": hit.get("Uuid"),
        "title": hit.get("Title"),
        "owner": hit.get("Organization"),
        "wfs_url": url,
        "wfs_host": parsed.netloc,
        # What the publisher put in the url, not what we would ask for.
        "declared_request": params.get("request"),
        "declared_typename": params.get("typename") or params.get("typenames"),
        "access_constraint": hit.get("AccessConstraint"),
        "open_data": bool(hit.get("AccessIsOpendata")),
        "theme": hit.get("Theme"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--limit", type=int, help="stop after this many catalogue hits")
    parser.add_argument("--pause", type=float, default=0.5)
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    first = _get(page_url(1, 1))
    total = int(first.get("NumFound") or 0)
    if args.limit:
        total = min(total, args.limit)
    print(f"{total:,} dataset records to read, {PAGE} a page")

    hosts: Counter[str] = Counter()
    seen_urls: Counter[str] = Counter()
    read = 0
    declared = 0
    with out_path.open("w", encoding="utf-8") as sink:
        offset = 1
        while read < total:
            payload = _get(page_url(offset, min(PAGE, total - read)))
            hits = payload.get("Results") or []
            if not hits:
                break
            for hit in hits:
                read += 1
                entry = declared_wfs(hit)
                if entry is None:
                    continue
                declared += 1
                hosts[entry["wfs_host"]] += 1
                seen_urls[entry["wfs_url"].split("?")[0]] += 1
                sink.write(json.dumps(entry, ensure_ascii=False) + "\n")
            sink.flush()
            offset += len(hits)
            print(f"  {read:,}/{total:,}  declared={declared:,}", flush=True)
            time.sleep(args.pause)

    print(f"\n{declared:,} of {read:,} dataset records declare a WFS")
    print(f"{len(seen_urls):,} distinct service address(es), "
          f"so {declared - len(seen_urls):,} rows share one with another dataset")
    print("\ntop hosts:")
    for host, count in hosts.most_common(12):
        print(f"  {count:>5,}  {host}")
    print("\nmost-shared addresses:")
    for url, count in seen_urls.most_common(6):
        print(f"  {count:>5,}  {url[:92]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
