"""Deterministic execution of validated plans."""

from __future__ import annotations

import json
from typing import Any

from public_data_agent.contracts import Provenance, ToolResult
from public_data_agent.fetch import JsonHttp, SelectionTooLarge, fetch_observations
from public_data_agent.join import JOIN_KEY, JOIN_SERIES, join_classification_to_table
from public_data_agent.planner import PlanStep, QuestionPlan
from public_data_agent.registry import Registry

# Step kinds that need data in hand before they mean anything.
NEEDS_DATA = {"join", "derive", "filter", "reshape", "visualize", "export"}
# Step kinds still without a generic implementation. Kept explicit so a plan
# containing one produces a warning rather than a silently missing column.
UNIMPLEMENTED = {"filter", "reshape", "visualize", "export"}


def execute_plan(registry: Registry, plan: QuestionPlan, *, http: JsonHttp | None = None) -> ToolResult:
    """Run a validated plan step by step, in order.

    Every step reads only what earlier steps produced. A step whose inputs are
    missing fails the plan rather than emitting a value built from something
    else; a step kind with no generic implementation warns and emits nothing.
    """

    fetched_any = False
    values: list[dict[str, Any]] = []
    provenance: list[Provenance] = []
    warnings: list[str] = []

    for step in plan.steps:
        if step.kind in NEEDS_DATA and not fetched_any:
            return ToolResult(
                status="failed",
                warnings=warnings,
                error=f"cannot execute {step.kind} before a successful fetch",
            )

        if step.kind == "fetch":
            outcome = _run_fetch(registry, step, http=http)
            if outcome.error is not None:
                return ToolResult(status="failed", warnings=[*warnings, *outcome.warnings], error=outcome.error)
            fetched_any = True
            values.extend(outcome.values)
            provenance.extend(outcome.provenance)
            continue

        if step.kind == "join":
            outcome = _run_join(registry, step, http=http)
            if outcome.error is not None:
                return ToolResult(status="failed", warnings=[*warnings, *outcome.warnings], error=outcome.error)
            warnings.extend(outcome.warnings)
            values.extend(outcome.values)
            provenance.extend(outcome.provenance)
            continue

        if step.kind == "derive":
            derived, notes, error = _run_derive(values)
            if error is not None:
                return ToolResult(status="failed", warnings=warnings, error=error)
            warnings.extend(notes)
            values.extend(derived)
            continue

        if step.kind in UNIMPLEMENTED:
            warnings.append(f"{step.kind} is not registered for generic plans; no derived value emitted")

    if not fetched_any:
        return ToolResult(status="not_fetched", warnings=warnings, error=plan.refusal_reason)
    return ToolResult(status="completed", values=values, provenance=provenance, warnings=warnings)


class _StepOutcome:
    __slots__ = ("values", "provenance", "warnings", "error")

    def __init__(self, values=None, provenance=None, warnings=None, error=None) -> None:
        self.values: list[dict[str, Any]] = values or []
        self.provenance: list[Provenance] = provenance or []
        self.warnings: list[str] = warnings or []
        self.error: str | None = error


def _run_fetch(registry: Registry, step: PlanStep, *, http: JsonHttp | None) -> _StepOutcome:
    if not step.dataset_id or not step.table_id:
        return _StepOutcome(error="fetch step requires dataset_id and table_id")
    try:
        # A plan step already names the periods it needs. Ignoring them fetched
        # whole tables, which on a large table means minutes of work to answer
        # a question about two years.
        from_year = min(step.periods) if step.periods else None
        to_year = max(step.periods) if step.periods else None
        fetched = fetch_observations(
            registry,
            step.dataset_id,
            table_id=step.table_id,
            from_year=from_year,
            to_year=to_year,
            http=http,
        )
    except SelectionTooLarge as exc:
        # Refused before the request, and recoverable: say what to narrow.
        return _StepOutcome(
            warnings=[f"{d['code']}: {d['selected']} of {d['available']}" for d in exc.dimensions],
            error=(
                f"{exc}. Add periods to the plan step, or narrow a dimension, "
                "so the selection fits the source's limit."
            ),
        )
    except Exception as exc:
        return _StepOutcome(error=str(exc))

    dataset = registry.get_dataset(step.dataset_id) or {}
    # Exactly the cells this request covered. Neither the series nor the
    # fetch_run_id identifies them: a row already present is reported
    # "unchanged" and keeps the run id of whichever fetch first wrote it, so
    # scoping by either pulled in years the plan never asked for.
    values = [
        {
            "id": row["id"],
            "observation_id": row["id"],
            "dataset_id": step.dataset_id,
            "table_id": step.table_id,
            "measure": row.get("measure"),
            "value": _decode(row.get("value_json")),
            "dimensions": _decode(row.get("dimensions_json")),
        }
        for row in registry.list_observations(step.dataset_id, ids=fetched.observation_ids)
    ]
    return _StepOutcome(
        values=values,
        provenance=[
            Provenance(
                dataset_id=step.dataset_id,
                title=dataset.get("title"),
                publisher=dataset.get("publisher_name"),
                license=dataset.get("license"),
                access_path=dataset.get("access_path"),
                request_url=fetched.request_url,
            )
        ],
    )


def _run_join(registry: Registry, step: PlanStep, *, http: JsonHttp | None) -> _StepOutcome:
    """Join a Klass classification to an SSB table on codes both sides store.

    `dataset_id` is the classification and `table_id` the table. The key is
    discovered inside the join by matching stored values, so a pair that shares
    no key fails the step rather than producing rows joined on something
    invented.
    """

    if not step.dataset_id or not step.table_id:
        return _StepOutcome(error="join step requires dataset_id (classification) and table_id")
    join_key = str(step.parameters.get("join_key") or JOIN_KEY)
    series = str(step.parameters.get("series") or JOIN_SERIES)
    # A join resolves one period at a time; a plan naming two years wants both.
    periods = step.periods or (None,)

    values: list[dict[str, Any]] = []
    provenance: list[Provenance] = []
    warnings: list[str] = []
    for period in periods:
        try:
            result = join_classification_to_table(
                registry,
                klass_dataset_id=step.dataset_id,
                ssb_table=step.table_id,
                year=period,
                http=http,
                join_key=join_key,
                series=series,
            )
        except Exception as exc:
            return _StepOutcome(warnings=warnings, error=f"join failed: {exc}")
        if not result.rows:
            warnings.append(
                f"join produced no rows for period {period}; the classification and the "
                "table share a key but no cell matched"
            )
        for row in result.rows:
            values.append(
                {
                    "id": f"join:{join_key}:{row.get(join_key)}:{row.get('year')}",
                    "dataset_id": f"ssb:{step.table_id}",
                    "table_id": step.table_id,
                    "measure": row.get("population_measure") or "joined",
                    "value": row.get("population"),
                    # "region" is an entity alias the methods layer recognises,
                    # so the derived rows are keyed by the readable name while
                    # the code stays alongside as the join evidence.
                    "dimensions": {
                        "region": row.get("klass_name"),
                        join_key: row.get(join_key),
                        "year": row.get("year"),
                    },
                    "why_matched": row.get("why_matched"),
                }
            )
        provenance.append(
            Provenance(
                dataset_id=result.right_dataset_id,
                title=result.right_title,
                publisher=result.right_publisher,
                access_path=result.right_request_url,
                request_url=result.right_request_url,
                why=f"joined to {step.dataset_id} on exact {join_key}",
            )
        )
    return _StepOutcome(values=values, provenance=provenance, warnings=warnings)


def _run_derive(values: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], str | None]:
    """Compute YoY, period change, index and rank over what earlier steps produced.

    Rows that cannot be cleaned into a typed observation are dropped by
    `clean`, not guessed at, and a series with a single period yields nulls
    with a stated reason rather than a fabricated change.
    """

    from methods.clean import clean
    from methods.derive import derive

    try:
        cleaned = clean(values)
    except Exception as exc:
        return [], [], f"derive failed while cleaning inputs: {exc}"
    if not cleaned:
        return [], ["derive had no numeric rows to work from; no derived value emitted"], None

    rows = derive(cleaned)
    periods = {row.observation.period for row in rows}
    notes: list[str] = []
    if len(periods) < 2:
        notes.append(
            f"only one period ({', '.join(sorted(periods))}) was available, so change "
            "and growth are undefined; rank is still computed within the period"
        )
    derived = [
        {
            "id": f"derived:{row.observation.id}",
            "observation_id": row.observation.id,
            "dataset_id": row.observation.dataset_id,
            "entity": row.observation.entity,
            "period": row.observation.period,
            "measure": row.observation.measure,
            "value": row.observation.value,
            "derived": {
                "yoy_growth": row.yoy_growth.to_dict(),
                "period_change": row.period_change.to_dict(),
                "index": row.index.to_dict(),
                "rank": row.rank.to_dict(),
                "rank_change": row.rank_change.to_dict(),
            },
        }
        for row in rows
    ]
    return derived, notes, None


def _decode(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value
