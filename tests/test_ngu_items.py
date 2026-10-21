"""The NGU connector stored link titles as observations. These stop that.

Fetching `ngu:ankringsforhold` produced seventeen rows whose measure was
`title` and whose values were "This document as HTML" and "OGC API
conformance classes implemented by this server", and marked the dataset
verified with a sample count of 17. The function doing it said so in its own
docstring.
"""

from __future__ import annotations

import pytest

from public_data_agent.sources.ngu import (
    DATA_REL,
    cells_from_ngu,
    cells_from_ngu_items,
    collections_url,
    items_url,
    printed_collections,
)

LANDING = {
    "title": "Marin: Ankringsforhold",
    "links": [
        {"rel": "self", "type": "application/json", "title": "This document",
         "href": "https://geo.ngu.no/api/features/ankringsforhold?f=json"},
        {"rel": "alternate", "type": "text/html", "title": "This document as HTML",
         "href": "https://geo.ngu.no/api/features/ankringsforhold?f=html"},
        {"rel": DATA_REL, "type": "application/json",
         "title": "Access the data (ankringOmr, Dataavgrensning, GeolAvgrLinje)",
         "href": "https://geo.ngu.no/api/features/ankringsforhold/collections"},
    ],
}

ITEMS = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "id": "ankringOmr.1",
            "geometry": {"type": "Polygon", "coordinates": [[[10.0, 60.0]]]},
            "properties": {
                "ankringsforhold": 2,
                "ankringsforholdNavn": "Gode ankringsforhold",
                "identifikasjon.lokalId": "abc-123",
                "datauttaksdato": "2024-05-02",
                "opphav": None,
            },
        }
    ],
}


def test_a_landing_page_is_refused_rather_than_stored() -> None:
    """"This document as HTML" is not an observation of anything."""

    with pytest.raises(ValueError) as caught:
        cells_from_ngu(LANDING)
    message = str(caught.value)
    assert "lists links, not features" in message
    assert DATA_REL in message, "the error says which link to follow"


def test_the_data_link_is_read_rather_than_composed() -> None:
    """`access_path + "/collections"` gives the same string today and is a guess."""

    assert collections_url(LANDING, "https://geo.ngu.no/api/features/ankringsforhold") == (
        "https://geo.ngu.no/api/features/ankringsforhold/collections"
    )
    without = {"links": [link for link in LANDING["links"] if link["rel"] != DATA_REL]}
    with pytest.raises(ValueError, match="prints no"):
        collections_url(without, "https://geo.ngu.no/api/features/ankringsforhold")


def test_a_collections_payload_yields_its_items_link() -> None:
    payload = {"collections": [{
        "id": "ankringOmr",
        "links": [
            {"rel": "items", "type": "text/html", "href": "https://geo.ngu.no/x?f=html"},
            {"rel": "items", "type": "application/geo+json", "href": "https://geo.ngu.no/x?f=json"},
        ],
    }]}
    (collection,) = printed_collections(payload)
    assert items_url(collection) == "https://geo.ngu.no/x?f=json"
    assert items_url({"links": [{"rel": "items", "type": "text/html", "href": "https://x"}]}) is None, (
        "an HTML items link is a page, not data"
    )
    with pytest.raises(ValueError, match="no collections array"):
        printed_collections({"collections": []})


def test_a_feature_is_named_by_the_publishers_own_Navn_field() -> None:
    """NGU writes `ankringsforhold` beside `ankringsforholdNavn`.

    The old NAME_FIELDS were title/rel/href, which are link fields and mean
    nothing on a seabed polygon.
    """

    (measure, value, dims) = cells_from_ngu_items(ITEMS)[0]
    assert measure == "ankringsforholdNavn"
    assert value == "Gode ankringsforhold"
    assert dims["ankringsforhold"] == "2"
    assert dims["identifikasjon.lokalId"] == "abc-123", "a dotted name is kept as printed"
    assert dims["id"] == "ankringOmr.1"
    assert "opphav" not in dims, "a null property is not a dimension"
    assert "geometry" not in dims


def test_a_feature_with_no_name_field_falls_back_to_its_identifier() -> None:
    payload = {"features": [{
        "id": "x.1",
        "properties": {"identifikasjon.lokalId": "abc-123", "datauttaksdato": "2024-05-02"},
    }]}
    (measure, value, _dims) = cells_from_ngu_items(payload)[0]
    assert measure == "identifikasjon.lokalId"
    assert value == "abc-123"


def test_an_empty_or_wrong_payload_is_refused() -> None:
    with pytest.raises(ValueError, match="no features array"):
        cells_from_ngu_items({"type": "FeatureCollection"})
    with pytest.raises(ValueError, match="no feature with properties"):
        cells_from_ngu_items({"features": [{"id": "x", "properties": {}}]})
    with pytest.raises(ValueError, match="not a JSON object"):
        cells_from_ngu_items([ITEMS])
