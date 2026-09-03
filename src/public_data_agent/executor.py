"""Deterministic execution of validated plans."""

from __future__ import annotations

import json
from typing import Any

from public_data_agent.contracts import Provenance, ToolResult
from public_data_agent.fetch import JsonHttp, fetch_observations
from public_data_agent.planner import QuestionPlan
from public_data_agent.registry import Registry


def execute_plan(registry: Registry, plan: QuestionPlan, *, http: JsonHttp | None = None) -> ToolResult:
    """Execute fetch steps only after validating their dependency order.

    Joins and methods are deliberately refused here until their explicit
    generic implementations are registered; returning no derived values is
    safer than guessing a shape or key.
    """
    fetched_any = False
    values: list[dict[str, Any]] = []
    provenance: list[Provenance] = []
    warnings: list[str] = []
    for step in plan.steps:
        if step.kind in {"join", "derive", "filter", "reshape", "visualize", "export"} and not fetched_any:
            return ToolResult(
                status="failed",
                warnings=warnings,
                error=f"cannot execute {step.kind} before a successful fetch",
            )
        if step.kind != "fetch":
            if step.kind in {"join", "derive", "filter", "reshape", "visualize", "export"}:
                warnings.append(f"{step.kind} is not registered for generic plans; no derived value emitted")
            continue
        if not step.dataset_id or not step.table_id:
            return ToolResult(status="failed", error="fetch step requires dataset_id and table_id")
        try:
            fetched = fetch_observations(registry, step.dataset_id, table_id=step.table_id, http=http)
        except Exception as exc:
            return ToolResult(status="failed", warnings=warnings, error=str(exc))
        fetched_any = True
        dataset = registry.get_dataset(step.dataset_id) or {}
        for row in registry.list_observations(step.dataset_id):
            value = _decode(row.get("value_json"))
            values.append({"observation_id": row["id"], "dataset_id": step.dataset_id, "table_id": step.table_id, "measure": row.get("measure"), "value": value, "dimensions": _decode(row.get("dimensions_json"))})
        provenance.append(Provenance(dataset_id=step.dataset_id, title=dataset.get("title"), publisher=dataset.get("publisher_name"), license=dataset.get("license"), access_path=dataset.get("access_path"), request_url=fetched.request_url))
    if not fetched_any:
        return ToolResult(status="not_fetched", warnings=warnings, error=plan.refusal_reason)
    return ToolResult(status="completed", values=values, provenance=provenance, warnings=warnings)


def _decode(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value
