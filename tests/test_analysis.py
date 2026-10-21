from __future__ import annotations

import json

from public_data_agent.analysis import run_analysis
from public_data_agent.analysis import GEOMETRY_BUDGET, RECORD_PAGE, run_record_analysis



class RegistryStub:
    def get_dataset(self, dataset_id):
        return {"title": "Demo", "publisher_name": "Publisher", "license": None, "access_path": "https://example.test/data"}

    def list_observations(self, dataset_id, *, series=None):
        return [
            {"id": "1", "table_id": "t", "measure": "count", "value_json": "12", "dimensions_json": '{"år":"2025","region":"Oslo"}'},
            {"id": "2", "table_id": "t", "measure": "count", "value_json": "9", "dimensions_json": '{"år":"2024","region":"Bergen"}'},
        ]


def test_run_analysis_filters_stored_cells_and_preserves_provenance() -> None:
    result = run_analysis(RegistryStub(), "demo", filters={"region": "Oslo"}, columns=["observation_id", "value", "dimensions"])
    assert result.status == "completed"
    assert result.values == [{"observation_id": "1", "value": 12, "dimensions": {"år": "2025", "region": "Oslo"}}]
    assert result.provenance[0].license is None
    assert result.numbers_retrieved is True


def test_run_analysis_groups_and_sorts_stored_cells() -> None:
    result = run_analysis(RegistryStub(), "demo", group_by=["region"], aggregate="sum", sort_by="value", descending=True)
    assert [row["value"] for row in result.values] == [12, 9]
    assert result.values[0]["region"] == "Oslo"
    assert result.values[0]["aggregate"] == "sum"


class RecordRegistryStub:
    """A dataset of things rather than measurements, in the store that holds them."""

    def __init__(self, count: int) -> None:
        self.rows = [
            {
                "id": f"entity:klass:1:{index}",
                "dataset_id": "klass:1",
                "kind": "entity",
                "series": "fetch:klass:1",
                "subject_scheme": "klass:1",
                "subject_code": f"{index:04d}",
                "subject_label": f"Kommune {index}",
                "period": None,
                "measure": None,
                "value_json": None,
                "attributes_json": '{"level":"2"}',
            }
            for index in range(count)
        ]

    def get_dataset(self, dataset_id):
        return {
            "title": "Kommuneinndeling",
            "publisher_name": "SSB",
            "license": None,
            "access_path": "https://example.test/klass/1",
        }

    def list_records(self, dataset_id, *, kind=None):
        return [row for row in self.rows if kind is None or row["kind"] == kind]


def test_record_analysis_says_how_many_it_left_out() -> None:
    """A truncated list that looks complete is how a caller comes to report
    "Norway has 200 municipalities"."""

    result = run_record_analysis(RecordRegistryStub(250), "klass:1")
    assert len(result.values) == RECORD_PAGE
    assert any("250 records matched" in warning for warning in result.warnings)
    assert result.values[0]["value"] is None
    assert result.provenance[0].access_path == "https://example.test/klass/1"


def test_record_analysis_filters_on_the_subject_and_on_attributes() -> None:
    registry = RecordRegistryStub(250)

    by_code = run_record_analysis(registry, "klass:1", filters={"subject_code": "0007"})
    assert [row["subject_label"] for row in by_code.values] == ["Kommune 7"]
    assert not by_code.warnings

    # An attribute is addressed by its own name, because a record's dimensions
    # are published keys, not a fixed schema.
    by_attribute = run_record_analysis(registry, "klass:1", filters={"level": "2"}, limit=3)
    assert len(by_attribute.values) == 3
    assert any("250 records matched" in warning for warning in by_attribute.warnings)

    assert run_record_analysis(registry, "klass:1", filters={"level": "9"}).values == []


class GeometryRegistryStub(RecordRegistryStub):
    """Features whose shapes are large, which is the normal case.

    One Havforskningsinstituttet advisory polygon carries 24 MB of
    coordinates, so a page of them is a download that happens to be shaped
    like an answer.
    """

    def __init__(self, count: int, *, coordinate_pairs: int) -> None:
        super().__init__(count)
        shape = {"type": "MultiPolygon", "coordinates": [[[5.0, 60.0]] * coordinate_pairs]}
        for row in self.rows:
            row["kind"] = "feature"
            row["geometry_json"] = json.dumps(shape)


def test_a_geometry_is_named_before_it_is_spent() -> None:
    registry = GeometryRegistryStub(3, coordinate_pairs=10)
    result = run_record_analysis(registry, "hi:x", kind="feature")
    assert [row["geometry_type"] for row in result.values] == ["MultiPolygon"] * 3
    assert all("geometry" not in row for row in result.values)
    assert any("include_geometry=true" in warning for warning in result.warnings)


def test_whole_shapes_are_returned_until_the_budget_is_spent() -> None:
    """A geometry is complete or absent, never truncated.

    Half a polygon is a different place, so the budget drops whole shapes and
    says how many it dropped rather than cutting any of them short.
    """

    registry = GeometryRegistryStub(40, coordinate_pairs=2000)
    result = run_record_analysis(registry, "hi:x", kind="feature", include_geometry=True)
    included = [row for row in result.values if "geometry" in row]
    assert 0 < len(included) < 40
    assert all(len(row["geometry"]["coordinates"][0]) == 2000 for row in included)
    spent = sum(len(json.dumps(row["geometry"])) for row in included)
    assert spent <= GEOMETRY_BUDGET
    assert any("left out to stay under" in warning for warning in result.warnings)


def test_a_dataset_with_records_is_not_told_to_fetch() -> None:
    """The advice was written for a world where records did not exist.

    17,900 rows moved into `records`, and a dataset holding only those was
    still told "call fetch for this dataset first" -- sending the caller to
    the network for data already in the registry.
    """

    class _Registry(RecordRegistryStub):
        def list_observations(self, dataset_id, *, series=None):
            return []

        @property
        def conn(self):
            raise AssertionError("stored_records should be the only query here")

    class _WithRecords(_Registry):
        def __init__(self) -> None:
            super().__init__(3)

    registry = _WithRecords()
    # `stored_records` goes through `conn`, so this pins the message by calling
    # the warning builder with the counts it would have read.
    from public_data_agent.analysis import _analysis_warnings

    import public_data_agent.analysis as analysis_module

    original = analysis_module.stored_records
    analysis_module.stored_records = lambda reg, ds: {"entity": 3}
    try:
        warnings = _analysis_warnings(
            registry, "klass:1", [], filters={}, measure=None,
            series=None, group_by=None, aggregate=None,
        )
    finally:
        analysis_module.stored_records = original
    assert warnings
    assert "3 entity records are already stored" in warnings[0]
    assert "Do not fetch" in warnings[0]
