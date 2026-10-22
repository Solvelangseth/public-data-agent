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


def test_the_hits_url_drops_the_page_size() -> None:
    """A hits request carrying `count=500` returns 500 on some servers, which
    makes the denominator equal to the sample and the coverage always 100%."""

    from public_data_agent.sources.wfs import hits_url_for

    feature = getfeature_url(CAPABILITIES_URL, "app:Hornkoraller", count=500, start=1000)
    hits = hits_url_for(feature)
    assert "count=" not in hits and "startIndex" not in hits
    assert hits.count("resultType=hits") == 1
    assert "typeNames=app%3AHornkoraller" in hits, "the encoded colon is the reliable one"


def test_asking_for_hits_twice_does_not_stack_the_parameter() -> None:
    from public_data_agent.sources.wfs import hits_url_for

    once = hits_url_for(getfeature_url(CAPABILITIES_URL, "a:b"))
    assert hits_url_for(once).count("resultType") == 1


def test_an_unknown_total_is_none_and_never_zero() -> None:
    """A layer whose size the service declines to state and a layer that is
    empty are different facts, and only one means there is nothing to fetch."""

    from public_data_agent.sources.wfs import total_from_hits

    unknown = ('<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" '
               'numberMatched="unknown" numberReturned="0"/>')
    assert total_from_hits(unknown) is None
    empty = ('<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" '
             'numberMatched="0" numberReturned="0"/>')
    assert total_from_hits(empty) == 0
    counted = ('<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" '
               'numberMatched="1993" numberReturned="0"/>')
    assert total_from_hits(counted) == 1993


def test_a_property_filter_uses_the_ogc_form_not_cql() -> None:
    """Measured on wfs.hornkoraller, whose unfiltered total is 1,993:

        CQL_FILTER=art='Radicipes'   HTTP 200, numberMatched 1993
        FILTER=<PropertyIsEqualTo…>  HTTP 200, numberMatched  119

    The CQL form is accepted and ignored. A reader using it would store all
    1,993 corals under each of five species datasets, with a 200 every time.
    """

    from public_data_agent.sources.wfs import property_filter_url

    url = property_filter_url(CAPABILITIES_URL, "app:Hornkoraller", "art", "Radicipes")
    assert "CQL_FILTER" not in url
    assert "FILTER=" in url
    assert "PropertyIsEqualTo" in url.replace("%3C", "<").replace("%3E", ">")
    assert "ValueReference" in url.replace("%3C", "<").replace("%3E", ">")


def test_a_filter_value_with_xml_characters_is_escaped() -> None:
    """A species name is tame; a place name with `&` is not, and an
    unescaped one produces a filter the server parses as something else."""

    from public_data_agent.sources.wfs import property_filter_url

    from urllib.parse import unquote

    url = property_filter_url(CAPABILITIES_URL, "a:b", "navn", "Fisk & Co <test>")
    decoded = unquote(url)
    assert "&amp;" in decoded and "&lt;test&gt;" in decoded
    # And the filter's own tags survive as tags, not as escaped text.
    assert "<PropertyIsEqualTo>" in decoded


def test_a_filter_that_returns_everything_is_not_credible() -> None:
    """The signature of a server that accepted the parameter and ignored it."""

    from public_data_agent.sources.wfs import filtered_count_is_credible

    assert filtered_count_is_credible(119, 1993)
    assert not filtered_count_is_credible(1993, 1993)
    # Unknown on either side is not evidence of anything.
    assert filtered_count_is_credible(None, 1993)
    assert filtered_count_is_credible(119, None)
