from __future__ import annotations

from public_data_agent.analysis import run_analysis


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
