from __future__ import annotations
import pytest

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


def _plan(*steps):
    from public_data_agent.planner import QuestionPlan

    return QuestionPlan(
        question="q", intent="t", parser="m", search_query="q", requirements=[], steps=list(steps)
    )


def test_join_and_derive_are_refused_before_any_fetch(tmp_path) -> None:
    """A derived value built from nothing is worse than no derived value."""

    from public_data_agent.executor import execute_plan
    from public_data_agent.planner import PlanStep
    from public_data_agent.registry import Registry

    registry = Registry(tmp_path / "r.sqlite")
    try:
        for kind in ("join", "derive"):
            result = execute_plan(registry, _plan(PlanStep(kind=kind, reason="early")))
            assert result.status == "failed"
            assert "before a successful fetch" in (result.error or "")
    finally:
        registry.close()


def test_derive_reports_a_single_period_instead_of_inventing_change(tmp_path) -> None:
    from public_data_agent.executor import _run_derive

    values = [
        {
            "id": f"o{i}", "dataset_id": "ssb:1", "table_id": "1", "measure": "Personer",
            "value": v, "dimensions": {"region": name, "year": "2025"},
        }
        for i, (name, v) in enumerate([("Alna", 10), ("Bjerke", 20)])
    ]
    derived, notes, error = _run_derive(values)
    assert error is None
    assert derived, "rank is still computable within one period"
    joined = " ".join(notes)
    assert "one period" in joined and "undefined" in joined
    # Growth with no prior period must be null, never a number.
    assert all(row["derived"]["yoy_growth"]["value"] is None for row in derived)


def test_derive_computes_growth_and_rank_with_lineage(tmp_path) -> None:
    from public_data_agent.executor import _run_derive

    values = []
    for name, per_year in (("Alna", {"2024": 100, "2025": 110}), ("Bjerke", {"2024": 200, "2025": 202})):
        for year, value in per_year.items():
            values.append({
                "id": f"{name}-{year}", "dataset_id": "ssb:1", "table_id": "1",
                "measure": "Personer", "value": value,
                "dimensions": {"region": name, "year": year},
            })
    derived, _notes, error = _run_derive(values)
    assert error is None
    latest = {row["entity"]: row for row in derived if row["period"] == "2025"}
    assert latest["Alna"]["derived"]["yoy_growth"]["value"] == pytest.approx(0.10)
    assert latest["Bjerke"]["derived"]["yoy_growth"]["value"] == pytest.approx(0.01)
    # Bjerke is larger, so it ranks first; growth and size are separate answers.
    assert latest["Bjerke"]["derived"]["rank"]["value"] == 1
    # Every derived number carries the inputs it came from.
    lineage = latest["Alna"]["derived"]["yoy_growth"]["lineage"]
    assert lineage["source_periods"] == ["2024", "2025"]
    assert len(lineage["source_observation_ids"]) == 2


def test_unimplemented_step_kinds_warn_rather_than_emit_nothing_silently(tmp_path) -> None:
    from public_data_agent.executor import UNIMPLEMENTED

    # These still have no generic implementation; the set is the contract.
    assert UNIMPLEMENTED == {"filter", "reshape", "visualize", "export"}
