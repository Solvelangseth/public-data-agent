from __future__ import annotations

from public_data_agent.executor import execute_plan
from public_data_agent.planner import PlanStep, QuestionPlan
from public_data_agent.registry import Registry


def _plan(*steps: PlanStep) -> QuestionPlan:
    return QuestionPlan("test", "test", "test", "test", [], list(steps))


def test_executor_refuses_transform_before_fetch(tmp_path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    result = execute_plan(registry, _plan(PlanStep("derive", "derive")))
    assert result.status == "failed"
    assert "before" in (result.error or "")
    assert result.numbers_retrieved is False
    registry.close()


def test_executor_without_fetch_is_explicitly_not_fetched(tmp_path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    result = execute_plan(registry, _plan(PlanStep("search", "search")))
    assert result.status == "not_fetched"
    assert result.values == []
    assert result.numbers_retrieved is False
    registry.close()
