"""Reading GML without transposing Norway into the Indian Ocean.

116 datasets in this registry declare a WFS and have never been asked, and
128 of the 130 answering addresses serve GML and nothing else, so this parser
is the gate on all of it. The cases here are the ones that are silent when
wrong.
"""

from __future__ import annotations

import pytest

from public_data_agent.gml import (
    UnknownAxisOrder,
    axis_order,
    epsg_code,
    features_from_gml,
    layers_from_capabilities,
    number_matched,
    position,
)

# Shortened from a live `wfs.geonorge.no/skwms1/wfs.hornkoraller` response.
# The namespace prefix is `app`, bound by an attribute on the <Name> element
# itself -- which is what broke the regex this parser replaced.
CAPABILITIES = """<?xml version='1.0' encoding='UTF-8'?>
<WFS_Capabilities xmlns="http://www.opengis.net/wfs/2.0"
    xmlns:ows="http://www.opengis.net/ows/1.1" version="2.0.0">
  <ows:ServiceIdentification>
    <ows:Title>Hornkoraller</ows:Title>
    <ows:ServiceType>WFS</ows:ServiceType>
  </ows:ServiceIdentification>
  <FeatureTypeList>
    <FeatureType>
      <Name xmlns:app="http://skjema.geonorge.no/SOSI/produktspesifikasjon/Hornkoraller/20201201">app:Hornkoraller</Name>
      <Title>Hornkoraller</Title>
      <DefaultCRS>urn:ogc:def:crs:EPSG::4258</DefaultCRS>
      <OtherCRS>urn:ogc:def:crs:EPSG::25833</OtherCRS>
      <OutputFormats>
        <Format>text/xml; subtype=gml/3.2.1</Format>
        <Format>application/gml+xml; version=3.2</Format>
      </OutputFormats>
    </FeatureType>
  </FeatureTypeList>
</WFS_Capabilities>
"""

# One feature, verbatim in shape from the same service. `breddegrad` and
# `lengdegrad` are the publisher's own named latitude and longitude, and they
# are what makes the axis-order assertion below independent of my reading.
FEATURE = """<?xml version='1.0' encoding='UTF-8'?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"
    xmlns:gml="http://www.opengis.net/gml/3.2"
    numberMatched="unknown" numberReturned="0">
  <wfs:member>
    <app:Hornkoraller xmlns:app="http://skjema.geonorge.no/SOSI/produktspesifikasjon/Hornkoraller/20201201"
        gml:id="hornkoraller.177378">
      <app:identifikasjon>
        <app:Identifikasjon>
          <app:lokalId>e74f0861-dcb4-44c2-8718-e55891625371</app:lokalId>
        </app:Identifikasjon>
      </app:identifikasjon>
      <app:posisjon>
        <gml:Point gml:id="hornkoraller.177378_APP_POSISJON" srsName="urn:ogc:def:crs:EPSG::4258">
          <gml:pos>70.435100 21.948400</gml:pos>
        </gml:Point>
      </app:posisjon>
      <app:art>Paragorgia arborea</app:art>
      <app:bunnDybde>328.87</app:bunnDybde>
      <app:breddegrad>70.435126</app:breddegrad>
      <app:lengdegrad>21.948403</app:lengdegrad>
    </app:Hornkoraller>
  </wfs:member>
</wfs:FeatureCollection>
"""

EXCEPTION = """<?xml version='1.0' encoding='UTF-8'?>
<ows:ExceptionReport xmlns:ows="http://www.opengis.net/ows/1.1" version="2.0.0">
  <ows:Exception exceptionCode="InvalidParameterValue">
    <ows:ExceptionText>Output format application/json is not supported</ows:ExceptionText>
  </ows:Exception>
</ows:ExceptionReport>
"""


def test_a_name_with_an_attribute_is_still_found() -> None:
    """The regression this parser was written for.

    `<(?:\\w+:)?Name>` reported zero layers for every wfs.geonorge.no service
    -- 24 false negatives out of 40 -- because the <Name> here carries an
    xmlns:app attribute and that pattern demands `>` straight after the tag.
    """

    layers = layers_from_capabilities(CAPABILITIES)
    assert [layer["name"] for layer in layers] == ["app:Hornkoraller"]
    assert layers[0]["crs"] == "urn:ogc:def:crs:EPSG::4258"
    assert layers[0]["formats"] == [
        "text/xml; subtype=gml/3.2.1",
        "application/gml+xml; version=3.2",
    ]
    assert layers[0]["other_crs"] == ["urn:ogc:def:crs:EPSG::25833"]


def test_the_prefix_is_kept_because_typeNames_needs_it() -> None:
    """`typeNames=Hornkoraller` without the prefix is not the same request."""

    assert layers_from_capabilities(CAPABILITIES)[0]["name"].startswith("app:")


def test_an_exception_report_is_not_an_empty_service() -> None:
    """Both documents refuse it, and the message is carried through.

    Reading an exception as "no layers" or "no features" records a service
    outage, or a rejected output format, as a fact about the dataset.
    """

    for reader in (layers_from_capabilities, features_from_gml):
        with pytest.raises(ValueError, match="exception report"):
            reader(EXCEPTION)
    with pytest.raises(ValueError, match="application/json"):
        features_from_gml(EXCEPTION)


def test_a_capabilities_document_with_no_layers_raises() -> None:
    empty = CAPABILITIES.replace(
        CAPABILITIES[CAPABILITIES.index("<FeatureTypeList>"):
                     CAPABILITIES.index("</FeatureTypeList>") + len("</FeatureTypeList>")],
        "<FeatureTypeList></FeatureTypeList>",
    )
    with pytest.raises(ValueError, match="no FeatureType declared"):
        layers_from_capabilities(empty)


def test_latitude_comes_first_in_epsg_4258() -> None:
    """Checked against the publisher's own named fields, not against my reading.

    The feature carries `breddegrad` 70.435126 and `lengdegrad` 21.948403 as
    properties, and its `gml:pos` is `70.435100 21.948400`. So the first
    ordinate is the latitude, and Paragorgia arborea is off Finnmark rather
    than in the Indian Ocean.
    """

    feature = features_from_gml(FEATURE)[0]
    assert feature["geometry"] == {"latitude": 70.4351, "longitude": 21.9484, "epsg": 4258}
    assert abs(feature["geometry"]["latitude"] - float(feature["properties"]["breddegrad"])) < 0.001
    assert abs(feature["geometry"]["longitude"] - float(feature["properties"]["lengdegrad"])) < 0.001


def test_a_projected_crs_is_not_called_longitude() -> None:
    """25833 is easting-first and nothing is reprojected.

    Naming a UTM easting `longitude` would be a worse error than leaving it
    named correctly, because every later stage would treat 570000 as degrees.
    """

    pair = position("570000.00 7812000.00", "urn:ogc:def:crs:EPSG::25833")
    assert pair == {"easting": 570000.0, "northing": 7812000.0, "epsg": 25833}
    assert "longitude" not in pair and "latitude" not in pair


def test_an_unknown_crs_raises_rather_than_defaulting() -> None:
    """The whole point of the table.

    A default of 4326 would read a projected coordinate as degrees, and a
    default of "first is x" would transpose every geographic one. Both are
    silent. 29 of the 797 layers declare no CRS at all, and those have to be
    refused too.
    """

    with pytest.raises(UnknownAxisOrder, match="not in this module's axis-order table"):
        axis_order("urn:ogc:def:crs:EPSG::3857")
    for absent in (None, "", "EPSG:", "not a crs"):
        with pytest.raises(UnknownAxisOrder, match="no EPSG code"):
            axis_order(absent)


def test_the_epsg_code_is_read_from_every_spelling_in_use() -> None:
    assert epsg_code("urn:ogc:def:crs:EPSG::4258") == 4258
    assert epsg_code("http://www.opengis.net/def/crs/EPSG/0/25833") == 25833
    assert epsg_code("EPSG:4326") == 4326
    assert epsg_code(None) is None
    assert epsg_code("CRS:84") is None


def test_an_ordinate_never_becomes_a_property() -> None:
    """`gml:pos` read as a property is "70.435100 21.948400" stored as a label.

    The registry has already had to undo 11,374 cells of that kind, and this
    one would arrive right beside a geometry that holds the same numbers
    properly.
    """

    properties = features_from_gml(FEATURE)[0]["properties"]
    assert "pos" not in properties
    assert not any(" " in value and value.replace(" ", "").replace(".", "").isdigit()
                   for value in properties.values())
    assert properties["art"] == "Paragorgia arborea"
    assert properties["bunnDybde"] == "328.87"


def test_a_nested_property_is_flattened_to_its_leaf() -> None:
    """`app:identifikasjon/app:Identifikasjon/app:lokalId` -> `lokalId`."""

    assert features_from_gml(FEATURE)[0]["properties"]["lokalId"] == (
        "e74f0861-dcb4-44c2-8718-e55891625371"
    )


def test_a_colliding_leaf_name_is_reported_not_overwritten() -> None:
    """Shallow flattening loses the second of two same-named leaves.

    It has to be visible, because the alternative is a feature that silently
    carries one of two values with nothing saying which.
    """

    doubled = FEATURE.replace(
        "<app:art>Paragorgia arborea</app:art>",
        "<app:art>Paragorgia arborea</app:art><app:nest><app:art>Radicipes</app:art></app:nest>",
    )
    feature = features_from_gml(doubled)[0]
    assert feature["properties"]["art"] == "Paragorgia arborea"
    assert "art" in feature["properties_dropped"]


def test_geonorge_says_unknown_and_zero_while_returning_a_feature() -> None:
    """So neither count attribute is usable on a GetFeature there.

    The payload itself carries `numberMatched="unknown" numberReturned="0"`
    and one feature. `resultType=hits` is the only honest total, and it is a
    separate request.
    """

    assert number_matched(FEATURE) is None
    assert len(features_from_gml(FEATURE)) == 1
    hits = ('<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" '
            'numberMatched="1993" numberReturned="0"/>')
    assert number_matched(hits) == 1993


def test_a_collection_with_no_members_raises() -> None:
    """An empty answer and a misread document are different answers."""

    empty = ('<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" '
             'numberMatched="0" numberReturned="0"></wfs:FeatureCollection>')
    with pytest.raises(ValueError, match="no members"):
        features_from_gml(empty)


def test_a_polygon_is_named_and_not_decoded() -> None:
    """Half-reading an outline would put one vertex where a boundary belongs."""

    polygon = FEATURE.replace(
        '<gml:Point gml:id="hornkoraller.177378_APP_POSISJON" srsName="urn:ogc:def:crs:EPSG::4258">'
        "\n          <gml:pos>70.435100 21.948400</gml:pos>\n        </gml:Point>",
        '<gml:Polygon srsName="urn:ogc:def:crs:EPSG::4258"><gml:exterior>'
        "<gml:LinearRing><gml:posList>70.4 21.9 70.5 21.9 70.5 22.0 70.4 21.9"
        "</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon>",
    )
    feature = features_from_gml(polygon)[0]
    assert feature["geometry_type"] == "Polygon"
    assert "geometry" not in feature
    assert "posList" not in feature["properties"]
