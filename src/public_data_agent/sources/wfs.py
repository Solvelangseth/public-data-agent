"""Read features from a WFS, which is a different thing from reading its menu.

`fetch.py` refuses every URL carrying `/wfs`, `/ows` or `service=wfs`, and it
is right to: fetching a `GetCapabilities` once stored seventeen layer names as
observations, with `measure: "title"` and values like "This document as HTML".
A capabilities document is a listing of what a service offers, which is
metadata.

A `GetFeature` response is not that. It is the things themselves -- 1,993
coral observations with species, depth, date and bottom type -- and they are
things in places, so they land in `records` as `feature`, exactly as the NGU
features do. The guard therefore has to separate the two requests rather than
the two protocols, and `is_wfs_feature_url` is where that line is drawn.

165 Geonorge datasets declare a WFS, 116 of them are in this registry, and
**none has ever been asked**. The services behind them hold 797 layers, which
is four times what the catalogue itemises.

Output format is GML, not GeoJSON, and that was measured rather than assumed:
128 of the 130 answering addresses advertise GML alone, `wfs.geonorge.no` and
`kart.ssb.no` both answer HTTP 400 to `outputFormat=application/json`, and 97
of the 165 declarations are on `wfs.geonorge.no`. `gml.py` does the parsing.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from public_data_agent.gml import features_from_gml, number_matched

# A layer name is `app:Hornkoraller` in a capabilities document and
# `mareano_biologi/bomtraal_arter` in some catalogue records. Same layer, two
# spellings, and `typeNames` takes the first.
PREFIX_SEPARATORS = ("/", ":")

# What a feature is called, when the publisher gives it a name at all. SOSI
# product specifications suffix a name field with `navn`; everything else here
# is an identifier, and a record that carries only an identifier is correct --
# inventing a label for it is the failure the whole record migration was about.
NAME_SUFFIXES = ("navn", "name", "tittel")
ID_FIELDS = ("lokalId", "lokalid", "identifikasjon", "id", "objid")

# Paging. A WFS returns everything it has unless told otherwise, and some of
# these layers hold tens of thousands of features on a machine with no room
# for them.
DEFAULT_COUNT = 1000


def normalise_layer(layer: str | None) -> str | None:
    """`a/b` -> `a:b`, and anything already colon-separated left alone.

    The catalogue writes `mareano_biologi/bomtraal_arter` for a layer whose
    capabilities document calls it `mareano_biologi:bomtraal_arter`. Sending
    the slash form as `typeNames` returns an exception report, which reads as
    a dead layer.
    """

    if not layer or not isinstance(layer, str):
        return None
    layer = layer.strip()
    if not layer:
        return None
    if ":" in layer:
        return layer
    if "/" in layer:
        head, _, tail = layer.rpartition("/")
        return f"{head}:{tail}"
    return layer


def is_wfs_feature_url(url: str | None) -> bool:
    """True only for a WFS `GetFeature` that names a layer.

    Three conditions, and all three are needed. Without `service=WFS` this
    matches an OGC API Features path. Without `request=GetFeature` it matches
    the capabilities document, which is the metadata this registry spent a
    migration removing. Without a `typeNames` it is a request for everything
    the service holds, which no server answers and which names no dataset.
    """

    if not url or not isinstance(url, str):
        return False
    query = {key.casefold(): str(value) for key, value in parse_qsl(urlsplit(url).query)}
    if query.get("service", "").casefold() != "wfs":
        return False
    if query.get("request", "").casefold() != "getfeature":
        return False
    return bool(query.get("typenames") or query.get("typename"))


def getfeature_url(
    address: str,
    layer: str,
    *,
    count: int = DEFAULT_COUNT,
    start: int | None = None,
    version: str = "2.0.0",
) -> str:
    """A GetFeature URL for one layer, with the publisher's own query kept.

    The declared address usually carries `request=GetCapabilities`; that is
    replaced rather than appended to, because a query with two `request`
    parameters is answered differently by different servers and this must not
    depend on which.
    """

    normalised = normalise_layer(layer)
    if not normalised:
        raise ValueError("a GetFeature needs a layer name; none was given")
    parts = urlsplit(address)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query)
        if key.casefold() not in {
            "service", "request", "version", "typenames", "typename",
            "count", "startindex", "outputformat", "acceptversions",
        }
    ]
    query.extend([
        ("service", "WFS"),
        ("version", version),
        ("request", "GetFeature"),
        ("typeNames", normalised),
        ("count", str(count)),
    ])
    if start:
        query.append(("startIndex", str(start)))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def hits_url(address: str, layer: str, *, version: str = "2.0.0") -> str:
    """The same request asking only how many there are.

    `wfs.geonorge.no` answers every GetFeature with
    `numberMatched="unknown" numberReturned="0"` while returning features, so
    neither attribute can be read off a data response. `resultType=hits` is
    the only honest total.
    """

    return getfeature_url(address, layer, count=1, version=version) + "&resultType=hits"


def _is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool))


def _name_field(properties: dict[str, Any]) -> str | None:
    for field in sorted(properties):
        lowered = field.casefold()
        if any(lowered.endswith(suffix) for suffix in NAME_SUFFIXES):
            value = properties[field]
            if isinstance(value, str) and value.strip():
                return field
    return None


def cells_from_wfs(xml: str | bytes) -> list[tuple[str, Any, dict[str, str]]]:
    """One cell per feature, the way the NGU reader does it.

    The cell's measure is the field that names the feature, and where the
    publisher prints no name it is the identifier field instead -- the record
    then carries a code and no label, which is the honest outcome.

    Geometry is carried in the dimensions as named ordinates, never as a bare
    pair: `gml:pos` under `EPSG::4258` is latitude first and the same
    publisher's GeoJSON is longitude first, so a pair with no names is a
    coin toss about which hemisphere a feature is in.
    """

    features = features_from_gml(xml)
    cells: list[tuple[str, Any, dict[str, str]]] = []
    for feature in features:
        properties = {
            key: value
            for key, value in (feature.get("properties") or {}).items()
            if _is_scalar(value) and value is not None and str(value).strip()
        }
        dimensions = {key: str(value) for key, value in properties.items()}
        if feature.get("id"):
            dimensions.setdefault("gml:id", str(feature["id"]))
        geometry = feature.get("geometry")
        if isinstance(geometry, dict):
            for key, value in geometry.items():
                if value is not None:
                    dimensions[f"geometry.{key}"] = str(value)
        if feature.get("geometry_type"):
            dimensions["geometry.type"] = str(feature["geometry_type"])
        if not dimensions:
            continue
        measure = _name_field(properties)
        if measure is not None:
            cells.append((measure, properties.get(measure), dimensions))
            continue
        # No name printed. The cell then carries the identifier as its measure
        # and **no value**, which is how `records_from_cells` is told to store
        # a code with no label. Passing the identifier as the value too makes
        # `subject_label` a copy of `subject_code` -- a label that says
        # nothing, which is one step from the invented names this registry
        # spent a migration removing. The species, depth and bottom type stay
        # in the attributes either way; what is refused is calling a UUID a
        # name.
        identifier = next((field for field in ID_FIELDS if properties.get(field)), None)
        if identifier is None and feature.get("id"):
            identifier = "gml:id"
        if identifier is None:
            continue
        cells.append((identifier, None, dimensions))
    if not cells:
        raise ValueError(
            "the GetFeature response parsed and held no feature with any scalar "
            "property; an empty layer and a response this reader misread are "
            "different answers"
        )
    return cells


def wfs_table_id(url: str) -> str:
    """The layer name, which is what identifies the rows within a service.

    Many datasets share one address -- 11 Fiskeridirektoratet datasets sit on
    one `WFSServer` -- so the host is not an identifier and the layer is.
    """

    query = {key.casefold(): str(value) for key, value in parse_qsl(urlsplit(url).query)}
    layer = query.get("typenames") or query.get("typename") or ""
    return layer or urlsplit(url).path.strip("/").replace("/", ":")


def total_from_hits(xml: str | bytes) -> int | None:
    """How many features the layer holds, from a `resultType=hits` response.

    None when the service declines to say. That is not a failure and must not
    become a zero: a layer whose size is unknown and a layer that is empty are
    different facts, and only one of them means there is nothing to fetch.
    """

    return number_matched(xml)


def hits_url_for(feature_url: str) -> str:
    """Turn a GetFeature URL into the request that only counts.

    `hits_url` builds one from an address and a layer; this takes the URL the
    connector already holds, so the count is asked of exactly the layer that
    was read rather than of one rebuilt from parts that might differ.

    `count` and `startIndex` are dropped: a hits request with a page size
    attached returns the page size on some servers, which would make the
    denominator equal to the sample and the sample rate always 100%.

    The colon is percent-encoded, as everywhere else. That took two attempts
    to establish, and the first one was wrong in a way worth recording.

    One request per spelling suggested the server cared which encoding it got
    and flipped depending on whether `count` or `resultType` was present --
    four cells, four clean answers, a tidy story. Six requests per spelling
    say otherwise:

        typeNames=app%3AHornkoraller &resultType=hits   200 x6
        typeNames=app:Hornkoraller   &resultType=hits   200 x3, 404 x3
        typeNames=app%3AHornkoraller &count=2           200 x6
        typeNames=app:Hornkoraller   &count=2           200 x6

    `wfs.geonorge.no` is simply **flaky on the unencoded colon** -- one
    backend behind it decodes differently from the others -- and the single
    sample had caught three of the four cells on the wrong side of a coin
    flip. The encoded form is the reliable one.

    A failure here is still treated as "no total", never as an empty layer.
    """

    parts = urlsplit(feature_url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query)
        if key.casefold() not in {"count", "startindex", "resulttype", "outputformat"}
    ]
    query.append(("resultType", "hits"))
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), "")
    )


def property_filter_url(
    address: str,
    layer: str,
    field: str,
    value: str,
    *,
    count: int = DEFAULT_COUNT,
    version: str = "2.0.0",
) -> str:
    """A GetFeature for the features whose `field` equals `value`.

    **OGC `FILTER`, not `CQL_FILTER`**, and the difference is not stylistic.
    Measured on `wfs.hornkoraller`, whose unfiltered total is 1,993:

        CQL_FILTER=art='Radicipes'   HTTP 200, numberMatched 1993
        FILTER=<PropertyIsEqualTo…>  HTTP 200, numberMatched  119

    The CQL form is **accepted and ignored**. A reader that used it would
    store all 1,993 corals under each of the five species datasets, with a
    200 on every request and nothing anywhere saying the filter had not
    applied. Which is why `filtered_count_is_credible` exists below: a filter
    that returns the unfiltered total did not filter.
    """

    escaped = (
        str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    ogc = (
        "<Filter><PropertyIsEqualTo>"
        f"<ValueReference>{field}</ValueReference>"
        f"<Literal>{escaped}</Literal>"
        "</PropertyIsEqualTo></Filter>"
    )
    return getfeature_url(address, layer, count=count, version=version) + "&FILTER=" + quote(ogc)


def filtered_count_is_credible(filtered: int | None, unfiltered: int | None) -> bool:
    """False when a filter plainly did not apply.

    A filtered count equal to the unfiltered one is the signature of a server
    that accepted the parameter and ignored it. It is not proof of a bug --
    a filter can legitimately match everything -- but on a layer partitioned
    into several subsets it never should, and the caller is better off
    refusing than storing a whole layer under one of its parts.
    """

    if filtered is None or unfiltered is None:
        return True
    return filtered < unfiltered
