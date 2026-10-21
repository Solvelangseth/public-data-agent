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

from public_data_agent.models import SourceError
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


# --- the registers ----------------------------------------------------------


def _sources_payload():
    return {
        "license": LICENCE,
        "data": [
            {
                "@type": "SensorSystem",
                "id": "SN18700",
                "name": "OSLO - BLINDERN",
                "shortName": "Blindern",
                "country": "Norge",
                "countryCode": "NO",
                "county": "OSLO",
                "countyId": 3,
                "municipality": "OSLO",
                "municipalityId": 301,
                "masl": 94,
                "validFrom": "1931-01-01T00:00:00.000Z",
                "wigosId": "0-578-0-18700",
                "geometry": {"@type": "Point", "coordinates": [10.7201, 59.9423]},
                "stationHolders": ["MET.NO"],
                "externalIds": ["01492"],
            }
        ],
    }


def test_the_station_register_keeps_the_published_kommune_key() -> None:
    """countyId and municipalityId are MET's own keys into the kommune spine.

    They are the reason this register is worth storing at all, so losing one
    would be worse than losing the station.
    """

    from public_data_agent.entity_records import records_from_cells
    from public_data_agent.sources.frost import (
        STATION_ID_FIELDS, STATION_LABEL_FIELDS, cells_from_frost_sources,
    )

    (record,) = records_from_cells(
        cells_from_frost_sources(_sources_payload()),
        dataset_id="frost:sources", table_id="sources",
        id_fields=STATION_ID_FIELDS, label_fields=STATION_LABEL_FIELDS,
        prefix="frost", kind="entity",
    )
    assert record["subject_code"] == "SN18700"
    assert record["subject_label"] == "OSLO - BLINDERN"
    assert record["attributes"]["countyId"] == "3"
    assert record["attributes"]["municipalityId"] == "301"


def test_the_station_place_is_flattened_from_the_nested_geometry() -> None:
    """A station without its coordinates says a measurement exists, not where."""

    from public_data_agent.sources.frost import cells_from_frost_sources

    (_measure, _value, dims) = cells_from_frost_sources(_sources_payload())[0]
    assert dims["longitude"] == "10.7201"
    assert dims["latitude"] == "59.9423"
    assert "geometry" not in dims


def test_a_list_valued_field_is_not_flattened_into_a_dimension() -> None:
    """stationHolders is a list. Choosing a delimiter for it would be inventing."""

    from public_data_agent.sources.frost import cells_from_frost_sources

    payload = _sources_payload()
    assert payload["data"][0]["stationHolders"] == ["MET.NO"], "premise: it is a list"
    (_measure, _value, dims) = cells_from_frost_sources(payload)[0]
    assert "stationHolders" not in dims
    assert "externalIds" not in dims


def test_a_station_with_no_name_keeps_its_id_rather_than_inventing_one() -> None:
    from public_data_agent.sources.frost import cells_from_frost_sources

    payload = _sources_payload()
    payload["data"][0]["name"] = ""
    (_measure, value, _dims) = cells_from_frost_sources(payload)[0]
    assert value == "SN18700"


def test_the_element_vocabulary_carries_the_publishers_unit() -> None:
    from public_data_agent.entity_records import records_from_cells
    from public_data_agent.sources.frost import (
        ELEMENT_ID_FIELDS, ELEMENT_LABEL_FIELDS, cells_from_frost_elements,
    )

    payload = {
        "license": LICENCE,
        "data": [{"id": "air_temperature", "name": "Air temperature", "unit": "degC",
                  "category": "Temperature", "status": "CF-name"}],
    }
    (record,) = records_from_cells(
        cells_from_frost_elements(payload),
        dataset_id="frost:elements", table_id="elements",
        id_fields=ELEMENT_ID_FIELDS, label_fields=ELEMENT_LABEL_FIELDS,
        prefix="frost", kind="entity",
    )
    assert record["subject_code"] == "air_temperature"
    assert record["subject_label"] == "Air temperature"
    assert record["attributes"]["unit"] == "degC"


def test_the_registers_refuse_a_payload_with_no_members() -> None:
    from public_data_agent.sources.frost import (
        cells_from_frost_elements, cells_from_frost_sources,
    )

    with pytest.raises(ValueError, match="no station"):
        cells_from_frost_sources({"license": LICENCE, "data": []})
    with pytest.raises(ValueError, match="no element"):
        cells_from_frost_elements({"license": LICENCE, "data": []})
    with pytest.raises(ValueError, match="no data array"):
        cells_from_frost_sources({"license": LICENCE})


def test_the_series_catalogue_is_read_for_requests_and_never_stored() -> None:
    """505 series at one station is a fact about Frost's catalogue, not Oslo.

    It is read for the `uri` the publisher generates per series, which is a
    declared request rather than a composed one.
    """

    from public_data_agent.sources import frost
    from public_data_agent.sources.frost import series_declared_by

    payload = {
        "license": LICENCE,
        "data": [{
            "sourceId": "SN18700:0",
            "elementId": "best_estimate_mean(air_temperature P1M)",
            "timeResolution": "P1M", "timeOffset": "PT0H", "unit": "degC",
            "validFrom": "1837-04-01T00:00:00.000Z",
            "level": {"levelType": "height_above_ground", "unit": "m", "value": 2},
            "uri": "https://frost.met.no/observations/v0.jsonld?sources=SN18700:0&referencetime=1837-04-01",
        }],
    }
    (series,) = series_declared_by(payload)
    assert series["sourceId"] == "SN18700:0"
    assert series["validFrom"] == "1837-04-01T00:00:00.000Z"
    assert series["level_value"] == "2"
    assert series["uri"].startswith("https://frost.met.no/observations/")
    # the refusal is structural: there is no reader that turns these into rows
    assert not hasattr(frost, "cells_from_frost_timeseries")
    assert not hasattr(frost, "records_from_frost_timeseries")


def test_an_observation_request_must_pin_all_three_parameters() -> None:
    """Each of the three returns HTTP 400 on its own, so two thirds is not a resource."""

    from public_data_agent.sources.frost import observation_request_is_complete

    complete = (
        "https://frost.met.no/observations/v0.jsonld?sources=SN18700"
        "&elements=air_temperature&referencetime=2026-10-01/2026-10-02"
    )
    assert observation_request_is_complete(complete)
    for missing in (
        "https://frost.met.no/observations/v0.jsonld?sources=SN18700&elements=air_temperature",
        "https://frost.met.no/observations/v0.jsonld?sources=SN18700&referencetime=2026-10-01",
        "https://frost.met.no/observations/v0.jsonld?elements=air_temperature&referencetime=2026-10-01",
        "https://frost.met.no/observations/v0.jsonld",
    ):
        assert not observation_request_is_complete(missing), missing


# --- ingest and fetch -------------------------------------------------------


class _Served:
    def __init__(self, body) -> None:
        self.body = body
        self.seen: list[dict[str, str] | None] = []

    def get_json_response(self, url: str, *, headers=None):
        from public_data_agent.http_util import JsonResponse

        self.seen.append(headers)
        return JsonResponse(status=200, url=url, body=self.body)


def _registry(tmp_path: Path, dataset_id: str, access_path: str):
    from public_data_agent.registry import Registry

    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_dataset_identity(
        dataset_id=dataset_id, title=None, publisher_name=None,
        access_path=access_path, license=None,
    )
    return registry


def test_frost_lists_two_datasets_and_makes_no_request() -> None:
    """A station is not a resource here, so there are not 2,235 of them."""

    from public_data_agent.sources.frost import FrostSource

    class Explodes:
        def get_json_response(self, url, *, headers=None):
            raise AssertionError(f"listing must not request {url}")

    source = FrostSource(http=Explodes())
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == ["sources", "elements"]
    for ref in refs:
        payload = source.fetch_dataset(ref).payload
        assert payload["license"] == LICENCE, "Frost declares it, so it is copied"
        assert payload["frost_requires_credential"] == "FROST_CLIENT_ID"


def test_the_station_register_fetch_stores_records(tmp_path: Path) -> None:
    from public_data_agent.fetch import _fetch_frost

    registry = _registry(tmp_path, "frost:sources",
                         "https://frost.met.no/sources/v0.jsonld?types=SensorSystem")
    http = _Served(_sources_payload())
    result = _fetch_frost(
        registry, registry.get_dataset("frost:sources"), http=http,
        headers={"Authorization": "Basic xyz"},
    )
    assert http.seen == [{"Authorization": "Basic xyz"}]
    assert result.table_id == "sources"
    assert registry.observation_count() == 0, "a station list is not a measurement"
    rows = registry.list_records("frost:sources", kind="entity")
    assert [row["subject_code"] for row in rows] == ["SN18700"]
    registry.close()


def test_the_series_catalogue_url_is_refused_by_the_fetcher(tmp_path: Path) -> None:
    from public_data_agent.fetch import _fetch_frost

    registry = _registry(tmp_path, "frost:ts", TS_URL)
    with pytest.raises(SourceError, match="metadata"):
        _fetch_frost(registry, registry.get_dataset("frost:ts"), http=_Served({}),
                     headers={"Authorization": "Basic xyz"})
    assert registry.record_count("frost:ts") == 0
    registry.close()


def test_an_incomplete_observation_url_is_refused_before_the_request(tmp_path: Path) -> None:
    """Frost would answer 400, and the run would be recorded as a failed fetch."""

    from public_data_agent.fetch import _fetch_frost

    registry = _registry(tmp_path, "frost:obs", OBS_URL)
    http = _Served({"license": LICENCE, "data": []})
    with pytest.raises(SourceError, match="referencetime"):
        _fetch_frost(registry, registry.get_dataset("frost:obs"), http=http,
                     headers={"Authorization": "Basic xyz"})
    assert http.seen == [], "nothing should have been requested"
    registry.close()


def test_a_complete_observation_url_stores_observations(tmp_path: Path) -> None:
    from public_data_agent.fetch import _fetch_frost

    url = (
        "https://frost.met.no/observations/v0.jsonld?sources=SN18700"
        "&elements=air_temperature&referencetime=2026-10-01/2026-10-02"
    )
    registry = _registry(tmp_path, "frost:obs", url)
    result = _fetch_frost(
        registry, registry.get_dataset("frost:obs"), http=_Served(_payload(SIX)),
        headers={"Authorization": "Basic xyz"},
    )
    assert result.counts.listed == 6
    assert registry.observation_count() == 6, "all six survive the store, not just one"
    capability = registry.get_capability("frost:obs")
    assert capability["capability"] == "observations"
    assert "timeResolution" in capability["notes"]
    registry.close()


def test_a_changed_licence_stops_the_store(tmp_path: Path) -> None:
    """The licence is copied from Frost, so a change must not pass unnoticed."""

    from public_data_agent.fetch import _fetch_frost

    registry = _registry(tmp_path, "frost:sources",
                         "https://frost.met.no/sources/v0.jsonld?types=SensorSystem")
    moved = _sources_payload()
    moved["license"] = "https://creativecommons.org/licenses/by/4.0/"
    with pytest.raises(SourceError, match="needs updating"):
        _fetch_frost(registry, registry.get_dataset("frost:sources"), http=_Served(moved),
                     headers={"Authorization": "Basic xyz"})
    assert registry.record_count("frost:sources") == 0
    registry.close()


def test_frost_is_a_registered_source() -> None:
    from public_data_agent.sources import SOURCE_IDS, build_source
    from public_data_agent.sources.frost import FrostSource

    assert "frost" in SOURCE_IDS
    assert isinstance(build_source("frost"), FrostSource)
