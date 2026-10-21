"""What the MET Frost reader must not lose.

Frost puts several real measurements of one element at one instant in a single
response, differing only in level, resolution and offset. The payloads here
are trimmed copies of a live Blindern response, kept because every case below
is a way of silently losing some of them.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from public_data_agent.sources.frost import (
    CLIENT_ID_VAR,
    COVERAGE_DIMENSIONS,
    ConflictingObservations,
    MissingCredential,
    basic_auth_headers,
    cells_from_frost,
    distinct_coverage,
    frost_table_id,
    is_frost_observations_url,
    is_frost_timeseries_url,
    is_frost_url,
    printed_license,
)

OBS_URL = "https://frost.met.no/observations/v0.jsonld?sources=SN18700&elements=air_temperature"
TS_URL = "https://frost.met.no/observations/availableTimeSeries/v0.jsonld?sources=SN18700"
LICENCE = "https://creativecommons.org/licenses/by/3.0/no/"


def _obs(**over):
    base = {
        "elementId": "air_temperature",
        "value": 13.5,
        "unit": "degC",
        "level": {"levelType": "height_above_ground", "unit": "m", "value": 10},
        "timeOffset": "PT0H",
        "timeResolution": "PT10M",
        "timeSeriesId": 0,
        "performanceCategory": "C",
        "exposureCategory": "1",
        "qualityCode": 2,
    }
    base.update(over)
    return base


def _payload(observations, *, licence=LICENCE):
    return {
        "license": licence,
        "data": [
            {
                "sourceId": "SN18700:0",
                "referenceTime": "2026-10-01T00:00:00.000Z",
                "observations": observations,
            }
        ],
    }


# the six-at-one-instant case, which is the whole reason this reader exists
SIX = [
    _obs(),
    _obs(level={"levelType": "height_above_ground", "unit": "m", "value": 2},
         timeResolution="PT1M", qualityCode=0),
    _obs(timeResolution="PT1H"),
    _obs(level={"levelType": "height_above_ground", "unit": "m", "value": 2},
         timeResolution="PT1H", qualityCode=0),
    _obs(level={"levelType": "height_above_ground", "unit": "m", "value": 2},
         qualityCode=0),
    _obs(timeOffset="PT6H"),
]


def test_six_measurements_at_one_instant_all_survive() -> None:
    """They differ only in level, resolution and offset, and all six are real.

    A key of element plus time alone turns these into one cell and loses five
    without raising -- the same failure that once collapsed 157 bathymetry
    contours into one record because they all said depth = 1000.
    """

    cells = cells_from_frost(_payload(SIX))
    assert len(cells) == 6
    assert distinct_coverage(cells) == 6
    assert {measure for measure, _value, _dims in cells} == {"air_temperature"}


def test_every_coverage_dimension_is_load_bearing() -> None:
    """Dropping any one of them merges cells that are not the same measurement.

    This asserts its own premise: if a dimension could be removed without a
    collision, it would not belong in the set, and the test would say so.
    """

    cells = cells_from_frost(_payload(SIX))
    for dropped in ("level_value", "timeResolution", "timeOffset"):
        keys = {
            tuple([measure] + [dims.get(name, "") for name in COVERAGE_DIMENSIONS
                               if name != dropped])
            for measure, _value, dims in cells
        }
        assert len(keys) < len(cells), f"{dropped} is doing no work in the key"


def test_the_nested_level_is_flattened_not_dropped() -> None:
    """2m and 10m air temperature are different measurements."""

    cells = cells_from_frost(_payload([_obs()]))
    (_measure, _value, dims) = cells[0]
    assert dims["level_value"] == "10"
    assert dims["level_type"] == "height_above_ground"
    assert dims["level_unit"] == "m"
    assert "level" not in dims, "the nested object must not survive as a string"


def test_the_quality_flag_is_carried() -> None:
    """A value flagged 2 is not the same claim as a value flagged 0."""

    cells = cells_from_frost(_payload(SIX))
    flags = {dims["qualityCode"] for _measure, _value, dims in cells}
    assert flags == {"0", "2"}


def test_the_unit_comes_from_the_publisher() -> None:
    cells = cells_from_frost(_payload([_obs()]))
    assert cells[0][2]["unit"] == "degC"
    precipitation = cells_from_frost(
        _payload([_obs(elementId="sum(precipitation_amount P1D)", unit="mm", value=0.0,
                       level=None, timeResolution="P1D")])
    )
    assert precipitation[0][0] == "sum(precipitation_amount P1D)"
    assert precipitation[0][2]["unit"] == "mm"
    assert "level_value" not in precipitation[0][2], "a level-less series invents none"


def test_a_byte_identical_repeat_is_collapsed() -> None:
    """Frost repeats observations: 288 of 6,436 in one tested response.

    Verified by flattening each observation and comparing the whole object, so
    this is the publisher saying one thing twice rather than the reader losing
    a field.
    """

    cells = cells_from_frost(_payload([_obs(), _obs()]))
    assert len(cells) == 1
    assert cells[0][1] == 13.5


def test_two_values_for_one_measurement_raise_rather_than_pick_one() -> None:
    """Nothing in the response says which is the measurement, so neither does this."""

    with pytest.raises(ConflictingObservations) as caught:
        cells_from_frost(_payload([_obs(), _obs(value=99.0)]))
    message = str(caught.value)
    assert "air_temperature" in message
    assert "13.5" in message and "99.0" in message
    assert "SN18700:0" in message


def test_a_value_that_is_not_a_number_is_skipped() -> None:
    """Some Frost series publish a code, and a code is not a quantity."""

    cells = cells_from_frost(_payload([_obs(), _obs(elementId="snow_coverage_type", value="X")]))
    assert [measure for measure, _value, _dims in cells] == ["air_temperature"]
    with pytest.raises(ValueError, match="no numeric observation"):
        cells_from_frost(_payload([_obs(value=None), _obs(value="X")]))


def test_a_boolean_is_not_a_measurement() -> None:
    """bool is an int in Python, which is how a flag becomes a quantity."""

    with pytest.raises(ValueError, match="no numeric observation"):
        cells_from_frost(_payload([_obs(value=True)]))


def test_the_station_and_the_instant_ride_on_every_cell() -> None:
    cells = cells_from_frost(_payload(SIX))
    for _measure, _value, dims in cells:
        assert dims["sourceId"] == "SN18700:0"
        assert dims["referenceTime"] == "2026-10-01T00:00:00.000Z"


def test_the_licence_is_copied_because_frost_declares_one() -> None:
    """Unlike most sources here, so it must not be left null by habit."""

    assert printed_license(_payload(SIX)) == LICENCE
    assert printed_license(_payload(SIX, licence=None)) is None
    assert printed_license(_payload(SIX, licence="  ")) is None
    assert printed_license([{"license": LICENCE}]) is None


def test_a_payload_that_is_not_an_observation_response_is_refused() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_frost([_obs()])
    with pytest.raises(ValueError, match="no data array"):
        cells_from_frost({"license": LICENCE})


def test_the_table_id_comes_from_the_path_not_the_query() -> None:
    """Two stations are rows in one table, and the station is already a dimension.

    Keying the table by the query would split one series across as many tables
    as there are requests.
    """

    assert frost_table_id(OBS_URL) == "observations"
    assert frost_table_id(
        "https://frost.met.no/observations/v0.jsonld?sources=SN50540&elements=air_temperature"
    ) == "observations"
    assert frost_table_id(TS_URL) == "availableTimeSeries"
    assert frost_table_id("https://frost.met.no/sources/v0.jsonld?county=Oslo") == "sources"
    assert frost_table_id("https://frost.met.no/elements/v0.jsonld") == "elements"


def test_the_url_predicates_tell_the_endpoints_apart() -> None:
    assert is_frost_url(OBS_URL) and is_frost_url(TS_URL)
    assert is_frost_observations_url(OBS_URL)
    assert not is_frost_observations_url(TS_URL), (
        "availableTimeSeries is a catalogue of series, not observations"
    )
    assert is_frost_timeseries_url(TS_URL)
    assert not is_frost_timeseries_url(OBS_URL)
    assert not is_frost_url("https://api.met.no/weatherapi/locationforecast/2.0/compact")
    assert not is_frost_url(None)


# --- the credential ---------------------------------------------------------


def test_the_client_id_is_a_basic_auth_username_with_an_empty_password() -> None:
    """Both documented styles answer 200; this one needs no token and no clock."""

    headers = basic_auth_headers(client_id="abc-123")
    assert headers == {"Authorization": "Basic " + base64.b64encode(b"abc-123:").decode()}
    decoded = base64.b64decode(headers["Authorization"].split()[1]).decode()
    assert decoded.endswith(":"), "the password half stays empty"


def test_the_environment_is_read_and_the_secret_is_not() -> None:
    """The secret buys only a 24-hour bearer, which this connector does not use."""

    headers = basic_auth_headers(
        environ={CLIENT_ID_VAR: "from-env", "FROST_CLIENT_SECRET": "unused"}
    )
    decoded = base64.b64decode(headers["Authorization"].split()[1]).decode()
    assert decoded == "from-env:"


def test_a_missing_client_id_names_the_variable(tmp_path: Path) -> None:
    with pytest.raises(MissingCredential, match=CLIENT_ID_VAR):
        basic_auth_headers(environ={})
    with pytest.raises(MissingCredential, match="requestCredentials"):
        basic_auth_headers(environ={}, dotenv=tmp_path / "absent")


def test_dotenv_fills_what_the_environment_lacks(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text(f'{CLIENT_ID_VAR}="from-file"\n', encoding="utf-8")
    headers = basic_auth_headers(environ={}, dotenv=path)
    decoded = base64.b64decode(headers["Authorization"].split()[1]).decode()
    assert decoded == "from-file:"
    # the environment still wins where it has a value
    headers = basic_auth_headers(environ={CLIENT_ID_VAR: "from-env"}, dotenv=path)
    decoded = base64.b64decode(headers["Authorization"].split()[1]).decode()
    assert decoded == "from-env:"
