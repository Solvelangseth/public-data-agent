from __future__ import annotations

import csv

from public_data_agent.artifacts import export_csv, plot_values
from public_data_agent.contracts import Provenance, ToolResult


def _result() -> ToolResult:
    return ToolResult(
        status="completed",
        values=[{"label": "Oslo", "value": 12}, {"label": "Bergen", "value": 9}],
        provenance=[Provenance("demo")],
    )


def test_export_csv_contains_values_and_lineage(tmp_path) -> None:
    path = tmp_path / "result.csv"
    artifact = export_csv(_result(), path)
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["value"] == "12"
    assert artifact.rows == 2
    assert artifact.lineage == ("demo",)


def test_plot_values_writes_png(tmp_path) -> None:
    artifact = plot_values(_result(), tmp_path / "chart.png")
    assert artifact.media_type == "image/png"
    assert (tmp_path / "chart.png").is_file()
