"""Read GML 3.2 features and WFS capabilities, without guessing axis order.

165 Geonorge datasets declare a WFS and 116 of those are in this registry with
no capability row at all -- nothing has ever asked them. 130 of the 134
addresses answer, with 797 layers between them, and the format is not a
choice: 128 of the 130 advertise GML and nothing else. That was tested rather
than trusted, because an advertised list can understate -- `kart.hi.no` serves
`outputFormat=application/json` while advertising none, since GeoServer always
carries it. `wfs.geonorge.no` and `kart.ssb.no` both answer HTTP 400 to it,
and 97 of the 165 declarations are on `wfs.geonorge.no`.

So this parses GML. Two documents:

    layers_from_capabilities   what a service offers, from GetCapabilities
    features_from_gml          the rows, from GetFeature

Both read with ElementTree and both ignore namespace prefixes, because the
prefix is the publisher's choice and the element name is not: a feature is
`app:Hornkoraller` on one service and `ms:ar50` on another. The first attempt
at the capabilities document used a regex and reported **zero layers for every
wfs.geonorge.no service** -- 24 false negatives out of 40 -- because their
`<Name>` carries an `xmlns:app` attribute and `<(?:\\w+:)?Name>` demands `>`
straight after the tag. A pattern that fails silently for one publisher looks
like a finding about that publisher.

Like `opendap.py`, these are shallow and will not guess. A document that
parses but declares nothing recognisable raises, because "this service offers
no layers" and "this parser did not understand the document" are different
answers and only one of them is ever true.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

# Which coordinate comes first in a `gml:pos`. This is the trap in the whole
# module and it is silent when wrong: `EPSG::4258` writes
# `70.435100 21.948400` -- latitude first, a point off Finnmark -- while the
# same publisher's GeoJSON writes `[16.1687, 69.1226]`, longitude first.
# Reading one as the other puts every Norwegian feature in the Indian Ocean
# and nothing in the payload complains.
#
# A `urn:ogc:def:crs:EPSG::<code>` means the authority's own axis order, which
# for a geographic CRS is latitude, longitude. These five are every CRS the
# 797 layers declare; anything else raises rather than defaulting, because a
# default here is a wrong answer that looks like a right one.
LATITUDE_FIRST = frozenset({4258, 4326, 4230})
EASTING_FIRST = frozenset({25833, 32633})

# Geometry containers, and the ordinate elements inside them. The second
# set is not decoration: without it `gml:pos` arrives in `properties` as
# the string "70.435100 21.948400", which is a coordinate pair stored as a
# label right beside the geometry that already holds it properly.
GEOMETRY_ELEMENTS = frozenset({
    "Point", "LineString", "Polygon", "MultiSurface", "MultiPoint",
    "MultiCurve", "MultiGeometry", "Surface", "Curve", "LinearRing",
})
ORDINATE_ELEMENTS = frozenset({
    "pos", "posList", "coordinates", "lowerCorner", "upperCorner",
})


class UnknownAxisOrder(ValueError):
    """A CRS whose axis order this module has not been told.

    Deliberately not a default. Adding a code here means looking it up in the
    EPSG register, not inferring it from a number that looks like its
    neighbours -- 25833 is easting-first and 4258 is latitude-first, and
    nothing about the digits says so.
    """


def _local(tag: str) -> str:
    """An element's name without its namespace.

    `{http://www.opengis.net/wfs/2.0}FeatureType` -> `FeatureType`.
    """

    return tag.rsplit("}", 1)[-1]


def epsg_code(srs_name: str | None) -> int | None:
    """The EPSG code in an `srsName`, in any of the spellings in use.

        urn:ogc:def:crs:EPSG::4258
        http://www.opengis.net/def/crs/EPSG/0/25833
        EPSG:4326

    None when there is no srsName at all, which 29 of the 797 layers do --
    those are MapServer and ArcGIS services that declare no DefaultCRS. None
    is "not stated", and the caller has to decide what to do about it; it is
    not 4326.

    The authority has to say EPSG. An earlier version took any trailing
    integer and read `CRS:84` as EPSG:84 -- and `CRS:84` is the OGC
    longitude-first WGS84, the exact opposite of EPSG:4326's latitude-first,
    so that one would have transposed every coordinate it touched while
    returning a number that looked right.
    """

    if not srs_name or not isinstance(srs_name, str):
        return None
    if "epsg" not in srs_name.lower():
        return None
    tail = srs_name.strip().rstrip("/").rsplit(":", 1)[-1].rsplit("/", 1)[-1]
    try:
        return int(tail)
    except ValueError:
        return None


def axis_order(srs_name: str | None) -> str:
    """`"latitude-first"` or `"easting-first"`, or a raise.

    Raises on an absent srsName as well as an unknown code: a geometry whose
    CRS nobody stated cannot be turned into a longitude and a latitude, and
    returning one anyway is the failure this module exists to prevent.
    """

    code = epsg_code(srs_name)
    if code is None:
        raise UnknownAxisOrder(
            f"no EPSG code in srsName {srs_name!r}; a coordinate pair cannot be "
            "ordered without one, and assuming WGS84 would silently transpose "
            "every point that is not in it"
        )
    if code in LATITUDE_FIRST:
        return "latitude-first"
    if code in EASTING_FIRST:
        return "easting-first"
    raise UnknownAxisOrder(
        f"EPSG:{code} is not in this module's axis-order table; look it up in "
        "the EPSG register and add it, rather than defaulting -- 25833 is "
        "easting-first and 4258 is latitude-first and the numbers do not say so"
    )


def position(text: str, srs_name: str | None) -> dict[str, Any]:
    """One `gml:pos` as a named pair, ordered by its own CRS.

    Returns the two numbers under the names the CRS gives them, so a caller
    cannot mistake one for the other. A geographic CRS yields `latitude` and
    `longitude`; a projected one yields `easting` and `northing`, which are
    **not** converted -- this module does no reprojection, and calling a UTM
    easting a longitude would be a worse lie than leaving it named correctly.
    """

    parts = (text or "").split()
    if len(parts) < 2:
        raise ValueError(f"a gml:pos needs two ordinates, got {text!r}")
    try:
        first, second = float(parts[0]), float(parts[1])
    except ValueError as error:
        raise ValueError(f"non-numeric ordinate in gml:pos {text!r}") from error
    order = axis_order(srs_name)
    if order == "latitude-first":
        return {"latitude": first, "longitude": second, "epsg": epsg_code(srs_name)}
    return {"easting": first, "northing": second, "epsg": epsg_code(srs_name)}


def layers_from_capabilities(xml: str | bytes) -> list[dict[str, Any]]:
    """Every layer a WFS GetCapabilities declares.

    `name` is what goes in `typeNames`, kept exactly as published including
    its prefix -- `app:Hornkoraller`. The prefix is bound to a namespace by an
    attribute on that very element, which is why this is parsed and not
    matched.

    An `ows:ExceptionReport` raises: it is the service answering, and reading
    it as "no layers" would record a service outage as a service with nothing
    in it.
    """

    root = ET.fromstring(xml)
    if _local(root.tag) == "ExceptionReport":
        texts = [(e.text or "").strip() for e in root.iter() if _local(e.tag) == "ExceptionText"]
        raise ValueError("WFS returned an exception report: " + "; ".join(texts or ["no text"]))
    found: list[dict[str, Any]] = []
    for element in root.iter():
        if _local(element.tag) != "FeatureType":
            continue
        layer: dict[str, Any] = {"formats": [], "other_crs": []}
        for child in element:
            name = _local(child.tag)
            text = (child.text or "").strip()
            if name == "Name":
                layer["name"] = text
            elif name == "Title":
                layer["title"] = text
            elif name == "DefaultCRS":
                layer["crs"] = text
            elif name == "OtherCRS":
                layer["other_crs"].append(text)
            elif name == "OutputFormats":
                layer["formats"] = [(f.text or "").strip() for f in child if (f.text or "").strip()]
        if layer.get("name"):
            found.append(layer)
    if not found:
        raise ValueError(
            "no FeatureType declared in what parsed as a WFS capabilities "
            "document; a service with no layers and a document this parser "
            "misread are different answers"
        )
    return found


def features_from_gml(xml: str | bytes) -> list[dict[str, Any]]:
    """The features in a GML 3.2 FeatureCollection.

    One dict per feature: its `gml:id`, its scalar properties flattened by
    element name, and its geometry if it carries a `gml:Point`.

    Flattening is shallow on purpose. A Geonorge feature nests
    `app:identifikasjon/app:Identifikasjon/app:lokalId`, and the leaf names
    are what a reader wants -- but a repeated leaf under different parents
    would collide, so the first wins and the loss is visible in
    `properties_dropped` rather than silent.

    Geometry other than a point is reported by type and not decoded. A
    polygon's coordinate list is not a value this registry stores, and
    half-reading one would put a single vertex where an outline belongs.
    """

    root = ET.fromstring(xml)
    if _local(root.tag) == "ExceptionReport":
        texts = [(e.text or "").strip() for e in root.iter() if _local(e.tag) == "ExceptionText"]
        raise ValueError("WFS returned an exception report: " + "; ".join(texts or ["no text"]))
    members = [
        child
        for element in root.iter()
        if _local(element.tag) in ("member", "featureMember", "featureMembers")
        for child in element
    ]
    if not members and _local(root.tag) != "FeatureCollection":
        raise ValueError(
            "not a GML FeatureCollection, and no wfs:member found; refusing to "
            "guess which elements are features"
        )
    features: list[dict[str, Any]] = []
    for member in members:
        feature: dict[str, Any] = {
            "type": _local(member.tag),
            "id": next(
                (v for k, v in member.attrib.items() if _local(k) == "id"),
                None,
            ),
            "properties": {},
            "properties_dropped": [],
        }
        for element in member.iter():
            name = _local(element.tag)
            if name in GEOMETRY_ELEMENTS:
                feature.setdefault("geometry_type", name)
                if name == "Point" and "geometry" not in feature:
                    pos = next((e for e in element.iter() if _local(e.tag) == "pos"), None)
                    if pos is not None:
                        feature["geometry"] = position(
                            pos.text or "", element.get("srsName") or pos.get("srsName")
                        )
                continue
            if name in ORDINATE_ELEMENTS:
                # `70.435100 21.948400` read as a property is a coordinate
                # pair stored as a label, which is the trust violation this
                # registry already had to undo 11,374 times. It belongs to the
                # geometry or nowhere.
                continue
            text = (element.text or "").strip()
            if not text or element is member:
                continue
            if name in feature["properties"]:
                feature["properties_dropped"].append(name)
                continue
            feature["properties"][name] = text
        features.append(feature)
    if not features:
        raise ValueError(
            "a FeatureCollection with no members; a query that matched nothing "
            "and a document this parser misread are different answers, so the "
            "caller has to read numberMatched to tell them apart"
        )
    return features


def number_matched(xml: str | bytes) -> int | None:
    """What the service says the query matches, in total, or None.

    None means the service declined to say, and `wfs.geonorge.no` declines on
    every GetFeature: it answers `numberMatched="unknown"` and
    `numberReturned="0"` while returning three features, with a comment in the
    payload explaining that the WFS 2.0 schema will not let it write "unknown"
    in the second field. So neither attribute can be trusted on a GetFeature
    there, and `numberReturned` is not read at all.

    The count comes from a separate request instead:

        ?service=WFS&version=2.0.0&request=GetFeature
        &typeNames=app:Hornkoraller&resultType=hits

    which answers `numberMatched="1993"` and no features. One extra request
    per layer, and it is the only honest total -- `count=1` returns one
    feature whatever the real number is.
    """

    root = ET.fromstring(xml)
    raw = root.get("numberMatched")
    if raw in (None, "unknown"):
        return None
    try:
        return int(raw)
    except ValueError:
        return None
