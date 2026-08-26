from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.benchmark import load_questions, run_benchmark, validate_questions
from public_data_agent.cli import main
from public_data_agent.harvest import harvest
from public_data_agent.registry import Registry
from public_data_agent.sources.fixture import FixtureSource

FIXTURES = Path(__file__).parent / "fixtures"
QUESTIONS = Path(__file__).parent / "benchmark_questions.json"
STRANDSONE_ID = "fixture:b2864e84-b474-31ae-97b1-8b94a71f5b0f"


def _registry(tmp_path: Path) -> Registry:
    payloads = [
        json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        for name in ("ssb-strandsone.json", "helsedata-ssb.json", "sparse.json")
    ]
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FixtureSource(payloads))
    return registry


def test_validate_rejects_an_id_that_is_not_in_the_registry(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    payload = load_questions(QUESTIONS)
    payload["questions"][0]["expected"][0]["dataset_id"] = "datanorge:does-not-exist"
    with pytest.raises(ValueError, match="missing dataset"):
        validate_questions(registry, payload)
    registry.close()


def test_fixture_benchmark_scores_title_and_keyword_gold(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    result = run_benchmark(registry, load_questions(QUESTIONS))
    by_id = {row["id"]: row for row in result["questions"]}
    assert by_id["fx-simple"]["recall_at_5"] == 1.0
    assert by_id["fx-simple"]["mrr"] == 1.0
    assert by_id["fx-simple"]["ranked"][0] == STRANDSONE_ID
    assert by_id["fx-synonym"]["recall_at_5"] == 1.0
    assert by_id["fx-hard"]["recall_at_5"] == 0.0
    assert by_id["fx-hard"]["mrr"] == 0.0
    registry.close()


def test_cli_benchmark_writes_json(tmp_path: Path, capsys) -> None:
    db = tmp_path / "registry.sqlite"
    out = tmp_path / "results.json"
    assert main(["ingest", "--source", "fixture", "--fixtures", str(FIXTURES), "--db", str(db), "--quiet"]) == 0
    capsys.readouterr()
    assert main(
        [
            "benchmark",
            "--db",
            str(db),
            "--questions",
            str(QUESTIONS),
            "--out",
            str(out),
            "--quiet",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["question_count"] == 3
    assert "recall_at_5" in payload["our_search"]
    assert json.loads(out.read_text(encoding="utf-8"))["question_count"] == 3
