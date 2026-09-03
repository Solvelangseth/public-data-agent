from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.agent_loop import run_agent
from public_data_agent.harvest import harvest
from public_data_agent.pipeline import (
    CATALOGUE_ONLY,
    NOTHING_FOUND,
    READY,
    assess_readiness,
    stop_message,
)
from public_data_agent.registry import Registry
from public_data_agent.sources.fixture import FixtureSource

FIXTURES = Path(__file__).parent / "fixtures"
STRANDSONE_ID = "fixture:b2864e84-b474-31ae-97b1-8b94a71f5b0f"
SSB_TABLE_URL = "https://data.ssb.no/api/v0/no/table/11763"


def _registry(tmp_path: Path) -> Registry:
    payloads = [
        json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        for name in ("ssb-strandsone.json", "helsedata-ssb.json", "sparse.json")
    ]
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FixtureSource(payloads))
    return registry


def test_gate_stops_when_nothing_matches(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    try:
        readiness = assess_readiness(registry, "kvantekryptografi på Jupiter")
    finally:
        registry.close()
    assert readiness.ready is False
    assert readiness.outcome == NOTHING_FOUND
    assert readiness.observation_sources == []
    # A gate never produces a number, whatever it decides.
    assert readiness.numbers_retrieved is False


def test_gate_stops_when_matches_describe_data_we_cannot_fetch(tmp_path: Path) -> None:
    """A relevant catalogue record is not the same as a retrievable one."""

    registry = _registry(tmp_path)
    registry.conn.execute(
        "UPDATE datasets SET access_path = ? WHERE id = ?",
        ("https://example.invalid/landing-page", STRANDSONE_ID),
    )
    registry.conn.commit()
    try:
        readiness = assess_readiness(registry, "strandsone")
    finally:
        registry.close()
    assert readiness.ready is False
    assert readiness.outcome == CATALOGUE_ONLY
    assert readiness.catalogue_records, "the near misses must still be reported"
    assert readiness.observation_sources == []


def test_gate_continues_when_a_registered_connector_can_answer(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.conn.execute(
        "UPDATE datasets SET access_path = ?, title = ? WHERE id = ?",
        (SSB_TABLE_URL, "Folkemengde i strandsone", STRANDSONE_ID),
    )
    registry.conn.commit()
    try:
        readiness = assess_readiness(registry, "strandsone")
    finally:
        registry.close()
    assert readiness.ready is True
    assert readiness.outcome == READY
    assert readiness.observation_sources[0].dataset_id == STRANDSONE_ID
    assert readiness.observation_sources[0].capability == "observations"


def test_gate_reports_uncovered_terms_without_refusing_on_them(tmp_path: Path) -> None:
    """A term search cannot match may still be a dimension value we can select."""

    registry = _registry(tmp_path)
    registry.conn.execute(
        "UPDATE datasets SET access_path = ?, title = ? WHERE id = ?",
        (SSB_TABLE_URL, "Folkemengde i strandsone", STRANDSONE_ID),
    )
    registry.conn.commit()
    try:
        readiness = assess_readiness(registry, "strandsone i Vestvågøy")
    finally:
        registry.close()
    # The extra term is not stored anywhere, but the question stays answerable.
    assert "vestvågøy" in [term.casefold() for term in readiness.uncovered_terms]
    assert readiness.ready is True
    assert "vestvågøy" in readiness.reason.casefold()


def test_stop_message_states_no_numbers_and_names_the_near_misses(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.conn.execute(
        "UPDATE datasets SET access_path = ? WHERE id = ?",
        ("https://example.invalid/landing-page", STRANDSONE_ID),
    )
    registry.conn.commit()
    try:
        readiness = assess_readiness(registry, "strandsone")
    finally:
        registry.close()
    message = stop_message(readiness)
    assert "Ingen tall ble hentet" in message
    assert STRANDSONE_ID in message
    # It must not speculate about what the answer would have been.
    assert "sannsynlig" not in message.casefold()


def test_stop_message_refuses_to_render_for_an_answerable_question(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.conn.execute(
        "UPDATE datasets SET access_path = ? WHERE id = ?", (SSB_TABLE_URL, STRANDSONE_ID)
    )
    registry.conn.commit()
    try:
        readiness = assess_readiness(registry, "strandsone")
    finally:
        registry.close()
    with pytest.raises(ValueError):
        stop_message(readiness)


def test_agent_stops_before_any_model_call_when_the_gate_refuses(tmp_path: Path) -> None:
    """The point of the gate: an unanswerable question costs zero model calls."""

    registry = _registry(tmp_path)
    registry.conn.execute(
        "UPDATE datasets SET access_path = ? WHERE id = ?",
        ("https://example.invalid/landing-page", STRANDSONE_ID),
    )
    registry.conn.commit()
    db = str(tmp_path / "registry.sqlite")
    registry.close()

    class ExplodingModel:
        def next_action(self, messages, tools):  # pragma: no cover - must never run
            raise AssertionError("the model was called for an unanswerable question")

    result = run_agent("strandsone", ExplodingModel(), db=db)
    assert result.tool_calls == 0
    assert result.error is None
    assert "Ingen tall ble hentet" in result.final
    assert result.readiness["ready"] is False
    assert result.readiness["numbers_retrieved"] is False


def test_agent_proceeds_past_the_gate_when_a_source_can_answer(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.conn.execute(
        "UPDATE datasets SET access_path = ?, title = ? WHERE id = ?",
        (SSB_TABLE_URL, "Folkemengde i strandsone", STRANDSONE_ID),
    )
    registry.conn.commit()
    db = str(tmp_path / "registry.sqlite")
    registry.close()

    class Model:
        def next_action(self, messages, tools):
            return {"final": "reached the model"}

    result = run_agent("strandsone", Model(), db=db)
    assert result.final == "reached the model"


def test_gate_can_be_disabled_without_changing_tool_behaviour(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    db = str(tmp_path / "registry.sqlite")
    registry.close()

    class Model:
        def next_action(self, messages, tools):
            return {"final": "ran anyway"}

    result = run_agent("kvantekryptografi på Jupiter", Model(), db=db, gate=False)
    assert result.final == "ran anyway"
    assert result.readiness is None


def test_intake_and_gate_compose_into_one_verdict(tmp_path: Path) -> None:
    from public_data_agent.pipeline import run_intake

    registry = _registry(tmp_path)
    registry.conn.execute(
        "UPDATE datasets SET access_path = ?, title = ? WHERE id = ?",
        (SSB_TABLE_URL, "Folkemengde i strandsone", STRANDSONE_ID),
    )
    registry.conn.commit()
    try:
        out = run_intake(registry, "Hvilken strandsone er størst?")
    finally:
        registry.close()
    # Question words never reach search as requirements.
    assert "hvilken" not in out.request.search_terms
    assert out.readiness.ready is True
    assert out.proceed is True
    assert out.to_dict()["numbers_retrieved"] is False


def test_a_question_needing_clarification_does_not_proceed(tmp_path: Path) -> None:
    """Misreading a question is not evidence that the data is missing."""

    from public_data_agent.intake import validate_intake
    from public_data_agent.pipeline import run_intake

    class VagueProvider:
        def read_question(self, question):
            return {
                "search_terms": ["strandsone"],
                "clarifying_question": "Hvilken strandsone mener du?",
            }

    registry = _registry(tmp_path)
    registry.conn.execute(
        "UPDATE datasets SET access_path = ? WHERE id = ?", (SSB_TABLE_URL, STRANDSONE_ID)
    )
    registry.conn.commit()
    try:
        out = run_intake(registry, "strandsone", provider=VagueProvider())
    finally:
        registry.close()
    assert out.request.needs_clarification is True
    # Answerable, but we stop anyway until the question is settled.
    assert out.readiness.ready is True
    assert out.proceed is False


def _ready_registry(tmp_path: Path) -> tuple[Registry, str]:
    registry = _registry(tmp_path)
    registry.conn.execute(
        "UPDATE datasets SET access_path = ?, title = ? WHERE id = ?",
        (SSB_TABLE_URL, "Folkemengde i strandsone", STRANDSONE_ID),
    )
    registry.conn.commit()
    return registry, str(tmp_path / "registry.sqlite")


def test_router_puts_clarification_before_the_gate_verdict(tmp_path: Path) -> None:
    """A misread question is not evidence that data is missing."""

    from public_data_agent.pipeline import ROUTE_CLARIFY, ROUTE_SPECIFIC, route, run_intake

    class Vague:
        def read_question(self, question):
            return {"search_terms": ["strandsone"], "clarifying_question": "Hvilken?"}

    registry, _ = _ready_registry(tmp_path)
    try:
        assert route(run_intake(registry, "strandsone", provider=Vague())) == ROUTE_CLARIFY
        assert route(run_intake(registry, "strandsone")) == ROUTE_SPECIFIC
    finally:
        registry.close()


def test_router_sends_open_investigation_to_the_exploratory_path(tmp_path: Path) -> None:
    from public_data_agent.pipeline import ROUTE_EXPLORATORY, route, run_intake

    class Open:
        def read_question(self, question):
            return {"search_terms": ["strandsone"], "shape": "exploratory"}

    registry, _ = _ready_registry(tmp_path)
    try:
        assert route(run_intake(registry, "strandsone", provider=Open())) == ROUTE_EXPLORATORY
    finally:
        registry.close()


def test_router_stops_before_either_answering_path_when_nothing_can_answer(tmp_path: Path) -> None:
    from public_data_agent.pipeline import ROUTE_STOP, route, run_intake

    registry = _registry(tmp_path)
    try:
        assert route(run_intake(registry, "kvantekryptografi på Jupiter")) == ROUTE_STOP
    finally:
        registry.close()


def test_planner_may_only_choose_sources_that_can_return_observations(tmp_path: Path) -> None:
    """A planner handed a landing page will eventually try to fetch it."""

    from public_data_agent.pipeline import plan_candidates, run_intake

    registry, _ = _ready_registry(tmp_path)
    try:
        candidates = plan_candidates(run_intake(registry, "strandsone").readiness)
    finally:
        registry.close()
    assert candidates
    assert all(item["capability"] == "observations" for item in candidates)
    # The table id is read off the stored path, never guessed from a title.
    assert candidates[0]["table_id"] == "11763"


def test_specific_route_refuses_to_run_without_a_plan_provider(tmp_path: Path) -> None:
    from public_data_agent.pipeline import ROUTE_SPECIFIC, run_pipeline

    registry, db = _ready_registry(tmp_path)
    try:
        result = run_pipeline(registry, "strandsone", db=db)
    finally:
        registry.close()
    assert result.route == ROUTE_SPECIFIC
    assert "plan provider" in (result.error or "")
    # Never fall through to a different path to produce something.
    assert result.final is None
    assert result.numbers_retrieved is False


def test_pipeline_stop_route_answers_without_any_provider(tmp_path: Path) -> None:
    from public_data_agent.pipeline import ROUTE_STOP, run_pipeline

    registry = _registry(tmp_path)
    db = str(tmp_path / "registry.sqlite")
    try:
        result = run_pipeline(registry, "kvantekryptografi på Jupiter", db=db)
    finally:
        registry.close()
    assert result.route == ROUTE_STOP
    assert "Ingen tall ble hentet" in (result.final or "")
    assert result.numbers_retrieved is False


def test_pipeline_reports_a_rejected_plan_without_executing_it(tmp_path: Path) -> None:
    from public_data_agent.pipeline import run_pipeline

    class AnsweringPlanner:
        def make_plan(self, question, candidates):
            # A plan carrying a factual field must never reach the executor.
            return {"steps": [{"kind": "fetch"}], "answer": "64 920"}

    registry, db = _ready_registry(tmp_path)
    try:
        result = run_pipeline(registry, "strandsone", db=db, plan_provider=AnsweringPlanner())
    finally:
        registry.close()
    assert result.execution is None
    assert result.error
    assert result.numbers_retrieved is False
