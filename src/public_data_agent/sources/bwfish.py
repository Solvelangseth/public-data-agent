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

import datetime

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

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


# --- ingest -----------------------------------------------------------------
#
# There is no catalogue to list from: BarentsWatch publishes no OpenAPI
# document under /bwapi/ (openapi/v1/openapi.json, swagger/v1/swagger.json and
# openapi/index.json all 404). So the resources are enumerated, and the two
# things that could have been assumed were asked instead:
#
#   where the series starts   2011 w20 and earlier answer 200 with an empty
#                             localities array; 2012 w20 returns 1,936. So the
#                             weekly series begins in 2012.
#   how many weeks a year has week 0, 53 and 54 of 2024 are HTTP 400, while
#                             2020 w53 returns 1,696 rows. The publisher
#                             validates the week against the ISO calendar, so
#                             the year's real ISO week count is used -- not 52.
#
# A future week answers 200 with an empty array rather than 404, which is why
# the listing stops at the last completed ISO week rather than trusting the
# API to refuse one.

FIRST_YEAR = 2012
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "the fish health register, plus one resource per ISO week from "
    f"{FIRST_YEAR} to the last completed week; week counts from the ISO "
    "calendar, which the publisher validates against"
)


def iso_weeks_in(year: int) -> int:
    """How many ISO weeks a year has. 28 December is always in the last one."""

    return datetime.date(year, 12, 28).isocalendar()[1]


def last_complete_week(today=None) -> tuple[int, int]:
    """The most recent ISO year and week that has finished.

    The current week is excluded: it is still being reported, so a fetch of it
    would store a partial count and a re-fetch would change it. BarentsWatch
    answers it, which is exactly why this has to be decided here.
    """

    today = today or datetime.date.today()
    year, week, _weekday = (today - datetime.timedelta(days=7)).isocalendar()
    return year, week


def listed_weeks(today=None) -> list[tuple[int, int]]:
    year, week = last_complete_week(today)
    weeks: list[tuple[int, int]] = []
    for candidate in range(FIRST_YEAR, year + 1):
        last = week if candidate == year else iso_weeks_in(candidate)
        weeks.extend((candidate, number) for number in range(1, last + 1))
    return weeks


def week_url(year: int, week: int) -> str:
    return f"https://{HOST}{WEEK_MARK}{year}/{week}"


def localities_url() -> str:
    return f"https://{HOST}{LOCALITIES_PATH}"


class BwFishSource(SourceBase):
    """Ingest adapter for BarentsWatch Fiskehelse.

    Lists the site register and one resource per completed ISO week. It makes
    no request of its own: every listed resource is addressed by the
    publisher's own documented path shape, and whether a given week holds
    anything is the fetch's job to find out and record. That keeps a listing of
    780-odd weeks from costing 780 requests before a single one is stored.
    """

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = (f"https://{HOST}{PATH_MARK}",)
    ingest_reason = INGEST_REASON

    def __init__(
        self,
        *,
        max_items: int = DEFAULT_MAX_ITEMS,
        today=None,
        http: HttpClient | None = None,
    ) -> None:
        self.max_items = max_items
        self.today = today
        self.http = http

    def _listed(self) -> list[tuple[str, str, str]]:
        """(native id, url, title) for the register and every listed week."""

        listed = [("localities", localities_url(), "Fiskehelse — akvakulturlokaliteter")]
        for year, week in listed_weeks(self.today):
            listed.append(
                (
                    f"locality-{year}-{week:02d}",
                    week_url(year, week),
                    f"Fiskehelse — lakselus per lokalitet, {year} uke {week}",
                )
            )
        return listed

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0):
        cap = self.max_items if limit is None else limit
        return [
            DatasetRef(source_native_uri=url, source_native_id=native_id)
            for native_id, url, _title in self._listed()[offset : offset + cap]
        ]

    def fetch_dataset(self, ref):
        match = next(
            (item for item in self._listed() if item[1] == ref.source_native_uri),
            None,
        )
        if match is None:
            raise SourceError(
                f"BarentsWatch fish health lists no resource at {ref.source_native_uri}"
            )
        native_id, url, title = match
        payload = {
            "id": native_id,
            "uri": url,
            "title": {"no": title},
            "description": {
                "no": (
                    "Gjennomsnittlig antall voksne hunnlus per fisk per "
                    "lokalitet per uke, med sykdomsstatus for ILA og PD."
                    if native_id != "localities"
                    else "Akvakulturlokaliteter med kommunenummer og posisjon."
                )
            },
            "publisher": {"name": "BarentsWatch"},
            # BarentsWatch prints no licence on these endpoints and there is no
            # OpenAPI document to carry one, so it stays null by the rule.
            "license": None,
            "distribution": [{"accessURL": [url], "downloadURL": [url]}],
            "landingPage": [f"https://{HOST}/bwapi/openapi/index.html"],
            "bwfish_requires_credential": "BARENTSWATCH_API_CLIENT_ID",
            "bwfish_scope": SCOPE,
        }
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=native_id,
            source_native_uri=url,
            fetched_from=url,
            payload=payload,
        )
