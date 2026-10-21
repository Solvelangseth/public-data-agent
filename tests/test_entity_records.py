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
