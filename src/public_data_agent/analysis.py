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
    filters: dict[str, Any] | None = None,
    measure: str | None = None,
    columns: list[str] | None = None,
    group_by: list[str] | None = None,
    aggregate: str | None = None,
    sort_by: str | None = None,
    descending: bool = False,
) -> ToolResult:
    """Filter/select stored cells; never fetches or invents missing values."""
    dataset = registry.get_dataset(dataset_id)
    if dataset is None:
        return ToolResult(status="failed", error=f"dataset not found in registry: {dataset_id}")
    filters = filters or {}
    rows: list[dict[str, Any]] = []
    for row in registry.list_observations(dataset_id):
        dimensions = _decode(row.get("dimensions_json")) or {}
        # Agents commonly use ``measure=value`` to request numeric cells.  The
        # stored measure label is source-defined and must not be guessed.
        if measure is not None and measure != "value" and row.get("measure") != measure:
            continue
        if any(
            (str(dimensions.get(key)) not in {str(item) for item in value} if isinstance(value, (list, tuple, set)) else str(dimensions.get(key)) != str(value))
            for key, value in filters.items()
        ):
            continue
        item = {
            "observation_id": row["id"],
            "dataset_id": dataset_id,
            "table_id": row["table_id"],
            "measure": row["measure"],
            "value": _decode(row.get("value_json")),
            "dimensions": dimensions,
        }
        rows.append(item)
    if group_by:
        rows = _aggregate(rows, group_by, aggregate or "count")
    if columns:
        rows = [{key: item[key] for key in columns if key in item} for item in rows]
    if sort_by:
        rows.sort(key=lambda item: (item.get(sort_by) is None, item.get(sort_by)), reverse=descending)
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


def _aggregate(rows: list[dict[str, Any]], group_by: list[str], aggregate: str) -> list[dict[str, Any]]:
    if aggregate not in {"count", "sum", "mean"}:
        raise ValueError("aggregate must be count, sum, or mean")
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        dimensions = row.get("dimensions") or {}
        key = tuple(row.get(field, dimensions.get(field)) for field in group_by)
        groups.setdefault(key, []).append(row)
    out: list[dict[str, Any]] = []
    for key, members in groups.items():
        item = {field: value for field, value in zip(group_by, key)}
        if aggregate == "count":
            value: Any = len(members)
        else:
            numeric = [member.get("value") for member in members if isinstance(member.get("value"), (int, float)) and not isinstance(member.get("value"), bool)]
            value = (sum(numeric) / len(numeric)) if aggregate == "mean" and numeric else (sum(numeric) if numeric else None)
        item.update({"value": value, "aggregate": aggregate, "count": len(members)})
        out.append(item)
    return out
