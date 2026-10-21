"""The rule that decides what a row is about.

These cases are the ones that have actually been got wrong, each by a
different connector, so they are kept as the record of why the rule reads the
way it does.
"""

from __future__ import annotations

from public_data_agent.entity_records import (
    AIRQUALITY_ID_FIELDS,
    AIRQUALITY_LABEL_FIELDS,
    GREP_ID_FIELDS,
    NORGESBANK_ID_FIELDS,
    cells_are_labels,
    records_from_cells,
)


def test_the_measure_wins_when_it_ranks_higher() -> None:
    """Udir prints `kode` as the measure and an `id` UUID as a dimension.

    Reading the dimensions first keyed every curriculum item by its UUID.
    """

    (record,) = records_from_cells(
        [("kode", "aarstrinn1", {"id": "uuid:1", "status": "publisert"})],
        dataset_id="grep:aarstrinn",
        table_id="aarstrinn",
        id_fields=GREP_ID_FIELDS,
        prefix="grep",
    )
    assert record["subject_code"] == "aarstrinn1"
    assert record["subject_label"] is None
    assert record["attributes"] == {"id": "uuid:1", "status": "publisert"}


def test_a_dimension_wins_when_it_ranks_higher() -> None:
    """Air quality prints `name` as the measure and `eoi` as a dimension.

    Reading the measure first made the station's own name its code and left it
    with no label at all, and a resource of codes without names then reads as
    a lookup rather than a register of stations.
    """

    (record,) = records_from_cells(
        [("name", "Alnabru", {"eoi": "NO0057A", "kommune": "Oslo"})],
        dataset_id="airquality:stations",
        table_id="stations",
        id_fields=AIRQUALITY_ID_FIELDS,
        label_fields=AIRQUALITY_LABEL_FIELDS,
        prefix="airquality",
    )
    assert record["subject_code"] == "NO0057A"
    assert record["subject_label"] == "Alnabru"


def test_the_measure_is_the_code_when_no_dimension_carries_one() -> None:
    """The same source's other endpoint, where the name is the code.

    `areaclasses` prints `name = "grunnkrets"` with the human reading under
    `desc`, so the value is the handle and the description is the label.
    """

    (record,) = records_from_cells(
        [("name", "grunnkrets", {"desc": "Grunnkrets"})],
        dataset_id="airquality:areaclasses",
        table_id="areaclasses",
        id_fields=AIRQUALITY_ID_FIELDS,
        label_fields=AIRQUALITY_LABEL_FIELDS,
        prefix="airquality",
    )
    assert record["subject_code"] == "grunnkrets"
    assert record["subject_label"] == "Grunnkrets"
    assert record["attributes"] == {}


def test_a_measure_that_repeats_its_value_is_naming_something() -> None:
    (record,) = records_from_cells(
        [("NO0013741165", "NO0013741165", {"TIME_PERIOD": "2026-07-28"})],
        dataset_id="norgesbank:CBC_CALENDAR",
        table_id="CBC_CALENDAR",
        id_fields=NORGESBANK_ID_FIELDS,
        prefix="norgesbank",
    )
    assert record["subject_code"] == "NO0013741165"
    assert record["subject_label"] is None


def test_a_row_with_no_identifier_is_keyed_by_what_it_printed() -> None:
    """Position is not an identity, and a re-fetch proved it.

    `basemap_land_2` returns seven continents and none of them carries a code.
    Keyed positionally, `Europe_Asia` was row0 in one fetch and row6 in the
    next, so the re-fetch created a second record for the same continent and
    relabelled the first.
    """

    cells = [("continent", "Europe_Asia", {}), ("continent", "Africa", {})]
    records = records_from_cells(
        cells, dataset_id="hi:basemap", table_id="basemap",
        id_fields=("fid",), prefix="hi", kind="feature",
    )
    assert [record["subject_code"] for record in records] == [None, None]
    assert len({record["id"] for record in records}) == 2

    # The same member keeps its id however the response is ordered.
    reordered = records_from_cells(
        list(reversed(cells)), dataset_id="hi:basemap", table_id="basemap",
        id_fields=("fid",), prefix="hi", kind="feature",
    )
    assert {record["id"] for record in records} == {record["id"] for record in reordered}


def test_one_number_makes_a_batch_a_measurement_batch() -> None:
    assert cells_are_labels([("rate", "NCB 09/2026", {})])
    assert not cells_are_labels([("rate", "4.25", {}), ("rate", "NCB 09/2026", {})])
    # A suppressed cell is still an observation, so an all-empty batch is not
    # a batch of labels.
    assert not cells_are_labels([("rate", ":", {}), ("rate", None, {})])
    assert not cells_are_labels([])


def test_members_that_differ_only_in_place_keep_different_ids() -> None:
    """A bathymetry collection publishes 157 contours that all say the same thing.

    `depth = 1000`, no identifier, and where they are is the only difference.
    Digested from the properties alone, every one of them got the same handle
    and 157 features collapsed into a single record that reported as a clean
    store.
    """

    cells = [("depth", 1000, {}), ("depth", 1000, {})]
    geometries = [
        {"type": "LineString", "coordinates": [[5.0, 60.0], [5.1, 60.1]]},
        {"type": "LineString", "coordinates": [[10.0, 70.0], [10.1, 70.1]]},
    ]
    records = records_from_cells(
        cells, dataset_id="hi:bathymetry", table_id="bathymetry",
        id_fields=("fid",), prefix="hi", kind="feature", distinguish=geometries,
    )
    assert len({record["id"] for record in records}) == 2

    # Without the geometry there is nothing to tell them apart, and the store
    # refuses rather than letting one overwrite the other.
    collapsed = records_from_cells(
        cells, dataset_id="hi:bathymetry", table_id="bathymetry",
        id_fields=("fid",), prefix="hi", kind="feature",
    )
    assert len({record["id"] for record in collapsed}) == 1


def test_a_number_under_an_identifier_is_not_a_measurement() -> None:
    """`cristin:fundings` was a verified observation source for this reason.

    Its cells held `cristin_funding_id = "1"`, and the rule that correctly
    reads Norges Bank's `"4.25"` as a number read that one too. A quoted
    identifier and a quoted rate are the same string; what tells them apart is
    what the measure is called.
    """

    from public_data_agent.entity_records import identifies_rather_than_measures

    assert identifies_rather_than_measures("cristin_funding_id")
    assert identifies_rather_than_measures("ISIN")
    assert identifies_rather_than_measures("kode")
    assert not identifies_rather_than_measures("Månedslønn (kr)")
    assert not identifies_rather_than_measures("Antall brukere")
    # The word has to end the label: a count of codes still measures.
    assert not identifies_rather_than_measures("Antall koder i bruk")

    assert cells_are_labels([("cristin_funding_id", "1", {})])
    assert not cells_are_labels([("Styringsrente", "4.25", {})])
    # One real measurement is enough, whatever else the batch carries.
    assert not cells_are_labels(
        [("cristin_funding_id", "1", {}), ("Styringsrente", "4.25", {})]
    )


def test_a_layer_descriptor_is_refused_like_the_root_above_it() -> None:
    """One level below a MapServer root, and the same thing in substance.

    A probe reached 39 Sokkeldirektoratet layers, each answering with its own
    column definitions -- OBJECTID, alias, domain, editable, nullable -- and
    stored 840 of them as observations, verified as entities. A query response
    carries `fields` and `features` together, so requiring the absence of
    `features` leaves real data alone.
    """

    import pytest

    from public_data_agent.fetch import ServiceCatalogue, _refuse_service_catalogue

    descriptor = {
        "name": "afex_area",
        "type": "Feature Layer",
        "geometryType": "esriGeometryPolygon",
        "capabilities": "Query",
        "fields": [{"name": "OBJECTID", "type": "esriFieldTypeOID", "alias": "OBJECTID"}],
    }
    with pytest.raises(ServiceCatalogue, match="field definitions"):
        _refuse_service_catalogue(descriptor, dataset_id="sodir:afex_area", url="https://x")

    # The same fields, with rows beside them, is data.
    answered = dict(descriptor, features=[{"attributes": {"OBJECTID": 1}}])
    _refuse_service_catalogue(answered, dataset_id="sodir:afex_area", url="https://x")


def test_preflight_classifies_without_fetching_or_storing() -> None:
    """The verdicts this session learned one source at a time, as shape tests.

    Each of these was found by fetching a payload, printing it and reading it.
    They are code now, which is the difference between a person per source and
    a command for all of them.
    """

    import sys

    sys.path.insert(0, "scripts")
    from preflight import classify

    def verdict(payload, url="https://example.test/x", status=200):
        return classify(status, payload, url)[0]

    assert verdict({"layers": [{"id": 0}]}) == "catalogue"
    assert verdict({"collections": [{"id": "a"}]}) == "catalogue"
    assert verdict({"fields": [{"name": "OBJECTID"}], "type": "Feature Layer"}) == "catalogue"
    assert verdict({"itemType": "feature", "extent": {}}) == "catalogue"
    assert verdict({"capabilities": "Query", "currentVersion": 11.1}) == "catalogue"
    assert verdict({}, url="https://x?service=WMS&request=GetCapabilities") == "catalogue"
    assert verdict({"data": {"codelists": []}, "meta": {}}) == "structure"
    assert verdict({}, url="https://x/$metadata") == "structure"

    # A change log: every published key is bookkeeping.
    assert verdict({"features": [{"properties": {"id": "1", "lastModified": "2021"}}]}) == (
        "bookkeeping"
    )
    # Real features, and a plain JSON array of members.
    assert verdict({"features": [{"properties": {"navn": "Moldfalla", "dybde": 40}}]}) == "rows"
    assert verdict([{"navn": "Oslo"}]) == "rows"

    # What the registry cannot learn from, reported as such rather than guessed.
    assert verdict(None, status=401) == "restricted"
    assert verdict(None, status=404) == "withdrawn"
    assert verdict("TimeoutError", status=0) == "unreachable"
    assert verdict("<?xml version='1.0'?><available/>") == "unclear"
