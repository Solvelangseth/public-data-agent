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
