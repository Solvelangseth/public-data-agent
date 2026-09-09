"""The query rewriter, and what happens when it misbehaves.

A rewriter is optional and remote. It can return nonsense, return an answer
instead of search terms, or fail outright, and none of those may take the search
down with it or put a model's words where evidence belongs.
"""

from __future__ import annotations

import json
from pathlib import Path

from public_data_agent.harvest import harvest
from public_data_agent.registry import Registry
from public_data_agent.retrieval import find
from public_data_agent.rewrite import clean_terms, terms_for
from public_data_agent.sources.fixture import FixtureSource

FIXTURES = Path(__file__).parent / "fixtures"
STRANDSONE_ID = "fixture:b2864e84-b474-31ae-97b1-8b94a71f5b0f"


def _registry(tmp_path: Path) -> Registry:
    payloads = [
        json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        for name in ("ssb-strandsone.json", "helsedata-ssb.json", "sparse.json")
    ]
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FixtureSource(payloads))
    return registry


class _Rewriter:
    def __init__(self, terms: list[str] | None = None, *, fail: bool = False) -> None:
        self.result, self.fail, self.calls = terms or [], fail, 0

    def terms(self, query: str) -> list[str]:
        self.calls += 1
        if self.fail:
            raise RuntimeError("the rewriter is down")
        return self.result


def test_clean_terms_keeps_short_phrases_and_drops_everything_else() -> None:
    assert clean_terms('{"terms": ["konsumprisindeks", "prisutvikling"]}') == [
        "konsumprisindeks",
        "prisutvikling",
    ]
    # A model that answers the question instead of translating it contributes
    # nothing, rather than contributing a sentence as a search term.
    assert clean_terms({"terms": ["Prisene steg med 3,4 prosent i fjor ifølge SSB"]}) == []
    assert clean_terms(None) == []
    assert clean_terms("not json at all") == []
    assert clean_terms({"terms": ["a", "a", "b"]}) == ["a", "b"]


def test_terms_are_cached_so_a_repeated_question_costs_one_call(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    rewriter = _Rewriter(["strandsone"])
    try:
        assert terms_for(registry, rewriter, "kystlinje", model="m") == ["strandsone"]
        assert terms_for(registry, rewriter, "kystlinje", model="m") == ["strandsone"]
        assert rewriter.calls == 1
        # A different model is a different rewrite and must not read this cache.
        assert terms_for(registry, rewriter, "kystlinje", model="other") == ["strandsone"]
        assert rewriter.calls == 2
    finally:
        registry.close()


def test_a_question_that_gains_nothing_is_still_cached(tmp_path: Path) -> None:
    # Empty is a real answer. Treating it as a cache miss would pay for a call
    # every time such a question is asked.
    registry = _registry(tmp_path)
    rewriter = _Rewriter([])
    try:
        assert terms_for(registry, rewriter, "kystlinje", model="m") == []
        assert terms_for(registry, rewriter, "kystlinje", model="m") == []
        assert rewriter.calls == 1
        assert registry.get_query_rewrite("kystlinje", model="m") == []
        assert registry.get_query_rewrite("never asked", model="m") is None
    finally:
        registry.close()


def test_a_failing_rewriter_leaves_the_search_working(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    try:
        without = find(registry, "strandsone", limit=5)
        broken = find(registry, "strandsone", limit=5, rewriter=_Rewriter(fail=True))
        assert broken.observations == without.observations
        assert broken.catalogue == without.catalogue
    finally:
        registry.close()


def test_no_rewriter_means_nothing_changes(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    try:
        result = find(registry, "strandsone", limit=5)
        assert not any("catalogue's words" in step for step in result.steps)
    finally:
        registry.close()


def test_the_terms_searched_are_reported(tmp_path: Path) -> None:
    # A caller has to be able to see that the question it asked is not the
    # question that was searched for.
    registry = _registry(tmp_path)
    try:
        result = find(registry, "kystlinje", limit=5, rewriter=_Rewriter(["strandsone"]))
        assert any("strandsone" in step for step in result.steps)
        assert STRANDSONE_ID in result.observations + result.catalogue
    finally:
        registry.close()


def test_a_rewrite_never_invents_a_result(tmp_path: Path) -> None:
    # The model proposes search terms, not datasets. A term naming something the
    # registry does not hold must add nothing at all.
    registry = _registry(tmp_path)
    try:
        without = find(registry, "strandsone", limit=10)
        with_junk = find(
            registry, "strandsone", limit=10, rewriter=_Rewriter(["ssbtable:99999", "xyzzy"])
        )
        assert set(with_junk.observations) <= set(without.observations)
        assert set(with_junk.catalogue) <= set(without.catalogue)
    finally:
        registry.close()
