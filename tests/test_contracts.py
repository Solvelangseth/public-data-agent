from __future__ import annotations

from public_data_agent.contracts import Artifact, Provenance, ToolResult


def test_provenance_preserves_unknown_license_as_null() -> None:
    item = Provenance(dataset_id="ssb:11763", publisher="SSB")
    assert item.to_dict()["license"] is None
    assert item.to_dict()["dataset_id"] == "ssb:11763"


def test_tool_result_only_reports_numbers_from_values() -> None:
    empty = ToolResult(status="not_fetched")
    assert empty.numbers_retrieved is False
    assert empty.to_dict()["numbers_retrieved"] is False

    result = ToolResult(status="completed", values=[{"value": 12}], provenance=[])
    assert result.numbers_retrieved is True

    metadata = ToolResult(status="completed", values=[{"value": "unknown"}])
    assert metadata.numbers_retrieved is False


def test_artifact_serializes_lineage_and_columns() -> None:
    artifact = Artifact(
        kind="csv",
        path="/tmp/result.csv",
        media_type="text/csv",
        rows=2,
        columns=("value", "dataset_id"),
        lineage=("ssb:11763", "methods.yoy"),
    )
    assert artifact.to_dict() == {
        "kind": "csv",
        "path": "/tmp/result.csv",
        "media_type": "text/csv",
        "rows": 2,
        "columns": ["value", "dataset_id"],
        "lineage": ["ssb:11763", "methods.yoy"],
    }
