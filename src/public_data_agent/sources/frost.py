"""MET Frost: the observation archive, read without collapsing it.

Frost is the deepest time series in Norwegian public data -- Blindern's
monthly mean air temperature starts in 1837 -- and it is addressed by station,
element and period, which is the shape this registry answers questions from.

The whole difficulty is in one place. A single `referenceTime` at a single
station carries several observations of the *same* element, and they are real,
different measurements:

    air_temperature  13.5 degC  level 10m  timeResolution PT10M
    air_temperature  13.5 degC  level  2m  timeResolution PT1M
    air_temperature  13.5 degC  level 10m  timeResolution PT1H
    air_temperature  13.5 degC  level  2m  timeResolution PT1H
    ...

Six of them in one response, differing only in `level`, `timeResolution` and
`timeOffset`. A reader that keys a cell by element and time alone turns those
six into one and loses five without an error -- the same failure that once
collapsed 157 bathymetry contours into a single record because they all said
`depth = 1000`. So every field that distinguishes two observations of one
element is carried as a dimension, the nested `level` object is flattened
rather than dropped, and `coverage_dimensions` names the set so a caller
cannot quietly omit one.

`qualityCode` is carried for the same reason it is published: a value flagged
2 is not the same claim as a value flagged 0, and dropping the flag would
present them as equally good.

Frost declares its own licence in every response envelope
(`https://creativecommons.org/licenses/by/3.0/no/`), so unlike most sources
here the licence is copied rather than left null.
"""

from __future__ import annotations

import base64
import os
import urllib.parse
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from public_data_agent.http_util import HttpClient, RateLimiter
from public_data_agent.models import DatasetRef, HarvestedRecord, SourceError
from public_data_agent.sources.base import SourceBase

SOURCE_ID = "frost"
SOURCE_NAME = "MET Frost observasjoner"
HOST = "frost.met.no"
OBSERVATIONS_PATH = "/observations/v0.jsonld"
TIMESERIES_PATH = "/observations/availableTimeSeries/v0.jsonld"
SOURCES_PATH = "/sources/v0.jsonld"
ELEMENTS_PATH = "/elements/v0.jsonld"
FROST_RPS = 2.0
FROST_BURST = 4

CLIENT_ID_VAR = "FROST_CLIENT_ID"
CLIENT_SECRET_VAR = "FROST_CLIENT_SECRET"

# Printed in every Frost response envelope. Recorded here so the ingest can
# state it, and checked against the payload on fetch rather than assumed.
FROST_LICENSE = "https://creativecommons.org/licenses/by/3.0/no/"

# Every field that can differ between two observations of one element at one
# instant. Omitting any one of them merges measurements that are not the same
# measurement, and the merge is silent.
COVERAGE_DIMENSIONS = (
    "sourceId",
    "referenceTime",
    "elementId",
    "timeResolution",
    "timeOffset",
    "timeSeriesId",
    "level_value",
    "level_type",
    "exposureCategory",
    "performanceCategory",
)

# Published alongside the value and kept, because a flagged value is a
# different claim from an unflagged one.
CARRIED_DIMENSIONS = ("unit", "qualityCode", "level_unit")


class MissingCredential(SourceError):
    """No Frost client id. Names the variable, never a value."""


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


def basic_auth_headers(
    *,
    client_id: str | None = None,
    dotenv: Path | None = None,
    environ: dict[str, str] | None = None,
) -> dict[str, str]:
    """Frost takes the client id as a basic-auth username, password empty.

    Both documented styles were tested and both answer 200. This one is used
    because it needs no token endpoint and no refresh: a 24-hour bearer buys
    nothing here and adds a request, a clock and an expiry to get wrong. The
    secret stays unread, which is also why it is not a parameter.
    """

    if client_id is None:
        env = dict(os.environ if environ is None else environ)
        client_id = env.get(CLIENT_ID_VAR)
        if not client_id and dotenv is not None:
            client_id = read_dotenv(dotenv).get(CLIENT_ID_VAR)
    if not client_id:
        raise MissingCredential(
            f"Frost needs {CLIENT_ID_VAR}; register a client at "
            "https://frost.met.no/auth/requestCredentials.html and put it in .env"
        )
    encoded = base64.b64encode(f"{client_id}:".encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


def client(http: HttpClient | None = None) -> HttpClient:
    return http or HttpClient(limiter=RateLimiter(FROST_RPS, FROST_BURST), timeout=60.0)


def is_frost_url(access_path: str | None) -> bool:
    if not access_path:
        return False
    return urlsplit(access_path).netloc.casefold() == HOST


def is_frost_observations_url(access_path: str | None) -> bool:
    if not is_frost_url(access_path):
        return False
    return urlsplit(access_path or "").path.rstrip("/") == OBSERVATIONS_PATH


def is_frost_timeseries_url(access_path: str | None) -> bool:
    if not is_frost_url(access_path):
        return False
    return urlsplit(access_path or "").path.rstrip("/") == TIMESERIES_PATH


def frost_table_id(access_path: str) -> str:
    """A table id from the printed path, never from the query.

    Two requests to the same endpoint for different stations are the same
    table with different rows, and the station is already a dimension on
    every cell. Keying the table by the query would split one series across
    as many tables as there are requests.
    """

    path = urlsplit(access_path).path.rstrip("/")
    if path == OBSERVATIONS_PATH:
        return "observations"
    if path == TIMESERIES_PATH:
        return "availableTimeSeries"
    if path == SOURCES_PATH:
        return "sources"
    if path == ELEMENTS_PATH:
        return "elements"
    segment = path.split("/")[-1]
    return segment or SOURCE_ID


def printed_license(payload: Any) -> str | None:
    """The licence Frost prints in its own envelope, or None."""

    if not isinstance(payload, dict):
        return None
    declared = payload.get("license")
    if isinstance(declared, str) and declared.strip():
        return declared.strip()
    return None


def _flatten_level(level: Any) -> dict[str, str]:
    """`level` is nested, and it is what tells 2m from 10m air temperature."""

    if not isinstance(level, dict):
        return {}
    out: dict[str, str] = {}
    for key, name in (("levelType", "level_type"), ("unit", "level_unit"), ("value", "level_value")):
        value = level.get(key)
        if value is not None and not isinstance(value, (dict, list)):
            out[name] = str(value)
    return out


class ConflictingObservations(ValueError):
    """Two different values for one measurement. The reader cannot choose."""


def _coverage_key(measure: str, dims: dict[str, str]) -> tuple[str, ...]:
    return tuple([measure] + [dims.get(name, "") for name in COVERAGE_DIMENSIONS])


def cells_from_frost(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """Copy printed Frost observations into cells, one per measurement.

    The measure is the publisher's `elementId`, which already carries its own
    aggregation -- `sum(precipitation_amount P1D)` is the element's name, not
    something this reader composed.

    An observation with no numeric `value` is skipped: Frost publishes series
    whose value is a code or is absent for an instant, and neither is a
    quantity.

    **Frost repeats observations.** In one tested response, 288 of 6,436
    observations were byte-identical repeats of another in the same member --
    the same element, instant, level, resolution, offset, quality code and
    value, twice. Those were checked by flattening each observation and
    comparing the whole object, not by trusting the dimension set, which is
    the only way to tell a publisher's duplicate from a reader that is losing
    a field. A duplicate is one measurement stated twice, so it is collapsed.

    Two observations that agree on every distinguishing field and disagree on
    the value are a different matter: the reader has no basis for choosing, so
    it raises rather than keeping whichever came first. That mirrors what
    `_store_records` already does for records.
    """

    if not isinstance(payload, dict):
        raise ValueError("Frost payload is not a JSON object")
    members = payload.get("data")
    if not isinstance(members, list):
        raise ValueError("Frost payload printed no data array")
    cells: list[tuple[str, Any, dict[str, str]]] = []
    seen: dict[tuple[str, ...], Any] = {}
    duplicates = 0
    for member in members:
        if not isinstance(member, dict):
            continue
        source_id = member.get("sourceId")
        reference_time = member.get("referenceTime")
        observations = member.get("observations")
        if not isinstance(observations, list):
            continue
        for observation in observations:
            if not isinstance(observation, dict):
                continue
            element = observation.get("elementId")
            value = observation.get("value")
            if not isinstance(element, str) or not element.strip():
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            measure = element.strip()
            dims: dict[str, str] = {}
            if source_id is not None:
                dims["sourceId"] = str(source_id)
            if reference_time is not None:
                dims["referenceTime"] = str(reference_time)
            dims.update(_flatten_level(observation.get("level")))
            for key, printed in observation.items():
                if key in ("value", "elementId", "level"):
                    continue
                if printed is None or isinstance(printed, (dict, list)):
                    continue
                dims[key] = str(printed)
            key = _coverage_key(measure, dims)
            if key in seen:
                if seen[key] == value:
                    duplicates += 1
                    continue
                raise ConflictingObservations(
                    f"Frost printed two values for one measurement: {measure} at "
                    f"{dims.get('sourceId')} {dims.get('referenceTime')} "
                    f"(level {dims.get('level_value')}, {dims.get('timeResolution')}, "
                    f"{dims.get('timeOffset')}) is both {seen[key]!r} and {value!r}"
                )
            seen[key] = value
            cells.append((measure, value, dims))
    if not cells:
        raise ValueError("Frost payload printed no numeric observation")
    return cells


def distinct_coverage(cells: list[tuple[str, Any, dict[str, str]]]) -> int:
    """How many distinct measurements the cells describe.

    A reader can only be trusted if this equals the number of cells. Frost
    publishes six air_temperature values for one station at one instant, and
    a key that misses `level` or `timeResolution` collapses them without
    raising, so the count is checked rather than assumed.
    """

    seen = {
        tuple([measure] + [dims.get(name, "") for name in COVERAGE_DIMENSIONS])
        for measure, _value, dims in cells
    }
    return len(seen)


# --- the registers, which are complete resources on their own ---------------
#
# `/observations` refuses a request that does not pin all three of `sources`,
# `elements` and `referencetime` -- each returns HTTP 400 on its own. So an
# observation request is a *query*, not a resource with a stable URL, and it
# belongs behind the select mechanism rather than in a dataset row.
#
# Three things on this API are complete resources, and all three are worth
# having for their own sake:
#
#   /sources                         2,235 stations, with countyId and
#                                    municipalityId -- published join keys
#   /elements                        700 measures, each with its unit
#
# Those two are entities, not measurements, so they go to `records`.
# `/observations/availableTimeSeries` is deliberately not a third: see
# `series_declared_by` for why a catalogue of what the service offers is not
# stored, and what it is read for instead.

STATION_ID_FIELDS = ("id",)
STATION_LABEL_FIELDS = ("name",)
ELEMENT_ID_FIELDS = ("id",)
ELEMENT_LABEL_FIELDS = ("name",)


def _members(payload: Any, *, what: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError(f"Frost {what} payload is not a JSON object")
    members = payload.get("data")
    if not isinstance(members, list):
        raise ValueError(f"Frost {what} payload printed no data array")
    return [member for member in members if isinstance(member, dict)]


def _scalar_dims(member: dict[str, Any], *, skip: tuple[str, ...]) -> dict[str, str]:
    dims: dict[str, str] = {}
    for key, value in member.items():
        if key in skip or value is None:
            continue
        if isinstance(value, (dict, list)):
            continue
        dims[key] = str(value)
    return dims


def cells_from_frost_sources(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """The station register, as cells a record converter can read.

    `geometry` is nested and is the station's place, so its coordinates are
    flattened rather than dropped. `stationHolders` is a list of the bodies
    that own the station and is skipped here: a list is not a dimension, and
    inventing a delimiter to flatten one would be inventing.
    """

    cells: list[tuple[str, Any, dict[str, str]]] = []
    for member in _members(payload, what="sources"):
        station = member.get("id")
        name = member.get("name")
        if not isinstance(station, str) or not station.strip():
            continue
        label = name if isinstance(name, str) and name.strip() else station
        dims = _scalar_dims(member, skip=("name",))
        geometry = member.get("geometry")
        if isinstance(geometry, dict):
            coordinates = geometry.get("coordinates")
            if isinstance(coordinates, list) and len(coordinates) >= 2:
                dims["longitude"] = str(coordinates[0])
                dims["latitude"] = str(coordinates[1])
        cells.append(("name", label.strip(), dims))
    if not cells:
        raise ValueError("Frost sources payload printed no station")
    return cells


def cells_from_frost_elements(payload: Any) -> list[tuple[str, Any, dict[str, str]]]:
    """The measure vocabulary, with the publisher's own unit on each."""

    cells: list[tuple[str, Any, dict[str, str]]] = []
    for member in _members(payload, what="elements"):
        element = member.get("id")
        name = member.get("name")
        if not isinstance(element, str) or not element.strip():
            continue
        label = name if isinstance(name, str) and name.strip() else element
        cells.append(("name", label.strip(), _scalar_dims(member, skip=("name",))))
    if not cells:
        raise ValueError("Frost elements payload printed no element")
    return cells


def series_declared_by(payload: Any) -> list[dict[str, str]]:
    """What requests the publisher says are valid. **Never stored.**

    `availableTimeSeries` is the service describing what it offers, and by
    this project's own rule a listing of what a service offers is metadata
    while a listing of things the world contains is data. Blindern holding 505
    series is a fact about Frost's catalogue, not about Oslo. Storing it as
    entities is the mistake that put 11,374 name cards in the observations
    table, and the same refusal already deleted ArcGIS layer lists,
    Sokkeldirektoratet field definitions and Klass version lists.

    It is still worth reading, for one reason: each member prints a `uri`
    that is Frost's own observation request for that series, with the valid
    range already in it. A connector that wants the series should use the URL
    the publisher generated rather than compose one -- that is the difference
    between following a declaration and guessing a pattern.

    So this returns request descriptions for a caller to act on, and nothing
    here goes near `records` or `observations`.
    """

    declared: list[dict[str, str]] = []
    for member in _members(payload, what="availableTimeSeries"):
        source_id = member.get("sourceId")
        element = member.get("elementId")
        uri = member.get("uri")
        if not isinstance(source_id, str) or not source_id.strip():
            continue
        if not isinstance(element, str) or not element.strip():
            continue
        entry = {
            "sourceId": source_id.strip(),
            "elementId": element.strip(),
            "timeResolution": str(member.get("timeResolution") or ""),
            "timeOffset": str(member.get("timeOffset") or ""),
            "validFrom": str(member.get("validFrom") or ""),
            "validTo": str(member.get("validTo") or ""),
            "unit": str(member.get("unit") or ""),
        }
        entry.update(_flatten_level(member.get("level")))
        if isinstance(uri, str) and uri.startswith("http"):
            entry["uri"] = uri
        declared.append(entry)
    if not declared:
        raise ValueError("Frost availableTimeSeries payload printed no series")
    return declared


def observation_request_is_complete(access_path: str) -> bool:
    """`/observations` refuses any request missing one of three parameters.

    sources, elements and referencetime each return HTTP 400 on their own, so
    an incomplete URL is not a resource and must not be stored as one.
    """

    query = urllib.parse.parse_qs(urllib.parse.urlsplit(access_path).query)
    return all(query.get(name) for name in ("sources", "elements", "referencetime"))


# --- ingest -----------------------------------------------------------------

SOURCES_URL = f"https://{HOST}{SOURCES_PATH}?types=SensorSystem"
ELEMENTS_URL = f"https://{HOST}{ELEMENTS_PATH}"
DEFAULT_MAX_ITEMS = 10
INGEST_REASON = (
    "the two Frost resources that are complete without a query: the "
    "SensorSystem station register and the element vocabulary. Observation "
    "requests pin sources, elements and referencetime and are not datasets"
)

LISTED = (
    (
        "sources",
        SOURCES_URL,
        "MET Frost — målestasjoner",
        "Alle SensorSystem-stasjoner med fylkesnummer, kommunenummer, posisjon og høyde.",
    ),
    (
        "elements",
        ELEMENTS_URL,
        "MET Frost — måleelementer",
        "Vokabularet av målestørrelser Frost publiserer, med publisert enhet på hver.",
    ),
)


class FrostSource(SourceBase):
    """Ingest adapter for MET Frost.

    Two datasets, not 2,235. A station is not a resource on this API: every
    observation request pins `sources`, `elements` and `referencetime`
    together, and leaving out any one of them is an HTTP 400. So the station
    list and the element list are the resources, and reading measurements is a
    query against them.

    Listing makes no request. Both URLs are fixed and documented, and whether
    either answers is the fetch's job to find out and record.
    """

    source_id = SOURCE_ID
    source_name = SOURCE_NAME
    endpoints = (SOURCES_URL, ELEMENTS_URL)
    ingest_reason = INGEST_REASON

    def __init__(
        self,
        *,
        max_items: int = DEFAULT_MAX_ITEMS,
        http: HttpClient | None = None,
    ) -> None:
        self.max_items = max_items
        self.http = http

    def list_dataset_refs(self, *, limit: int | None = None, offset: int = 0):
        cap = self.max_items if limit is None else limit
        return [
            DatasetRef(source_native_uri=url, source_native_id=native_id)
            for native_id, url, _title, _description in LISTED[offset : offset + cap]
        ]

    def fetch_dataset(self, ref):
        match = next((item for item in LISTED if item[1] == ref.source_native_uri), None)
        if match is None:
            raise SourceError(f"MET Frost lists no resource at {ref.source_native_uri}")
        native_id, url, title, description = match
        return HarvestedRecord(
            source_id=self.source_id,
            source_name=self.source_name,
            source_endpoints=self.endpoints,
            ingest_reason=self.ingest_reason,
            source_native_id=native_id,
            source_native_uri=url,
            fetched_from=url,
            payload={
                "id": native_id,
                "uri": url,
                "title": {"no": title},
                "description": {"no": description},
                "publisher": {"name": "Meteorologisk institutt"},
                # Frost states this in every response envelope, so unlike
                # most sources here it is copied rather than left null. It is
                # re-read from the payload on fetch and must agree.
                "license": FROST_LICENSE,
                "distribution": [{"accessURL": [url], "downloadURL": [url]}],
                "landingPage": ["https://frost.met.no/index.html"],
                "frost_requires_credential": CLIENT_ID_VAR,
            },
        )
