"""A year filter that reached the registry and stopped there.

`fetch_observations` takes `from_year` and `to_year`. `_fetch_norgesbank`
took a `select` and no years, and the dispatch passed none, so a question
about 2024 fetched every year on record -- 854 observations instead of 34 --
while `ask()` reported the request as narrowed.

Found by auditing the 37 connectors that DO receive a select, after the 164
that do not had already been dealt with. Receiving a select is not the same
as honouring a filter, and Norges Bank is the case that proves the
difference: it validates select dimensions and raises on unknown ones, and
silently dropped the years.
"""

from __future__ import annotations

from public_data_agent.fetch import _norgesbank_request_url

FLOW = "https://data.norges-bank.no/api/data/GOVT_KEYFIGURES?format=sdmx-json"


def test_no_years_asked_is_the_request_unchanged() -> None:
    """The old behaviour has to survive exactly, since every stored Norges
    Bank observation was fetched with it."""

    assert _norgesbank_request_url(FLOW, 100) == FLOW + "&lastNObservations=100"


def test_a_year_becomes_the_sdmx_period_parameters() -> None:
    url = _norgesbank_request_url(FLOW, 100, from_year=2024, to_year=2024)
    assert "startPeriod=2024" in url and "endPeriod=2024" in url
    # Measured live: 74,612 bytes unfiltered, 6,249 for 2024 alone, and
    # 854 observations down to 34.
    assert "lastNObservations=100" in url


def test_a_range_keeps_both_ends() -> None:
    url = _norgesbank_request_url(FLOW, 10, from_year=2015, to_year=2024)
    assert "startPeriod=2015" in url and "endPeriod=2024" in url


def test_one_open_end_sends_only_that_end() -> None:
    """"From 2015" is a real question and must not become "2015 only"."""

    url = _norgesbank_request_url(FLOW, 10, from_year=2015)
    assert "startPeriod=2015" in url and "endPeriod" not in url
    url = _norgesbank_request_url(FLOW, 10, to_year=2024)
    assert "endPeriod=2024" in url and "startPeriod" not in url


def test_the_separator_is_right_when_the_url_has_no_query() -> None:
    bare = "https://data.norges-bank.no/api/data/GOVT_KEYFIGURES"
    url = _norgesbank_request_url(bare, 5, from_year=2024)
    assert url.startswith(bare + "?")
    assert url.count("?") == 1


def test_the_connector_and_the_dispatch_both_carry_the_years() -> None:
    """The defect was two halves: a connector without the parameter and a
    dispatch that would not have passed it. Either one alone re-breaks it."""

    import inspect

    from public_data_agent import fetch as fetch_module

    signature = inspect.signature(fetch_module._fetch_norgesbank)
    assert "from_year" in signature.parameters and "to_year" in signature.parameters
    source = inspect.getsource(fetch_module)
    call = source[source.index("return _fetch_norgesbank("):][:220]
    assert "from_year=from_year" in call and "to_year=to_year" in call
