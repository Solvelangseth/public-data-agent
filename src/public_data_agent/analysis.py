"""Small deterministic operations over stored observation cells."""

from __future__ import annotations

import json
from typing import Any

from public_data_agent.contracts import Provenance, ToolResult
from public_data_agent.registry import Registry


def run_analysis(
    registry: Registry,
    dataset_id: str,
    *,
    filters: dict[str, str] | None = None,
    measure: str | None = None,
    columns: list[str] | None = None,
) -> ToolResult:
    """Filter/select stored cells; never fetches or invents missing values."""
    dataset = registry.get_dataset(dataset_id)
    if dataset is None:
        return ToolResult(status="failed", error=f"dataset not found in registry: {dataset_id}")
    filters = filters or {}
    rows: list[dict[str, Any]] = []
    for row in registry.list_observations(dataset_id):
        dimensions = _decode(row.get("dimensions_json")) or {}
        if measure is not None and row.get("measure") != measure:
            continue
        if any(str(dimensions.get(key)) != str(value) for key, value in filters.items()):
            continue
        item = {
            "observation_id": row["id"],
            "dataset_id": dataset_id,
            "table_id": row["table_id"],
            "measure": row["measure"],
            "value": _decode(row.get("value_json")),
            "dimensions": dimensions,
        }
        if columns:
            item = {key: item[key] for key in columns if key in item}
        rows.append(item)
    provenance = [
        Provenance(
            dataset_id=dataset_id,
            title=dataset.get("title"),
            publisher=dataset.get("publisher_name"),
            license=dataset.get("license"),
            access_path=dataset.get("access_path"),
        )
    ]
    return ToolResult(status="completed", values=rows, provenance=provenance)


def _decode(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value
