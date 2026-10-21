"""What the BarentsWatch fish health reader must and must not do.

The payloads here are trimmed copies of real responses, with the field set
confirmed stable from 2015 to 2024. The cases are the ones a reader of this
shape gets wrong: a number that is a handle, a null that is not a zero, and a
credential error whose message has to say which half is missing without
printing either.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
from io import BytesIO
from pathlib import Path

import pytest

from public_data_agent.entity_records import records_from_cells
from public_data_agent.models import SourceError
from public_data_agent.sources.bwfish import (
    LOCALITY_ID_FIELDS,
    LOCALITY_LABEL_FIELDS,
    MEASURE,
    BarentsWatchToken,
    MissingCredential,
    bwfish_table_id,
    cells_from_bwfish_localities,
    cells_from_bwfish_week,
    is_bwfish_localities_url,
    is_bwfish_url,
    is_bwfish_week_url,
    read_dotenv,
)

WEEK_URL = "https://www.barentswatch.no/bwapi/v1/geodata/fishhealth/locality/2024/20"
LOCALITIES_URL = "https://www.barentswatch.no/bwapi/v1/geodata/fishhealth/localities"

REPORTED = {
    "localityNo": 35297,
    "localityWeekId": 1682665,
    "name": "Ådnøy Sø",
    "municipality": "Sandnes",
    "municipalityNo": "1108",
    "lat": 58.849,
    "lon": 5.733,
    "avgAdultFemaleLice": 0.11,
    "hasReportedLice": True,
    "hasSalmonoids": True,
    "isFallow": False,
    "isOnLand": False,
    "hasIla": False,
    "hasPd": False,
    "hasMechanicalRemoval": False,
    "hasSubstanceTreatments": True,
    "hasCleanerfishDeployed": False,
    "isSlaughterHoldingCage": False,
    "inFilteredSelection": True,
}
FALLOW = dict(REPORTED, localityNo=14746, localityWeekId=1682600, name="Aarsand",
              municipality="Bindal", municipalityNo="1811",
              avgAdultFemaleLice=None, hasReportedLice=False, isFallow=True)
WEEK = {"year": 2024, "week": 20, "localities": [REPORTED, FALLOW]}


def test_the_week_url_is_told_from_the_per_locality_detail() -> None:
    """`/locality/{year}/{week}` is a week; `/locality/{no}/{year}/{week}` is not.

    Both start with the same five segments, so a prefix test routes the
    detail payload -- which holds escapes and ILA zones, not a lice count --
    into the week reader and it raises on a payload it should never see.
    """

    detail = "https://www.barentswatch.no/bwapi/v1/geodata/fishhealth/locality/14746/2024/20"
    assert is_bwfish_url(WEEK_URL) and is_bwfish_url(detail)
    assert is_bwfish_week_url(WEEK_URL)
    assert not is_bwfish_week_url(detail)
    assert not is_bwfish_week_url(LOCALITIES_URL)
    assert is_bwfish_localities_url(LOCALITIES_URL)
    assert not is_bwfish_localities_url(WEEK_URL)


def test_another_host_is_not_ours() -> None:
    assert not is_bwfish_url("https://live.ais.barentswatch.no/v1/latest/combined")
    assert not is_bwfish_url("https://geo.barentswatch.no/geoserver/bw/ows")
    assert not is_bwfish_url(None)


def test_the_table_id_pads_the_week_so_it_sorts() -> None:
    assert bwfish_table_id(WEEK_URL) == "locality-2024-20"
    assert bwfish_table_id(
        "https://www.barentswatch.no/bwapi/v1/geodata/fishhealth/locality/2024/1"
    ) == "locality-2024-01"
    assert bwfish_table_id(LOCALITIES_URL) == "localities"


def test_only_the_lice_count_is_a_measure() -> None:
    """Four other numbers are printed and none of them is a measurement.

    localityNo and localityWeekId are handles, lat and lon are a place. A
    reader that promotes numbers by type stores a farm's id as a quantity,
    which is the mistake that put 11,374 name cards in the observations table.
    """

    cells = cells_from_bwfish_week(WEEK)
    assert [measure for measure, _value, _dims in cells] == [MEASURE]
    (_measure, value, dims) = cells[0]
    assert value == 0.11
    for handle in ("localityNo", "localityWeekId", "lat", "lon"):
        assert handle in dims, f"{handle} must survive as a dimension"


def test_a_fallow_site_is_absent_not_zero() -> None:
    """A null count means the site reported nothing, most often while fallow.

    Writing a zero would state that the lice count was measured and found to
    be none, which is a different claim and the one number this connector is
    for.
    """

    cells = cells_from_bwfish_week(WEEK)
    assert len(cells) == 1, "the fallow locality must not become a cell"
    assert WEEK["localities"][1]["avgAdultFemaleLice"] is None, "premise: it is null"
    values = [value for _measure, value, _dims in cells]
    assert 0 not in values and 0.0 not in values


def test_the_period_comes_from_the_response_not_the_url() -> None:
    """The envelope prints year and week, so a mislabelled request cannot lie."""

    (_measure, _value, dims) = cells_from_bwfish_week(WEEK)[0]
    assert dims["year"] == "2024"
    assert dims["week"] == "20"
    shifted = dict(WEEK, year=2019, week=33)
    (_m, _v, moved) = cells_from_bwfish_week(shifted)[0]
    assert (moved["year"], moved["week"]) == ("2019", "33")


def test_the_join_key_is_carried_as_published() -> None:
    """municipalityNo is the publisher's own key into every kommune dataset.

    It is a string with a leading-zero risk -- Oslo is "0301" -- so it must
    not pass through anything that would read it as a number.
    """

    (_measure, _value, dims) = cells_from_bwfish_week(WEEK)[0]
    assert dims["municipalityNo"] == "1108"
    oslo = dict(WEEK, localities=[dict(REPORTED, municipalityNo="0301")])
    (_m, _v, kept) = cells_from_bwfish_week(oslo)[0]
    assert kept["municipalityNo"] == "0301"


def test_the_request_artefact_is_not_stored_as_a_dimension() -> None:
    """`inFilteredSelection` answers a question about the request, not the farm."""

    (_measure, _value, dims) = cells_from_bwfish_week(WEEK)[0]
    assert "inFilteredSelection" in REPORTED, "premise: the publisher prints it"
    assert "inFilteredSelection" not in dims


def test_a_week_with_no_reported_count_raises_rather_than_storing_nothing() -> None:
    """An empty fetch that reports success is how a resource gets verified blind."""

    with pytest.raises(ValueError, match=MEASURE):
        cells_from_bwfish_week({"year": 2024, "week": 20, "localities": [FALLOW]})
    with pytest.raises(ValueError, match="localities array"):
        cells_from_bwfish_week({"year": 2024, "week": 20})
    with pytest.raises(ValueError, match="JSON object"):
        cells_from_bwfish_week([REPORTED])


def test_the_register_becomes_sites_keyed_by_locality_number() -> None:
    register = [
        {"localityNo": 35297, "name": "Ådnøy Sø", "municipality": "Sandnes",
         "municipalityNo": "1108", "aquaCultureRegistryVersion": 3},
    ]
    cells = cells_from_bwfish_localities(register)
    (record,) = records_from_cells(
        cells,
        dataset_id="bwfish:localities",
        table_id="localities",
        id_fields=LOCALITY_ID_FIELDS,
        label_fields=LOCALITY_LABEL_FIELDS,
        prefix="bwfish",
        kind="entity",
    )
    assert record["subject_code"] == "35297"
    assert record["subject_label"] == "Ådnøy Sø"
    assert record["attributes"]["municipalityNo"] == "1108"


def test_the_register_refuses_a_week_payload() -> None:
    with pytest.raises(ValueError, match="JSON array"):
        cells_from_bwfish_localities(WEEK)


# --- the credential ---------------------------------------------------------


def _fake_opener(payload: dict, *, calls: list):
    class Response:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def read(self) -> bytes:
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *_exc) -> bool:
            return False

    def opener(request, timeout=None):
        calls.append(urllib.parse.parse_qs(request.data.decode()))
        return Response(json.dumps(payload).encode())

    return opener


def test_a_missing_variable_is_named_and_the_other_is_not_printed() -> None:
    with pytest.raises(MissingCredential) as caught:
        BarentsWatchToken.from_env(environ={"BARENTSWATCH_API_CLIENT_ID": "you@example.com:c"})
    message = str(caught.value)
    assert "BARENTSWATCH_API_CLIENT_SECRET" in message
    assert "you@example.com:c" not in message, "an error must not echo the credential"


def test_an_unknown_scope_is_refused_before_any_request() -> None:
    with pytest.raises(MissingCredential, match="no scope"):
        BarentsWatchToken.from_env(scope="geodata", environ={})


def test_each_scope_reads_its_own_pair() -> None:
    """One client per scope, so the ais pair must not be used for api."""

    environ = {
        "BARENTSWATCH_CLIENT_ID": "you@example.com:ais",
        "BARENTSWATCH_CLIENT_SECRET": "ais-secret",
        "BARENTSWATCH_API_CLIENT_ID": "you@example.com:api",
        "BARENTSWATCH_API_CLIENT_SECRET": "api-secret",
    }
    calls: list = []
    for scope, expected in (("api", "you@example.com:api"), ("ais", "you@example.com:ais")):
        token = BarentsWatchToken.from_env(
            scope=scope, environ=environ,
            opener=_fake_opener({"access_token": "t", "expires_in": 3600}, calls=calls),
        )
        assert token.token() == "t"
    assert [call["client_id"][0] for call in calls] == [
        "you@example.com:api", "you@example.com:ais"
    ]
    assert [call["scope"][0] for call in calls] == ["api", "ais"]


def test_the_token_is_cached_for_its_hour_and_renewed_early() -> None:
    calls: list = []
    now = [1000.0]
    token = BarentsWatchToken(
        "you@example.com:api", "api-secret",
        opener=_fake_opener({"access_token": "t", "expires_in": 3600}, calls=calls),
        clock=lambda: now[0],
    )
    token.token()
    token.token()
    assert len(calls) == 1, "a cached token must not be re-requested"
    now[0] += 3600 - 59  # inside the renewal margin, before the real expiry
    token.token()
    assert len(calls) == 2, "the margin must renew before the token actually expires"


def test_the_token_header_is_a_bearer() -> None:
    token = BarentsWatchToken(
        "you@example.com:api", "api-secret",
        opener=_fake_opener({"access_token": "abc", "expires_in": 3600}, calls=[]),
    )
    assert token.headers() == {"Authorization": "Bearer abc"}


def test_the_servers_own_word_for_the_refusal_is_reported() -> None:
    """invalid_client and invalid_scope have different fixes, so say which."""

    def opener(request, timeout=None):
        raise urllib.error.HTTPError(
            "https://id.barentswatch.no/connect/token", 400, "Bad Request", {},
            BytesIO(json.dumps({"error": "invalid_scope"}).encode()),
        )

    token = BarentsWatchToken("you@example.com:api", "api-secret", opener=opener)
    with pytest.raises(SourceError, match="invalid_scope"):
        token.token()


def test_a_token_response_without_a_token_is_an_error_not_an_empty_bearer() -> None:
    token = BarentsWatchToken(
        "you@example.com:api", "api-secret",
        opener=_fake_opener({"token_type": "Bearer"}, calls=[]),
    )
    with pytest.raises(SourceError, match="no access_token"):
        token.token()


def test_dotenv_fills_only_what_the_environment_lacks(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text(
        '# a comment\n'
        'BARENTSWATCH_API_CLIENT_ID="you@example.com:api"\n'
        "export BARENTSWATCH_API_CLIENT_SECRET='file-secret'\n",
        encoding="utf-8",
    )
    values = read_dotenv(path)
    assert values["BARENTSWATCH_API_CLIENT_ID"] == "you@example.com:api"
    assert values["BARENTSWATCH_API_CLIENT_SECRET"] == "file-secret"
    calls: list = []
    token = BarentsWatchToken.from_env(
        environ={"BARENTSWATCH_API_CLIENT_SECRET": "env-secret"},
        dotenv=path,
        opener=_fake_opener({"access_token": "t", "expires_in": 3600}, calls=calls),
    )
    token.token()
    assert calls[0]["client_secret"][0] == "env-secret", "the environment wins"
    assert calls[0]["client_id"][0] == "you@example.com:api", "the file fills the gap"


def test_a_missing_dotenv_reads_as_empty(tmp_path: Path) -> None:
    assert read_dotenv(tmp_path / "nothing-here") == {}


# --- the fetch ---------------------------------------------------------------


class _Fetched:
    """One canned JSON response, recording the headers it was asked with."""

    def __init__(self, body) -> None:
        self.body = body
        self.seen: list[dict[str, str] | None] = []

    def get_json_response(self, url: str, *, headers=None):
        from public_data_agent.http_util import JsonResponse

        self.seen.append(headers)
        return JsonResponse(status=200, url=url, body=self.body)


def _token() -> BarentsWatchToken:
    return BarentsWatchToken(
        "you@example.com:api", "api-secret",
        opener=_fake_opener({"access_token": "abc", "expires_in": 3600}, calls=[]),
    )


def _registry(tmp_path: Path, dataset_id: str, access_path: str):
    from public_data_agent.registry import Registry

    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_dataset_identity(
        dataset_id=dataset_id,
        title="Fiskehelse",
        publisher_name=None,
        access_path=access_path,
        license=None,
    )
    return registry


def test_a_week_fetch_stores_observations_and_sends_the_bearer(tmp_path: Path) -> None:
    from public_data_agent.fetch import _fetch_bwfish

    registry = _registry(tmp_path, "bwfish:locality-2024-20", WEEK_URL)
    http = _Fetched(WEEK)
    result = _fetch_bwfish(
        registry, registry.get_dataset("bwfish:locality-2024-20"), http=http, token=_token()
    )
    assert http.seen == [{"Authorization": "Bearer abc"}]
    assert result.table_id == "locality-2024-20"
    assert result.counts.listed == 1, "one of the two localities reported a count"
    assert registry.observation_count() == 1
    assert registry.record_count("bwfish:locality-2024-20") == 0, "a count is not an entity"
    capability = registry.get_capability("bwfish:locality-2024-20")
    assert capability["capability"] == "observations"
    assert "not zero" in capability["notes"]
    registry.close()


def test_the_register_fetch_stores_records_not_observations(tmp_path: Path) -> None:
    from public_data_agent.fetch import _fetch_bwfish

    registry = _registry(tmp_path, "bwfish:localities", LOCALITIES_URL)
    body = [{"localityNo": 35297, "name": "Ådnøy Sø", "municipality": "Sandnes",
             "municipalityNo": "1108", "aquaCultureRegistryVersion": 3}]
    result = _fetch_bwfish(
        registry, registry.get_dataset("bwfish:localities"),
        http=_Fetched(body), token=_token(),
    )
    assert result.table_id == "localities"
    assert registry.observation_count() == 0, "a list of places is not a measurement"
    rows = registry.list_records("bwfish:localities", kind="entity")
    assert [row["subject_code"] for row in rows] == ["35297"]
    assert [row["subject_label"] for row in rows] == ["Ådnøy Sø"]
    registry.close()


def test_the_per_locality_detail_path_is_refused_not_guessed(tmp_path: Path) -> None:
    """It shares five segments with the weekly path and holds no lice count.

    Without this, the detail payload reaches the week reader, which raises on
    a shape it was never meant to see -- a confusing error for a routing bug.
    """

    from public_data_agent.fetch import _fetch_bwfish

    detail = "https://www.barentswatch.no/bwapi/v1/geodata/fishhealth/locality/14746/2024/20"
    registry = _registry(tmp_path, "bwfish:detail", detail)
    with pytest.raises(SourceError, match="no reader"):
        _fetch_bwfish(
            registry, registry.get_dataset("bwfish:detail"),
            http=_Fetched({}), token=_token(),
        )
    registry.close()


def test_a_failed_fetch_stores_nothing_and_records_the_run(tmp_path: Path) -> None:
    from public_data_agent.fetch import _fetch_bwfish

    registry = _registry(tmp_path, "bwfish:locality-2024-20", WEEK_URL)
    empty = {"year": 2024, "week": 20, "localities": [FALLOW]}
    with pytest.raises(ValueError, match=MEASURE):
        _fetch_bwfish(
            registry, registry.get_dataset("bwfish:locality-2024-20"),
            http=_Fetched(empty), token=_token(),
        )
    assert registry.observation_count() == 0
    assert registry.get_capability("bwfish:locality-2024-20") is None, (
        "a week nobody reported must not be verified as readable"
    )
    runs = registry.conn.execute(
        "SELECT status FROM fetch_runs WHERE dataset_id = 'bwfish:locality-2024-20'"
    ).fetchall()
    assert [row["status"] for row in runs] == ["failed"]
    registry.close()


# --- ingest ------------------------------------------------------------------


def test_the_series_starts_where_the_api_said_it_starts() -> None:
    """2011 w20 answers 200 with an empty array; 2012 w20 returns 1,936 rows.

    The start is a probed fact, so a listing that began earlier would create
    hundreds of datasets the publisher holds nothing for.
    """

    import datetime

    from public_data_agent.sources.bwfish import FIRST_YEAR, listed_weeks

    assert FIRST_YEAR == 2012
    weeks = listed_weeks(datetime.date(2026, 10, 21))
    assert weeks[0] == (2012, 1)
    assert min(year for year, _week in weeks) == 2012


def test_a_fifty_three_week_year_is_listed_in_full() -> None:
    """Week 53 of 2024 is HTTP 400 and week 53 of 2020 returns 1,696 rows.

    The publisher validates the week against the ISO calendar, so assuming 52
    weeks loses real data and assuming 53 requests weeks that do not exist.
    """

    import datetime

    from public_data_agent.sources.bwfish import iso_weeks_in, listed_weeks

    assert iso_weeks_in(2020) == 53
    assert iso_weeks_in(2024) == 52
    weeks = set(listed_weeks(datetime.date(2026, 10, 21)))
    assert (2020, 53) in weeks
    assert (2024, 53) not in weeks
    assert (2024, 52) in weeks


def test_the_current_week_is_left_out_because_it_is_still_being_reported() -> None:
    """The API answers it, which is why the listing has to decide.

    A fetch of the running week stores a partial count that a re-fetch would
    change, and nothing downstream would know the number had moved.
    """

    import datetime

    from public_data_agent.sources.bwfish import last_complete_week, listed_weeks

    monday = datetime.date(2026, 10, 21)  # ISO week 43
    assert monday.isocalendar()[1] == 43, "premise: this date is in week 43"
    assert last_complete_week(monday) == (2026, 42)
    weeks = set(listed_weeks(monday))
    assert (2026, 42) in weeks
    assert (2026, 43) not in weeks


def test_listing_makes_no_request(tmp_path: Path) -> None:
    """772 weeks must not cost 772 requests before anything is stored.

    Passing an http client that raises on use is the only way to assert this:
    a listing that quietly fetched would otherwise pass every other test here.
    """

    import datetime

    from public_data_agent.sources.bwfish import BwFishSource

    class Explodes:
        def get_json_response(self, url, *, headers=None):
            raise AssertionError(f"listing must not request {url}")

        def get_json(self, url, *, headers=None):
            raise AssertionError(f"listing must not request {url}")

    source = BwFishSource(max_items=5, today=datetime.date(2026, 10, 21), http=Explodes())
    refs = source.list_dataset_refs()
    assert len(refs) == 5
    record = source.fetch_dataset(refs[0])
    assert record.source_native_id == "localities"


def test_the_register_is_listed_before_the_weeks() -> None:
    import datetime

    from public_data_agent.sources.bwfish import BwFishSource

    source = BwFishSource(max_items=3, today=datetime.date(2026, 10, 21))
    refs = source.list_dataset_refs()
    assert [ref.source_native_id for ref in refs] == [
        "localities", "locality-2012-01", "locality-2012-02",
    ]
    assert refs[1].source_native_uri.endswith("/locality/2012/1"), (
        "the url carries the publisher's week number, unpadded"
    )
    assert refs[1].source_native_id == "locality-2012-01", (
        "the table id pads so it sorts"
    )


def test_the_listing_declares_no_licence_it_was_not_given() -> None:
    """BarentsWatch prints none on these endpoints and has no OpenAPI document."""

    import datetime

    from public_data_agent.sources.bwfish import BwFishSource

    source = BwFishSource(max_items=2, today=datetime.date(2026, 10, 21))
    for ref in source.list_dataset_refs():
        payload = source.fetch_dataset(ref).payload
        assert payload["license"] is None
        assert payload["publisher"] == {"name": "BarentsWatch"}
        assert payload["bwfish_requires_credential"] == "BARENTSWATCH_API_CLIENT_ID"


def test_an_unlisted_uri_is_refused() -> None:
    import datetime

    from public_data_agent.models import DatasetRef
    from public_data_agent.sources.bwfish import BwFishSource

    source = BwFishSource(max_items=2, today=datetime.date(2026, 10, 21))
    with pytest.raises(SourceError, match="lists no resource"):
        source.fetch_dataset(
            DatasetRef(source_native_uri="https://www.barentswatch.no/bwapi/v1/x", source_native_id="x")
        )


def test_harvest_writes_the_rows_the_fetcher_will_read(tmp_path: Path) -> None:
    """The ingest id and the fetch table id have to agree, or a fetch re-keys.

    `bwfish_table_id` derives the table from the URL and the source derives
    the native id from the same week; this pins them together rather than
    trusting that two places spell it the same way.
    """

    import datetime

    from public_data_agent.harvest import harvest
    from public_data_agent.registry import Registry
    from public_data_agent.sources.bwfish import BwFishSource

    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, BwFishSource(max_items=4, today=datetime.date(2026, 10, 21)))
    for dataset_id, expected_table in (
        ("bwfish:localities", "localities"),
        ("bwfish:locality-2012-01", "locality-2012-01"),
    ):
        row = registry.get_dataset(dataset_id)
        assert row is not None, f"{dataset_id} was not harvested"
        assert row["license"] is None
        assert bwfish_table_id(row["access_path"]) == expected_table
    registry.close()


def test_bwfish_is_a_registered_source() -> None:
    from public_data_agent.sources import SOURCE_IDS, build_source
    from public_data_agent.sources.bwfish import BwFishSource

    assert "bwfish" in SOURCE_IDS
    source = build_source("bwfish")
    assert isinstance(source, BwFishSource)
    assert source.source_id == "bwfish"
