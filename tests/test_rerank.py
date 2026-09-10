"""Reordering a shortlist with a model, and the ways that can go wrong.

The reranker is remote, optional, and answers about results rather than
producing them. What matters is that it cannot introduce a dataset, cannot lose
one, and cannot take the search down when it fails.
"""

from __future__ import annotations

import json
from pathlib import Path

from public_data_agent.harvest import harvest
from public_data_agent.registry import Registry
from public_data_agent.rerank import clean_order, rerank
from public_data_agent.retrieval import find
from public_data_agent.sources.fixture import FixtureSource

FIXTURES = Path(__file__).parent / "fixtures"


def _registry(tmp_path: Path) -> Registry:
    payloads = [
        json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        for name in ("ssb-strandsone.json", "helsedata-ssb.json", "sparse.json")
    ]
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FixtureSource(payloads))
    return registry


class _Reranker:
    name = "fake"

    def __init__(self, order: list[int] | None = None, *, fail: bool = False) -> None:
        self.result, self.fail, self.calls = order or [], fail, 0

    def order(self, query: str, titles: list[str]) -> list[int]:
        self.calls += 1
        if self.fail:
            raise RuntimeError("the reranker is down")
        return self.result


def test_clean_order_keeps_only_positions_that_exist() -> None:
    assert clean_order('{"order": [3, 1, 7]}', 20) == [3, 1, 7]
    # A position outside the list names no dataset. Guessing what the model
    # meant would be inventing a result, so it is dropped.
    assert clean_order({"order": [1, 99, 0, -3]}, 20) == [1]
    assert clean_order({"order": [2, 2, 3]}, 20) == [2, 3]
    assert clean_order({"order": [True, "4"]}, 20) == []
    assert clean_order(None, 20) == []
    assert clean_order("not json", 20) == []


def test_nothing_is_lost_and_nothing_is_added(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    try:
        ranked = ["a", "b", "c", "d"]
        for dataset_id in ranked:
            registry.ensure_observation_dataset(
                dataset_id=dataset_id, title=dataset_id.upper(),
                publisher_name="t", access_path=None, license=None,
            )
        registry.conn.commit()
        out = rerank(registry, _Reranker([4, 3]), "q", ranked)
        assert sorted(out) == sorted(ranked)
        # keep=1 holds the original head, then the model's choices follow.
        assert out == ["a", "d", "c", "b"]
    finally:
        registry.close()


def test_a_failing_reranker_returns_the_ranking_unchanged(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    try:
        ranked = ["a", "b", "c"]
        for dataset_id in ranked:
            registry.ensure_observation_dataset(
                dataset_id=dataset_id, title=dataset_id, publisher_name="t",
                access_path=None, license=None,
            )
        registry.conn.commit()
        assert rerank(registry, _Reranker(fail=True), "q", ranked) == ranked
        assert rerank(registry, _Reranker([]), "q", ranked) == ranked
    finally:
        registry.close()


def test_an_ordering_is_not_reused_for_a_different_shortlist(tmp_path: Path) -> None:
    # An ordering is positions, and positions mean nothing without the list they
    # were given. Reusing them against a changed shortlist would silently point
    # at different datasets.
    registry = _registry(tmp_path)
    try:
        for dataset_id in ("a", "b", "c"):
            registry.ensure_observation_dataset(
                dataset_id=dataset_id, title=dataset_id, publisher_name="t",
                access_path=None, license=None,
            )
        registry.conn.commit()
        reranker = _Reranker([2])
        rerank(registry, reranker, "q", ["a", "b"])
        rerank(registry, reranker, "q", ["a", "b"])
        assert reranker.calls == 1
        rerank(registry, reranker, "q", ["a", "c"])
        assert reranker.calls == 2
    finally:
        registry.close()


def test_no_reranker_means_nothing_changes(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    try:
        plain = find(registry, "strandsone", limit=5)
        assert not any("reordered" in step for step in plain.steps)
    finally:
        registry.close()


def test_the_reordering_is_reported(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    try:
        result = find(registry, "strandsone", limit=5, reranker=_Reranker([2, 1]))
        if len(result.observations) > 1:
            assert any("reordered" in step for step in result.steps)
    finally:
        registry.close()
