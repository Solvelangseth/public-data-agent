"""Persist analysis results as local user artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from public_data_agent.contracts import Artifact, ToolResult


def export_csv(result: ToolResult, path: Path) -> Artifact:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = result.values
    columns = tuple(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _cell(row.get(key)) for key in columns})
    return Artifact("csv", str(path), "text/csv", len(rows), columns, tuple(p.dataset_id for p in result.provenance))


def export_json(result: ToolResult, path: Path) -> Artifact:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return Artifact("json", str(path), "application/json", len(result.values), (), tuple(p.dataset_id for p in result.provenance))


def plot_values(result: ToolResult, path: Path, *, label: str = "label") -> Artifact:
    """Create a simple bar chart from numeric result values only."""
    import matplotlib.pyplot as plt

    points = [(str(row.get(label, index)), row.get("value")) for index, row in enumerate(result.values)]
    points = [(key, value) for key, value in points if isinstance(value, (int, float)) and not isinstance(value, bool)]
    if not points:
        raise ValueError("no numeric values available for visualization")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axis = plt.subplots(figsize=(8, 4.5))
    axis.bar([item[0] for item in points], [item[1] for item in points])
    axis.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return Artifact("chart", str(path), "image/png", len(points), (label, "value"), tuple(p.dataset_id for p in result.provenance))


def _cell(value: Any) -> Any:
    return json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else value
