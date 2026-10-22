"""What the catalogue says about a WFS, kept apart from whether it answers.

165 of 7,437 Geonorge dataset records declare a WFS in
`ServiceWfsDistributionUrlForDataset`, 116 of them are in this registry, and
**all 116 have never been asked by any fetch**. That is the breadth this
sweep is for, and the rule it has to hold to is that a declaration is a
declaration: the url is recorded as the publisher wrote it, and nothing here
claims the endpoint works.
"""

from __future__ import annotations

import importlib.util
import urllib.parse
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "resolve_geonorge_wfs", Path("scripts/resolve_geonorge_wfs.py")
)
sweep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sweep)


def test_a_record_with_no_wfs_field_declares_nothing() -> None:
    assert sweep.declared_wfs({"Uuid": "a", "Title": "t"}) is None


def test_a_non_http_value_is_not_a_declaration() -> None:
    """The field is free text in the catalogue and has held placeholders."""

    for value in ("", "n/a", "ikke tilgjengelig", "wfs", None, 7):
        assert sweep.declared_wfs({"ServiceWfsDistributionUrlForDataset": value}) is None


def test_the_url_is_recorded_as_the_publisher_wrote_it() -> None:
    """Including its `GetCapabilities`, which is not what a reader would ask.

    Rewriting it into a `GetFeature` needs a layer name, and 97 of the 165
    declarations point at a `wfs.geonorge.no` service whose layer is named
    only inside its capabilities document. Guessing one here would put a url
    in the registry that nobody has seen answer.
    """

    url = ("https://wfs.geonorge.no/skwms1/wfs.hornkoraller"
           "?service=WFS&request=GetCapabilities&version=2.0.0")
    entry = sweep.declared_wfs({
        "Uuid": "94bc96ae", "Title": "Hornkoraller", "Organization": "Kartverket",
        "ServiceWfsDistributionUrlForDataset": url,
        "AccessIsOpendata": True,
    })
    assert entry is not None
    assert entry["wfs_url"] == url
    assert entry["wfs_host"] == "wfs.geonorge.no"
    assert entry["declared_request"] == "GetCapabilities"
    assert entry["declared_typename"] is None
    assert entry["open_data"] is True


def test_a_declared_typename_is_kept_under_either_spelling() -> None:
    """WFS 1.1 spells it `typeName`, 2.0 spells it `typeNames`, and the
    catalogue carries both. Case varies too."""

    for key in ("typeName", "TYPENAMES", "typenames"):
        entry = sweep.declared_wfs({
            "ServiceWfsDistributionUrlForDataset":
                f"https://example.no/wfs?service=WFS&{key}=app:Hornkoraller",
        })
        assert entry is not None
        assert entry["declared_typename"] == "app:Hornkoraller", key


def test_the_facet_survives_url_encoding() -> None:
    """The bracketed facet parameter must reach the catalogue unencoded.

    Encoded, the facet is ignored and the search returns services and
    applications alongside datasets -- 7,437 becomes a larger number of a
    different thing, which is the kind of total that gets quoted later.
    """

    url = sweep.page_url(offset=501, limit=500)
    assert "facets%5B0%5Dname=type" in url
    assert "facets%5B0%5Dvalue=dataset" in url
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert query["offset"] == ["501"]
    assert query["limit"] == ["500"]
