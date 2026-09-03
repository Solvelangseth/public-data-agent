from __future__ import annotations

import json
from pathlib import Path

from public_data_agent.ask import DEMO_QUESTION, ask
from public_data_agent.cli import main
from public_data_agent.harvest import harvest
from public_data_agent.registry import Registry
from public_data_agent.sources.fixture import FixtureSource
from public_data_agent.planner import build_plan
from public_data_agent.search import search_report

FIXTURES = Path(__file__).parent / "fixtures"


def _registry(tmp_path: Path) -> Registry:
    payloads = [json.loads((FIXTURES / "ssb-strandsone.json").read_text(encoding="utf-8"))]
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FixtureSource(payloads))
    return registry


def test_non_demo_question_returns_ranked_hits_without_unplanned_numbers(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    result = ask(registry, "Hvilke strandsone-data finnes?", search_limit=5)
    assert result.plan is not None
    assert result.plan.intent == "catalog_search_and_optional_fetch"
    assert result.execution["status"] == "not_fetched"
    assert result.answer["numbers_retrieved"] is False
    assert result.answer["observations"] == []
    assert "no numbers were retrieved" in result.answer["explanation"]
    registry.close()


def test_demo_plan_contains_search_fetch_join_and_derived_steps(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.conn.execute(
        "UPDATE datasets SET access_path = ?, title = ? WHERE id = ?",
        (
            "https://data.ssb.no/api/klass/v1/versions/1168.json",
            "Bydelsinndeling Oslo",
            "fixture:b2864e84-b474-31ae-97b1-8b94a71f5b0f",
        ),
    )
    registry.conn.commit()
    report = search_report(registry, DEMO_QUESTION, limit=5)
    plan = build_plan(
        DEMO_QUESTION,
        report,
        klass_dataset_id="fixture:b2864e84-b474-31ae-97b1-8b94a71f5b0f",
        ssb_table="11763",
        latest_year=2025,
        prior_year=2024,
        registry=registry,
    )
    assert [step.kind for step in plan.steps] == ["search", "fetch", "fetch", "join", "derive"]
    registry.close()


def test_plain_norwegian_population_prompt_selects_registered_sources(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.conn.execute(
        "UPDATE datasets SET access_path = ? WHERE id = ?",
        ("https://data.ssb.no/api/klass/v1/versions/1168.json", "fixture:b2864e84-b474-31ae-97b1-8b94a71f5b0f"),
    )
    registry.conn.commit()
    question = "Finn folkemengde i Oslo-bydeler, sammenlign de to siste årene og ranger de som vokser mest"
    plan = build_plan(
        question,
        search_report(registry, question, limit=5),
        klass_dataset_id="fixture:b2864e84-b474-31ae-97b1-8b94a71f5b0f",
        ssb_table="11763",
        latest_year=2025,
        prior_year=2024,
        registry=registry,
    )
    assert plan.intent == "bydel_population_size_and_growth"
    assert plan.steps[1].dataset_id == "fixture:b2864e84-b474-31ae-97b1-8b94a71f5b0f"
    assert plan.steps[2].dataset_id == "ssb:11763"
    assert plan.refusal_reason is None
    registry.close()


def test_plan_command_is_dry_run_and_writes_structured_plan(tmp_path: Path, capsys) -> None:
    registry = _registry(tmp_path)
    db = tmp_path / "registry.sqlite"
    registry.close()

    assert main(["plan", DEMO_QUESTION, "--db", str(db)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [step["kind"] for step in payload["plan"]["steps"]] == ["search"]
    assert payload["execution"]["status"] == "not_executed"
    assert payload["execution"]["numbers_retrieved"] is False
    assert "no fetch" in payload["execution"]["explanation"]
