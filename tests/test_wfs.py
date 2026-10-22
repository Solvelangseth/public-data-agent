"""A GetFeature is not a GetCapabilities, and that is the whole change.

`fetch_observations` refused every URL carrying `wfs`, `ows` or `service=wfs`.
The refusal was earned: fetching a capabilities document once stored seventeen
layer names as observations, with `measure: "title"` and values like "This
document as HTML". But it refused the features along with the menu, and 116
datasets that declare a WFS had therefore never been asked.

So the line moves from "which protocol" to "which request", and these are the
cases that keep it in the right place.
"""

from __future__ import annotations

import pytest

from public_data_agent.sources.wfs import (
    cells_from_wfs,
    getfeature_url,
    hits_url,
    is_wfs_feature_url,
    normalise_layer,
    wfs_table_id,
)

CAPABILITIES_URL = (
    "https://wfs.geonorge.no/skwms1/wfs.hornkoraller"
    "?service=WFS&request=GetCapabilities&version=2.0.0"
)

FEATURES = """<?xml version='1.0' encoding='UTF-8'?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"
    xmlns:gml="http://www.opengis.net/gml/3.2" numberMatched="unknown" numberReturned="0">
  <wfs:member>
    <app:Hornkoraller xmlns:app="http://skjema.geonorge.no/x" gml:id="hornkoraller.1">
      <app:identifikasjon><app:Identifikasjon>
        <app:lokalId>e74f0861-dcb4-44c2</app:lokalId>
      </app:Identifikasjon></app:identifikasjon>
      <app:posisjon><gml:Point srsName="urn:ogc:def:crs:EPSG::4258">
        <gml:pos>70.435100 21.948400</gml:pos></gml:Point></app:posisjon>
      <app:art>Paragorgia arborea</app:art>
      <app:bunnDybde>328.87</app:bunnDybde>
    </app:Hornkoraller>
  </wfs:member>
</wfs:FeatureCollection>
"""

NAMED = FEATURES.replace(
    "<app:art>Paragorgia arborea</app:art>",
    "<app:art>Paragorgia arborea</app:art><app:stedsnavn>Korallrev ved Røst</app:stedsnavn>",
)


def test_a_capabilities_url_is_not_a_feature_url() -> None:
    """The one that must keep failing. A capabilities document is a listing of
    what the service offers, which is metadata, and storing it as data is the
    violation this registry spent a migration undoing."""

    assert not is_wfs_feature_url(CAPABILITIES_URL)


def test_a_getfeature_url_is_one() -> None:
    assert is_wfs_feature_url(getfeature_url(CAPABILITIES_URL, "app:Hornkoraller"))


def test_all_three_conditions_are_needed() -> None:
    base = "https://wfs.geonorge.no/skwms1/wfs.x?"
    assert not is_wfs_feature_url(base + "request=GetFeature&typeNames=a:b"), "no service=WFS"
    assert not is_wfs_feature_url(base + "service=WFS&typeNames=a:b"), "no request"
    assert not is_wfs_feature_url(base + "service=WFS&request=GetFeature"), "no layer"
    # An OGC API Features path is a different protocol with its own reader.
    assert not is_wfs_feature_url("https://geo.ngu.no/api/features/collections/x/items")
    assert not is_wfs_feature_url(None) and not is_wfs_feature_url("")


def test_the_two_layer_spellings_become_one() -> None:
    """The catalogue writes `mareano_biologi/bomtraal_arter`; the capabilities
    document calls the same layer `mareano_biologi:bomtraal_arter`. Sending the
    slash form returns an exception report, which reads as a dead layer."""

    assert normalise_layer("mareano_biologi/bomtraal_arter") == "mareano_biologi:bomtraal_arter"
    assert normalise_layer("app:Hornkoraller") == "app:Hornkoraller"
    assert normalise_layer("plain") == "plain"
    assert normalise_layer(None) is None and normalise_layer("  ") is None


def test_the_declared_request_is_replaced_not_appended() -> None:
    """A query with two `request` parameters is answered differently by
    different servers, and this must not depend on which."""

    url = getfeature_url(CAPABILITIES_URL, "app:Hornkoraller", count=25)
    assert url.count("request=") == 1
    assert "request=GetFeature" in url
    assert "GetCapabilities" not in url
    assert "count=25" in url
    assert "typeNames=app%3AHornkoraller" in url


def test_a_publishers_own_query_parameters_survive() -> None:
    url = getfeature_url(
        "https://ogc.dsb.no/wfs.ashx?datasett=storulykke&service=WFS&request=GetCapabilities",
        "a:b",
    )
    assert "datasett=storulykke" in url


def test_a_missing_layer_is_refused() -> None:
    with pytest.raises(ValueError, match="needs a layer name"):
        getfeature_url(CAPABILITIES_URL, "")


def test_the_count_comes_from_a_separate_request() -> None:
    """`wfs.geonorge.no` answers every GetFeature with
    `numberMatched="unknown" numberReturned="0"` while returning features."""

    url = hits_url(CAPABILITIES_URL, "app:Hornkoraller")
    assert url.endswith("&resultType=hits")
    assert "request=GetFeature" in url


def test_the_table_id_is_the_layer_not_the_host() -> None:
    """11 Fiskeridirektoratet datasets share one `WFSServer` address, so the
    host identifies nothing and the layer identifies the rows."""

    url = getfeature_url(CAPABILITIES_URL, "app:Hornkoraller")
    assert wfs_table_id(url) == "app:Hornkoraller"


def test_a_feature_with_no_printed_name_gets_a_code_and_no_label() -> None:
    """The rule the record migration established.

    Passing the identifier as the value too makes `subject_label` a copy of
    `subject_code` -- a label that says nothing, one step from the invented
    names that migration removed. The species stays in the attributes.
    """

    cells = cells_from_wfs(FEATURES)
    assert len(cells) == 1
    measure, value, dimensions = cells[0]
    assert measure == "lokalId"
    assert value is None, "an identifier is not a name"
    assert dimensions["art"] == "Paragorgia arborea"
    assert dimensions["bunnDybde"] == "328.87"


def test_a_printed_name_is_used_when_there_is_one() -> None:
    measure, value, _dimensions = cells_from_wfs(NAMED)[0]
    assert measure == "stedsnavn"
    assert value == "Korallrev ved Røst"


def test_geometry_arrives_named_never_as_a_bare_pair() -> None:
    """`gml:pos` under EPSG::4258 is latitude first and the same publisher's
    GeoJSON is longitude first. A pair with no names is a coin toss about
    which hemisphere the feature is in."""

    _measure, _value, dimensions = cells_from_wfs(FEATURES)[0]
    assert dimensions["geometry.latitude"] == "70.4351"
    assert dimensions["geometry.longitude"] == "21.9484"
    assert dimensions["geometry.epsg"] == "4258"
    assert dimensions["geometry.type"] == "Point"


def test_an_empty_result_raises_rather_than_reading_as_zero_features() -> None:
    empty = ('<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" '
             'numberMatched="0" numberReturned="0"></wfs:FeatureCollection>')
    with pytest.raises(ValueError, match="no members"):
        cells_from_wfs(empty)


def test_an_exception_report_is_not_an_empty_layer() -> None:
    report = ('<?xml version="1.0"?><ows:ExceptionReport '
              'xmlns:ows="http://www.opengis.net/ows/1.1"><ows:Exception>'
              '<ows:ExceptionText>Unknown typeNames</ows:ExceptionText>'
              '</ows:Exception></ows:ExceptionReport>')
    with pytest.raises(ValueError, match="exception report"):
        cells_from_wfs(report)


def test_the_fetch_dispatch_still_refuses_a_capabilities_url() -> None:
    """The guard and the new door have to coexist: one request routed, the
    other still refused, by the same function."""

    from public_data_agent.fetch import _MAP_SERVICE_MARKS

    assert any(mark in CAPABILITIES_URL.casefold() for mark in _MAP_SERVICE_MARKS)
    assert not is_wfs_feature_url(CAPABILITIES_URL)
    # And the feature URL hits the same marks, which is why the dispatch must
    # sit above the guard rather than after it.
    feature_url = getfeature_url(CAPABILITIES_URL, "app:Hornkoraller").casefold()
    assert any(mark in feature_url for mark in _MAP_SERVICE_MARKS)
    assert is_wfs_feature_url(feature_url)
