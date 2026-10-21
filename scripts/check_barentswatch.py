"""Ask BarentsWatch what a credential in `.env` is allowed to do. Store nothing.

BarentsWatch issues one scope per client -- `ais` or `api` -- and the two are
not interchangeable. A client registered as an AIS-client gets vessel
positions and is refused by everything under `/bwapi/`. So "do we have
BarentsWatch access" is not a yes-or-no question, and this script answers the
real one: which scope does this pair hold, and which endpoints answer it.

Three failures look alike from the outside and mean entirely different things:

    invalid_client   the id and secret are not a recognised pair
    invalid_scope    the pair is real, this client was not registered for it
    HTTP 401         the token is fine, this endpoint is outside its scope

The first one has a trap worth naming, because it cost a round trip here. A
client id is `you@example.com:clientname`, and MyPage shows the name next to
the secret. Pasting the name into the secret field produces `invalid_client`
with no hint that the two fields disagree, so this script checks for it
before it asks the server anything.

Usage:

    scripts/check_barentswatch.py                 # every pair it finds
    scripts/check_barentswatch.py --prefix BARENTSWATCH_API_
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TOKEN_URL = "https://id.barentswatch.no/connect/token"
USER_AGENT = "public-data-agent (https://github.com/Solvelangseth/public-data-agent)"

# One probe per scope: an endpoint that answers rows when the scope is right.
PROBES = {
    "api": [
        "https://www.barentswatch.no/bwapi/v1/geodata/fishhealth/locality/2024/1",
        "https://www.barentswatch.no/bwapi/v1/geodata/fishhealth/localities",
    ],
    "ais": [
        "https://live.ais.barentswatch.no/v1/latest/combined",
        "https://historic.ais.barentswatch.no/v1/historic/trackslast24hours/257111020",
    ],
}


def read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        values[key] = value.strip().strip('"').strip("'")
    return values


def token_for(client_id: str, secret: str, scope: str) -> tuple[str | None, str]:
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": secret,
        "scope": scope,
    }).encode()
    request = urllib.request.Request(
        TOKEN_URL, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.loads(response.read())
            return payload.get("access_token"), f"granted {payload.get('scope')!r}, {payload.get('expires_in')}s"
    except urllib.error.HTTPError as error:
        detail = error.read(300).decode("utf-8", "replace")
        try:
            detail = json.loads(detail).get("error", detail)
        except ValueError:
            detail = " ".join(detail.split())[:90]
        return None, f"HTTP {error.code} {detail}"
    except Exception as error:
        return None, f"{type(error).__name__}"


def describe(url: str, token: str) -> str:
    request = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read(2_000_000)
    except urllib.error.HTTPError as error:
        return f"HTTP {error.code}"
    except Exception as error:
        return type(error).__name__
    try:
        payload = json.loads(raw)
    except ValueError:
        # A capped read of a long array lands mid-token; say so rather than
        # calling the endpoint broken.
        return f"HTTP 200, {len(raw)} bytes, not parseable at this read size"
    if isinstance(payload, list):
        first = payload[0] if payload and isinstance(payload[0], dict) else None
        keys = f", keys {sorted(first)[:8]}" if first else ""
        return f"HTTP 200, {len(payload)} row(s){keys}"
    if isinstance(payload, dict):
        inner = "".join(f", {k}[{len(v)}]" for k, v in payload.items() if isinstance(v, list))
        return f"HTTP 200, object with keys {sorted(payload)[:8]}{inner}"
    return f"HTTP 200, {type(payload).__name__}"


def check(prefix: str, env: dict[str, str]) -> bool:
    client_id = env.get(f"{prefix}CLIENT_ID", "")
    secret = env.get(f"{prefix}CLIENT_SECRET", "")
    print(f"=== {prefix}CLIENT_ID / {prefix}CLIENT_SECRET")
    if not client_id or not secret:
        print("    not set\n")
        return False
    if ":" not in client_id:
        print("    the id has no ':' -- it should look like you@example.com:clientname\n")
        return False
    name = client_id.split(":", 1)[1]
    if secret == name:
        print("    the secret is a copy of the client NAME, the text after the ':' in")
        print("    the id. MyPage shows them side by side. Open the client and copy the")
        print("    secret itself, or create a new one if it was only shown at creation.\n")
        return False

    held = None
    for scope in ("api", "ais"):
        token, note = token_for(client_id, secret, scope)
        print(f"    scope={scope:4} {note}")
        if token and held is None:
            held = (scope, token)
    if held is None:
        print()
        return False
    scope, token = held
    for url in PROBES[scope]:
        print(f"      {describe(url, token):<64} {url}")
    print()
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", default=".env")
    parser.add_argument("--prefix", action="append", default=[],
                        help="default: BARENTSWATCH_ and BARENTSWATCH_API_")
    args = parser.parse_args()
    env = read_dotenv(Path(args.env))
    prefixes = args.prefix or ["BARENTSWATCH_", "BARENTSWATCH_API_"]
    ok = [check(prefix, env) for prefix in prefixes]
    return 0 if any(ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
