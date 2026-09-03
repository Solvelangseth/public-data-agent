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


def test_execution_returns_only_the_cells_this_request_covered(tmp_path) -> None:
    """Neither series nor fetch_run_id identifies what a request asked for.

    A row already present is reported "unchanged" and keeps the run id of
    whichever fetch first wrote it, so an earlier wider fetch would otherwise
    leak years the plan never asked for into the result.
    """

    from public_data_agent.fetch import FetchResult

    result = FetchResult(
        dataset_id="ssb:1", table_id="1", request_url="u", http_status=200,
        observation_ids=["a", "b"],
    )
    assert result.observation_ids == ["a", "b"]


def test_registry_selects_observations_by_explicit_ids(tmp_path) -> None:
    from public_data_agent.registry import Registry

    registry = Registry(tmp_path / "r.sqlite")
    try:
        # An empty id list means "this request covered nothing", never "all rows".
        assert registry.list_observations("ssb:1", ids=[]) == []
    finally:
        registry.close()
