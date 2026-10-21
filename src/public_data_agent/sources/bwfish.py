"""BarentsWatch Fiskehelse: a lice count per fish farm per week.

What this connector exists for is one number. `avgAdultFemaleLice` is the
average count of adult female salmon lice per fish at a locality in a given
week, and it is the number the whole Norwegian aquaculture regime turns on:
the treatment threshold, the delousing orders, the production-area traffic
light. BarentsWatch publishes it per locality per week, back to 2012, beside
the booleans that say whether the site reported, whether it was fallow, and
whether ILA or PD was confirmed there.

Two endpoints, two different kinds of thing, so two readers:

    /fishhealth/locality/{year}/{week}   measurements -- observation cells
    /fishhealth/localities               the register -- entity records

The weekly endpoint publishes four other numbers and none of them is a
measurement: `localityNo` and `localityWeekId` are handles, `lat` and `lon`
are a place. Reading a number as a measurement because it is a number is the
mistake that put 11,374 name cards in the observations table, so the measure
is named here rather than inferred.

This is the first connector in the project that needs a credential. The token
is read from the environment or from `.env`, is never written to the registry,
and is cached in memory for its hour. BarentsWatch issues one scope per
client -- `api` or `ais` -- so the two have separate variables and a client
registered for one is refused by the other with `invalid_scope`.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import SourceError

SOURCE_ID = "bwfish"
SOURCE_NAME = "BarentsWatch Fiskehelse"
HOST = "www.barentswatch.no"
PATH_MARK = "/bwapi/v1/geodata/fishhealth/"
WEEK_MARK = "/bwapi/v1/geodata/fishhealth/locality/"
LOCALITIES_PATH = "/bwapi/v1/geodata/fishhealth/localities"
TOKEN_URL = "https://id.barentswatch.no/connect/token"
BWFISH_RPS = 2.0
BWFISH_BURST = 4

# The one measurement on the weekly row. Adult female lice per fish, which is
# what the regulation counts.
MEASURE = "avgAdultFemaleLice"

# Published, numeric, and not measurements. Kept as dimensions so a record
# stays addressable, never promoted to a measure.
HANDLE_FIELDS = ("localityNo", "localityWeekId")
PLACE_FIELDS = ("lat", "lon")

# `inFilteredSelection` answers "is this row inside the selection you asked
# for", which is a fact about the request and not about the locality. The
# project refuses response metadata as data, and a dimension is still data.
RESPONSE_FIELDS = frozenset({"inFilteredSelection"})

# What the register addresses a site by, and what it prints as the name.
LOCALITY_ID_FIELDS = ("localityNo",)
LOCALITY_LABEL_FIELDS = ("name",)

# One scope per client, so one pair of variables per scope.
CREDENTIALS = {
    "api": ("BARENTSWATCH_API_CLIENT_ID", "BARENTSWATCH_API_CLIENT_SECRET"),
    "ais": ("BARENTSWATCH_CLIENT_ID", "BARENTSWATCH_CLIENT_SECRET"),
}
SCOPE = "api"

# A token lasts 3600s. Renewing a minute early costs one request an hour and
# removes the case where a token expires between being read and being used.
RENEW_MARGIN = 60.0


class MissingCredential(SourceError):
    """No client id and secret for this scope. Names the variables, not values."""


class BarentsWatchToken:
    """A cached client-credentials token for one BarentsWatch scope.

    The secret is held only here and only in memory. Nothing in this class
    prints it, and `repr` is left as the default on purpose: the attributes
    are not the secret, the local is.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        scope: str = SCOPE,
        token_url: str = TOKEN_URL,
        opener=urllib.request.urlopen,
        clock=time.monotonic,
    ) -> None:
        if not client_id or not client_secret:
            raise MissingCredential("BarentsWatch client id and secret are both required")
        self._client_id = client_id
        self._client_secret = client_secret
        self.scope = scope
        self.token_url = token_url
        self._opener = opener
        self._clock = clock
        self._token: str | None = None
        self._expires_at = 0.0

    @classmethod
    def from_env(
        cls,
        *,
        scope: str = SCOPE,
        dotenv: Path | None = None,
        environ: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> "BarentsWatchToken":
        try:
            id_var, secret_var = CREDENTIALS[scope]
        except KeyError:
            raise MissingCredential(
                f"BarentsWatch issues no scope {scope!r}; known scopes: {sorted(CREDENTIALS)}"
            ) from None
        env = dict(os.environ if environ is None else environ)
        values = {id_var: env.get(id_var), secret_var: env.get(secret_var)}
        if dotenv is not None and not all(values.values()):
            from_file = read_dotenv(dotenv)
            for key, value in values.items():
                if not value:
                    values[key] = from_file.get(key)
        missing = sorted(key for key, value in values.items() if not value)
        if missing:
            raise MissingCredential(
                f"BarentsWatch scope {scope!r} needs {' and '.join(missing)}; "
                f"register a client at https://www.barentswatch.no/minside/ "
                f"({'API-client' if scope == 'api' else 'AIS-client'}) and put the "
                f"pair in .env"
            )
        return cls(values[id_var] or "", values[secret_var] or "", scope=scope, **kwargs)

    def token(self) -> str:
        if self._token is not None and self._clock() < self._expires_at:
            return self._token
        body = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": self.scope,
            }
        ).encode()
        request = urllib.request.Request(
            self.token_url,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with self._opener(request, timeout=30) as response:
                payload = json.loads(response.read())
        except Exception as exc:
            # An id and secret that are not a recognised pair, and a pair
            # registered for the other scope, are different problems with
            # different fixes, and the server says which in the body.
            raise SourceError(
                f"BarentsWatch refused the {self.scope!r} client credentials: "
                f"{_token_error(exc)}"
            ) from exc
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token:
            raise SourceError("BarentsWatch token response printed no access_token")
        lifetime = payload.get("expires_in")
        lifetime = float(lifetime) if isinstance(lifetime, (int, float)) else 3600.0
        self._token = token
        self._expires_at = self._clock() + max(lifetime - RENEW_MARGIN, 0.0)
        return token

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token()}"}


def _token_error(exc: Exception) -> str:
    """The server's own word for what was wrong, without the secret in it."""

    read = getattr(exc, "read", None)
    if callable(read):
        try:
            raw = read()
        except Exception:
            raw = b""
        text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
        try:
            named = json.loads(text).get("error")
        except Exception:
            named = None
        if isinstance(named, str) and named:
            code = getattr(exc, "code", None)
            return f"HTTP {code} {named}" if code else named
    return f"{type(exc).__name__}"


def read_dotenv(path: Path) -> dict[str, str]:
    """Variables from a dotenv file. Absent file reads as empty, not an error."""

    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        values[key] = value.strip().strip('"').strip("'")
    return values


def client(http: HttpClient | None = None) -> HttpClient:
    return http or HttpClient(limiter=RateLimiter(BWFISH_RPS, BWFISH_BURST), timeout=60.0)


def is_bwfish_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    parsed = urlsplit(access_path)
    return parsed.netloc.casefold() == HOST and parsed.path.startswith(PATH_MARK)


def is_bwfish_week_url(access_path: str | None) -> bool:
    """A `{year}/{week}` locality request. The per-locality detail is longer."""

    return _week_of(access_path) is not None


def is_bwfish_localities_url(access_path: str | None) -> bool:
    if not is_bwfish_url(access_path):
        return False
    return urlsplit(access_path or "").path.rstrip("/").casefold() == LOCALITIES_PATH


def _week_of(access_path: str | None) -> tuple[str, str] | None:
    if not is_bwfish_url(access_path):
        return None
    path = urlsplit(access_path or "").path
    if not path.startswith(WEEK_MARK):
        return None
    rest = [part for part in path[len(WEEK_MARK) :].split("/") if part]
    if len(rest) != 2 or not all(part.isdigit() for part in rest):
        return None
    return rest[0], rest[1]


def bwfish_table_id(access_path: str) -> str:
    """A table id from the printed path, so a re-fetch lands in the same table."""

    week = _week_of(access_path)
    if week is not None:
        year, number = week
        return f"locality-{year}-{int(number):02d}"
    if is_bwfish_localities_url(access_path):
        return "localities"
    segment = urlsplit(access_path).path.rstrip("/").split("/")[-1]
    return segment or SOURCE_ID


def cells_from_bwfish_week(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy one week's printed lice counts into observation cells.

    The envelope prints `year` and `week` once and the localities under
    `localities`; both ride along as dimensions because they are the period
    the count belongs to, and they come from the response rather than from
    the URL so a mislabelled request cannot invent a period.

    A locality whose `avgAdultFemaleLice` is null reported no count that
    week -- most often because it was fallow -- and is skipped. That is an
    absent measurement, not a zero, and writing a zero would be inventing
    the one number this connector exists for.
    """

    if not isinstance(payload, dict):
        raise ValueError("BarentsWatch fish health week payload is not a JSON object")
    members = payload.get("localities")
    if not isinstance(members, list):
        raise ValueError("BarentsWatch fish health week payload printed no localities array")
    period = {
        key: _as_dim(payload.get(key))
        for key in ("year", "week")
        if _is_scalar(payload.get(key)) and payload.get(key) is not None
    }
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for member in members:
        if not isinstance(member, dict):
            continue
        value = member.get(MEASURE)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        dims = dict(period)
        dims.update(
            {
                key: _as_dim(other)
                for key, other in member.items()
                if key != MEASURE and key not in RESPONSE_FIELDS and _is_scalar(other)
            }
        )
        cells.append((MEASURE, value, dims))
    if not cells:
        raise ValueError(
            "BarentsWatch fish health week payload printed no "
            f"{MEASURE} for any locality"
        )
    return cells


def cells_from_bwfish_localities(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy the printed site register into cells a record converter can read.

    The register is a list of places, not of measurements, so the cell's
    measure is the field the name is printed under and the identity rides as
    a dimension. `records_from_cells` reads that shape.
    """

    if not isinstance(payload, list):
        raise ValueError("BarentsWatch localities payload is not a JSON array")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for member in payload:
        if not isinstance(member, dict):
            continue
        name = member.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        dims = {
            key: _as_dim(value)
            for key, value in member.items()
            if key != "name" and key not in RESPONSE_FIELDS and _is_scalar(value)
        }
        cells.append(("name", name.strip(), dims))
    if not cells:
        raise ValueError("BarentsWatch localities payload printed no named site")
    return cells


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _as_dim(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
