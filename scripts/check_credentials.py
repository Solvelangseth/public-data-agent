"""Ask each credentialled API what the keys in `.env` are allowed to do.

The point is not "is the key set" -- a key can be present, well-formed and
refused. Each publisher is asked a real question and the answer is reported
with the distinction that decides what to do next:

    the pair is not recognised        regenerate or re-copy the secret
    the pair is real, wrong scope     register a second client
    the token is fine, endpoint 401    the resource is outside that scope
    it works                           build the connector

Nothing is stored and no secret is printed, so this is safe to run and safe to
paste the output of. One check per publisher, each in its own function, so a
new one is a function and a line in CHECKS.

Usage:

    scripts/check_credentials.py                 # everything configured
    scripts/check_credentials.py --only nve
    scripts/check_credentials.py --ask nve       # prompt for a candidate key
"""

from __future__ import annotations

import argparse
import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "public-data-agent (https://github.com/Solvelangseth/public-data-agent)"


def read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip().removeprefix("export ").strip()] = value.strip().strip('"').strip("'")
    return values


def _get(url: str, headers: dict[str, str]) -> tuple[int, object | None, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **headers})
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            raw = response.read(2_000_000)
            try:
                return response.status, json.loads(raw), ""
            except ValueError:
                return response.status, None, f"{len(raw)} bytes, not JSON at this read size"
    except urllib.error.HTTPError as error:
        body = error.read(300).decode("utf-8", "replace")
        try:
            named = json.loads(body)
            body = named.get("error") or named.get("title") or " ".join(body.split())
        except ValueError:
            body = " ".join(body.split())
        return error.code, None, body[:110]
    except Exception as error:
        return 0, None, type(error).__name__


def _post_form(url: str, fields: dict[str, str]) -> tuple[int, dict | None, str]:
    body = urllib.parse.urlencode(fields).encode()
    request = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read()), ""
    except urllib.error.HTTPError as error:
        text = error.read(300).decode("utf-8", "replace")
        try:
            named = json.loads(text).get("error")
        except ValueError:
            named = None
        return error.code, None, named or " ".join(text.split())[:110]
    except Exception as error:
        return 0, None, type(error).__name__


def _shape(value: str) -> str:
    """Enough to spot a truncated or mis-pasted value, not enough to use it."""

    skeleton = "".join("9" if c.isdigit() else ("a" if c.isalpha() else c) for c in value)
    return f"{len(value)} chars, shape {skeleton[:44]}"


def _rows(payload: object) -> str:
    if isinstance(payload, list):
        first = payload[0] if payload and isinstance(payload[0], dict) else None
        return f"{len(payload)} row(s)" + (f", keys {sorted(first)[:7]}" if first else "")
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, list):
                first = value[0] if value and isinstance(value[0], dict) else None
                return f"{key}[{len(value)}]" + (f", keys {sorted(first)[:7]}" if first else "")
        return f"object, keys {sorted(payload)[:7]}"
    return "no rows"


def check_barentswatch(env: dict[str, str], ask: str | None) -> bool:
    ok = False
    for scope, prefix in (("api", "BARENTSWATCH_API_"), ("ais", "BARENTSWATCH_")):
        client_id = env.get(f"{prefix}CLIENT_ID", "")
        secret = ask if ask else env.get(f"{prefix}CLIENT_SECRET", "")
        print(f"  {prefix}CLIENT_ID / _SECRET  (scope {scope!r})")
        if not client_id or not secret:
            print("      not set\n")
            continue
        if ":" in client_id and secret == client_id.split(":", 1)[1]:
            print("      WARNING: the secret equals the client name, the text after the")
            print("      ':' in the id -- a common copy-paste slip. Asking anyway.")
        status, payload, note = _post_form(
            "https://id.barentswatch.no/connect/token",
            {"grant_type": "client_credentials", "client_id": client_id,
             "client_secret": secret, "scope": scope},
        )
        if payload is None:
            meaning = {
                "invalid_client": "the id and secret are not a recognised pair",
                "invalid_scope": f"the pair is real but not registered for {scope!r}",
            }.get(note, "")
            print(f"      token: HTTP {status} {note}" + (f" -- {meaning}" if meaning else ""))
            print()
            continue
        token = payload.get("access_token")
        print(f"      token: HTTP {status}, scope {payload.get('scope')!r}, "
              f"{payload.get('expires_in')}s")
        probes = {
            "api": ["https://www.barentswatch.no/bwapi/v1/geodata/fishhealth/localities"],
            "ais": ["https://live.ais.barentswatch.no/v1/latest/combined"],
        }[scope]
        for url in probes:
            code, body, note = _get(url, {"Authorization": f"Bearer {token}"})
            print(f"      HTTP {code}  {_rows(body) if body is not None else note}  {url}")
            ok = ok or code == 200
        print()
    return ok


def check_frost(env: dict[str, str], ask: str | None) -> bool:
    client_id = env.get("FROST_CLIENT_ID", "")
    secret = ask if ask else env.get("FROST_CLIENT_SECRET", "")
    print("  FROST_CLIENT_ID / FROST_CLIENT_SECRET")
    if not client_id:
        print("      not set\n")
        return False
    print(f"      client id: {_shape(client_id)}")
    # Frost takes the client id as a basic-auth username with an empty
    # password. That needs no token and no refresh, so it is the form a
    # connector should use; the secret is only for the 24-hour bearer.
    basic = base64.b64encode(f"{client_id}:".encode()).decode()
    code, body, note = _get(
        "https://frost.met.no/sources/v0.jsonld?county=Oslo",
        {"Authorization": f"Basic {basic}"},
    )
    print(f"      basic auth:  HTTP {code}  {_rows(body) if body is not None else note}")
    ok = code == 200
    if secret:
        status, payload, tnote = _post_form(
            "https://frost.met.no/auth/accessToken",
            {"client_id": client_id, "client_secret": secret,
             "grant_type": "client_credentials"},
        )
        if payload and payload.get("access_token"):
            print(f"      token:       HTTP {status}, {payload.get('expires_in')}s")
            code, body, note = _get(
                "https://frost.met.no/sources/v0.jsonld?county=Oslo",
                {"Authorization": f"Bearer {payload['access_token']}"},
            )
            print(f"      bearer:      HTTP {code}  "
                  f"{_rows(body) if body is not None else note}")
            ok = ok or code == 200
        else:
            print(f"      token:       HTTP {status} {tnote}")
    print()
    return ok


def check_nve(env: dict[str, str], ask: str | None) -> bool:
    key = ask if ask else env.get("NVE_HYDAPI_API_KEY", "")
    print("  NVE_HYDAPI_API_KEY")
    if not key:
        print("      not set\n")
        return False
    print(f"      {_shape(key)}")
    code, body, note = _get("https://hydapi.nve.no/api/v1/Parameters", {"X-API-Key": key})
    print(f"      X-API-Key:   HTTP {code}  {_rows(body) if body is not None else note}")
    if code == 401:
        # The same 401 arrives with no key at all, so the status alone does not
        # say whether the header or the value is wrong. Saying so beats a bare
        # 401 that sends the reader to try other header names, which do not
        # help: NVE documents X-API-Key and it is the one in use here.
        bare, _body, _note = _get("https://hydapi.nve.no/api/v1/Parameters", {})
        print(f"      no key:      HTTP {bare} -- so the 401 is the key being refused,")
        print("      not the header. NVE cannot show you an existing key again; make a")
        print("      new one at https://hydapi.nve.no/Users (free, several per email,")
        print("      older keys keep working) and copy it whole.")
    elif code == 200:
        for url in (
            "https://hydapi.nve.no/api/v1/Stations?Active=1",
            "https://hydapi.nve.no/api/v1/Series?StationId=1.200.0",
        ):
            inner, payload, inote = _get(url, {"X-API-Key": key})
            print(f"      HTTP {inner}  {_rows(payload) if payload is not None else inote}  {url}")
    print()
    return code == 200


CHECKS = {
    "barentswatch": check_barentswatch,
    "frost": check_frost,
    "nve": check_nve,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", default=".env")
    parser.add_argument("--only", action="append", default=[], choices=sorted(CHECKS))
    parser.add_argument("--ask", metavar="PUBLISHER", choices=sorted(CHECKS),
                        help="prompt for that publisher's secret instead of reading it")
    args = parser.parse_args()
    env = read_dotenv(Path(args.env))
    wanted = args.only or sorted(CHECKS)
    typed = None
    if args.ask:
        from getpass import getpass
        typed = getpass(f"secret for {args.ask} (not echoed): ").strip() or None
        wanted = [args.ask]
    results = []
    for name in wanted:
        print(f"=== {name}")
        results.append(CHECKS[name](env, typed if name == args.ask else None))
    return 0 if any(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
