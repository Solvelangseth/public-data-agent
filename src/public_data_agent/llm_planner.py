"""Provider boundary for LLM-generated plans.

Providers may interpret language, but their output is accepted only after the
same structural and registry-candidate checks used by the executor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from public_data_agent.planner import PlanStep, QuestionPlan
from public_data_agent.search import SearchReport


class PlanProvider(Protocol):
    def make_plan(self, question: str, candidates: list[dict[str, Any]]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class PlanValidation:
    plan: QuestionPlan | None
    error: str | None = None


def candidate_context(report: SearchReport, *, limit: int = 10) -> list[dict[str, Any]]:
    """Create the bounded, factual context supplied to a planning provider."""
    return [
        {
            "dataset_id": hit.dataset_id,
            "title": hit.title,
            "publisher": hit.publisher,
            "license": hit.license,
            "access_path": hit.access_path,
            "table_id": _table_id(hit.access_path),
            "why": hit.why,
        }
        for hit in report.hits[:limit]
    ]


def _table_id(access_path: str | None) -> str | None:
    if not access_path:
        return None
    return access_path.rstrip("/").rsplit("/", 1)[-1] or None


def validate_model_plan(
    payload: dict[str, Any],
    *,
    question: str,
    candidate_dataset_ids: set[str],
    candidate_table_ids: set[str] | None = None,
) -> PlanValidation:
    """Validate model JSON without accepting factual answer content."""
    if not isinstance(payload, dict):
        return PlanValidation(None, "model plan must be an object")
    forbidden = {"answer", "values", "observations", "population", "yoy", "license"}
    if forbidden.intersection(payload):
        return PlanValidation(None, "model plan contains factual output fields")
    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        return PlanValidation(None, "model plan must contain a non-empty steps list")
    candidate_table_ids = candidate_table_ids or set()
    steps: list[PlanStep] = []
    for raw in raw_steps:
        if not isinstance(raw, dict) or not isinstance(raw.get("kind"), str):
            return PlanValidation(None, "each plan step needs a kind")
        dataset_id = raw.get("dataset_id")
        if dataset_id is not None and dataset_id not in candidate_dataset_ids:
            return PlanValidation(None, f"model selected dataset outside candidates: {dataset_id}")
        table_id = raw.get("table_id")
        if table_id is not None and candidate_table_ids and str(table_id) not in candidate_table_ids:
            return PlanValidation(None, f"model selected table outside candidates: {table_id}")
        periods = raw.get("periods", ())
        if not isinstance(periods, (list, tuple)) or any(not isinstance(p, int) for p in periods):
            return PlanValidation(None, "plan periods must be integers")
        steps.append(
            PlanStep(
                kind=raw["kind"],
                reason=str(raw.get("reason", "model-selected operation")),
                dataset_id=dataset_id,
                table_id=table_id,
                periods=tuple(periods),
            )
        )
    requirements = payload.get("requirements", [])
    if not isinstance(requirements, list) or any(not isinstance(item, str) for item in requirements):
        return PlanValidation(None, "plan requirements must be strings")
    return PlanValidation(
        QuestionPlan(
            question=question,
            intent=str(payload.get("intent", "model_intent")),
            parser="llm_structured_plan",
            search_query=str(payload.get("search_query", question)),
            requirements=requirements,
            steps=steps,
            refusal_reason=payload.get("refusal_reason"),
        )
    )


def plan_with_provider(
    provider: PlanProvider,
    *,
    question: str,
    candidates: list[dict[str, Any]],
) -> PlanValidation:
    """Ask a provider for JSON and validate it before execution."""
    payload = provider.make_plan(question, candidates)
    return validate_model_plan(
        payload,
        question=question,
        candidate_dataset_ids={str(item["dataset_id"]) for item in candidates if item.get("dataset_id")},
        candidate_table_ids={str(item["table_id"]) for item in candidates if item.get("table_id")},
    )
