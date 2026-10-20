from __future__ import annotations

from public_data_agent.analysis import run_analysis
from public_data_agent.analysis import RECORD_PAGE, run_record_analysis



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
