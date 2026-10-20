"""Find SSB tables the publisher has taken down, and say so in the registry.

32 `ssbtable` capability rows had never been verified, and the standing
explanation was that a pinned dimension code was being rejected -- SSB's v0
API answers HTTP 400 `{"error": "Parameter error"}`, which reads as a bad
query. It is not. The v2 API answers the same tables with
`{"title": "Non-existent table", "status": 404}`: the tables are gone.

So the probe asks v2, which gives a straight answer, and marks what it finds.
A withdrawn table is not `unverified` -- nobody failing to check and the
publisher having removed it are different facts, and only one of them is worth
retrying.

Rate limits are respected: SSB returns 429 under a tight loop, so requests are
spaced and a 429 is reported rather than treated as an answer.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from public_data_agent.fetch import CAPABILITY_WITHDRAWN
from public_data_agent.registry import Registry, utc_now

V2_METADATA = "https://data.ssb.no/api/pxwebapi/v2-beta/tables/{table}/metadata?lang=no"
USER_AGENT = "public-data-agent (https://github.com/Solvelangseth/public-data-agent)"
PAUSE_SECONDS = 3.5


def _probe(table: str, timeout: float = 30.0) -> tuple[int, bytes]:
    request = urllib.request.Request(
        V2_METADATA.format(table=table), headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(400)
    except urllib.error.HTTPError as error:
        return error.code, error.read(400)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/registry.sqlite")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--pause", type=float, default=PAUSE_SECONDS)
    args = parser.parse_args()

    registry = Registry(Path(args.db))
    rows = registry.conn.execute(
        "SELECT dataset_id FROM resource_capability "
        "WHERE verified_at IS NULL AND dataset_id LIKE 'ssbtable:%' ORDER BY dataset_id"
    ).fetchall()
    if not rows:
        print("no unverified SSB capability rows left to probe")
        return 0

    withdrawn: list[str] = []
    alive: list[str] = []
    unclear: list[tuple[str, int]] = []
    for index, row in enumerate(rows):
        dataset_id = row["dataset_id"]
        table = dataset_id.split(":", 1)[1]
        status, body = _probe(table)
        if status == 404 and b"Non-existent table" in body:
            withdrawn.append(dataset_id)
        elif status == 200:
            alive.append(dataset_id)
        else:
            unclear.append((dataset_id, status))
        if index + 1 < len(rows):
            time.sleep(args.pause)

    print(f"withdrawn ({len(withdrawn)}): {' '.join(withdrawn)}")
    print(f"still published ({len(alive)}): {' '.join(alive)}")
    if unclear:
        # A 429 is the rate limiter, not an answer about the table.
        print(f"no clear answer ({len(unclear)}): {unclear}")
    if not args.apply:
        print("\ndry run; pass --apply to record what the probe found.")
        return 0

    stamped = utc_now()
    note = (
        f"withdrawn {stamped[:10]}: SSB's v2 API answers this table "
        '{"title": "Non-existent table", "status": 404}. The v0 API reports it as '
        'HTTP 400 "Parameter error", which is why it looked like a rejected query.'
    )
    for dataset_id in withdrawn:
        existing = registry.get_capability(dataset_id)
        if existing is None:
            continue
        merged = {key: existing[key] for key in existing.keys() if key != "dataset_id"}
        merged.update(
            {
                "capability": CAPABILITY_WITHDRAWN,
                "record_kind": None,
                "notes": f"{existing['notes']}; {note}" if existing["notes"] else note,
            }
        )
        registry.set_capability(dataset_id, merged)
    registry.conn.commit()
    print(f"marked {len(withdrawn)} capability rows withdrawn")
    registry.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
