"""Two defects in the discovery tool, found by using its own output.

Both were my errors and both had the same shape: the tool recorded something
true and presented it in a way that misled the next reader.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("discover", Path("scripts/discover.py"))
discover = importlib.util.module_from_spec(spec)
spec.loader.exec_module(discover)

THREDDS = (
    "https://thredds.met.no/thredds/dodsC/KSS/Klima_i_Norge/utgave2025/"
    "ClimateStatistics/change-evap/ensemble-mean_change-evap.nc.html"
)


def test_an_opendap_form_leads_to_the_dataset_that_generated_it() -> None:
    """151 THREDDS rows resolve to `<dataset>.nc.html` and read as `unclear`.

    The `.html` is a form the server generates from the dataset it names, so
    stripping it addresses the thing one character away -- which the first
    version of the classifier reported as "not JSON" and left there.
    """

    doors = discover.opendap_doors(THREDDS)
    assert [how for _url, how in doors] == ["convention:opendap-dds", "convention:opendap-das"]
    assert doors[0][0].endswith("ensemble-mean_change-evap.nc.dds")
    assert doors[1][0].endswith("ensemble-mean_change-evap.nc.das")


def test_only_an_opendap_path_gets_those_doors() -> None:
    """An ordinary .html page is a page. `/dodsC/` is what makes it a form."""

    assert discover.opendap_doors("https://example.no/report.html") == []
    assert discover.opendap_doors("https://thredds.met.no/thredds/catalog/x/catalog.html") == []
    assert discover.opendap_doors(THREDDS[: -len(".html")]) == [], (
        "the dataset itself is not its own form"
    )


def test_they_are_marked_convention_not_declared() -> None:
    """No link in any response says to do this, so it must not claim one did."""

    for _url, how in discover.opendap_doors(THREDDS):
        assert how.startswith("convention:")
        assert not how.startswith("declared:")


def test_an_opendap_document_is_rows_not_a_parse_failure() -> None:
    dds = "Dataset {\n    Int32 time[time = 2];\n    Float32 change-evap_annual[time = 2];\n}"
    das = 'Attributes {\n    change-evap_annual {\n        String units "%";\n    }\n}'
    assert discover.classify(200, None, "https://x/y.nc.dds", dds)[0] == "rows"
    assert discover.classify(200, None, "https://x/y.nc.das", das)[0] == "rows"
    assert "variables" in discover.classify(200, None, "https://x/y.nc.dds", dds)[1]


def test_an_actual_html_page_is_still_unclear() -> None:
    """The fix must not turn every non-JSON body into a finding."""

    verdict, evidence = discover.classify(
        200, None, "https://example.no/page", "<!DOCTYPE html><html><body>hello"
    )
    assert verdict == "unclear"
    assert "not JSON" in evidence


def test_a_truncated_json_body_is_still_rows() -> None:
    """The earlier fix for an over-cap FeatureCollection must survive this one."""

    body = '{"type":"FeatureCollection","numberReturned":100,"numberMatched":88861,"features":[{'
    verdict, evidence = discover.classify(200, None, "https://x/items", body)
    assert verdict == "rows"
    assert "numberMatched=88861" in evidence


def test_an_unreachable_form_does_not_hide_its_dataset() -> None:
    """Generating the HTML form for a 1.85M-cell grid can time out.

    The form timing out says nothing about `.dds`, which answers in a moment,
    and the early return for `unreachable` swallowed the doors entirely. Seen
    live: the form timed out at 45s on a server that had answered 151 `.dds`
    requests minutes earlier.
    """

    seen: list[tuple[str, str]] = []

    class Timeouts:
        """Every request fails, which is the case the early return mishandled."""

        count = 0
        pause = 0.0

        def get(self, url: str):
            seen.append((url, ""))
            return 0, None, "TimeoutError"

    entries = list(
        discover.investigate(
            Timeouts(), THREDDS, dataset_id=None, source_id=None, depth=0, probe=False
        )
    )
    verdicts = [e["verdict"] for e in entries]
    hows = [e["how"] for e in entries]
    assert verdicts[0] == "unreachable", "the form's own failure is still reported"
    assert "convention:opendap-dds" in hows, (
        "the .dds must still be tried after the form failed"
    )
    assert any(url.endswith(".nc.dds") for url, _ in seen)


def test_an_unreachable_url_with_no_doors_still_stops() -> None:
    """The early return has to keep working for everything that is not OPeNDAP."""

    class Timeouts:
        count = 0
        pause = 0.0

        def get(self, url: str):
            return 0, None, "TimeoutError"

    entries = list(
        discover.investigate(
            Timeouts(), "https://example.no/thing", dataset_id=None, source_id=None,
            depth=0, probe=False,
        )
    )
    assert len(entries) == 1
    assert entries[0]["verdict"] == "unreachable"
