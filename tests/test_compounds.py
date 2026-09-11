"""Splitting a Norwegian compound the catalogue never names anything with.

`oppdrettslaks` appears in no title, so a question using it reached nothing even
though the publisher wrote `laks`. The splitter recovers that, and every
condition on it exists because a looser version measured worse.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.harvest import harvest
from public_data_agent.registry import Registry
from public_data_agent.search import build_search_index, compound_splits, score_document, search
from public_data_agent.sources.fixture import FixtureSource

FIXTURES = Path(__file__).parent / "fixtures"


def _registry(tmp_path: Path, titles: dict[str, str], *, bulk: int = 60) -> Registry:
    """A registry with a realistic amount of filler.

    The frequency cap is a share of the catalogue, so in a three-row fixture
    every word looks common and nothing ever splits. The filler gives the ratio
    something to be a ratio of.
    """

    payloads = [json.loads((FIXTURES / "sparse.json").read_text(encoding="utf-8"))]
    registry = Registry(tmp_path / "registry.sqlite")
    harvest(registry, FixtureSource(payloads))
    for n, (dataset_id, title) in enumerate(titles.items()):
        registry.ensure_observation_dataset(
            dataset_id=dataset_id, title=title, publisher_name="t",
            access_path=f"https://data.ssb.no/api/v0/no/table/{n}", license=None,
        )
    for i in range(bulk):
        registry.ensure_observation_dataset(
            dataset_id=f"bulk:{i}", title=f"Data og statistikk nummer {i}",
            publisher_name="t", access_path=f"https://example.test/bulk/{i}", license=None,
        )
    registry.conn.commit()
    build_search_index(registry)
    return registry


def test_a_compound_splits_where_both_halves_are_published(tmp_path: Path) -> None:
    registry = _registry(tmp_path, {
        "a:1": "Matfisk. Salg av laks og ørret",
        "a:2": "Oppdrett av fisk i sjø",
    })
    try:
        assert compound_splits(registry, "oppdrettslaks") == ("oppdrett", "laks")
        assert "a:1" in [h.dataset_id for h in search(registry, "oppdrettslaks", limit=10)]
    finally:
        registry.close()


def test_a_word_the_catalogue_names_things_with_is_not_split(tmp_path: Path) -> None:
    # Without this, `eierskap` splits into `eier` and `skap`, and `barnehage`
    # into `barn` and `hage`. If the catalogue titles something `Barnehage`,
    # the exact match is the right match and there is nothing to take apart.
    registry = _registry(tmp_path, {
        "a:1": "Barnehage og barn i hage",
        "a:2": "Barn i Norge",
        "a:3": "Hage og grønt areal",
    })
    try:
        assert compound_splits(registry, "barnehage") == ()
    finally:
        registry.close()


def test_a_part_that_appears_everywhere_does_not_split(tmp_path: Path) -> None:
    # `datahotell` split into `data` and `hotell`, and because `data` is in 7.5%
    # of the real catalogue the right answer fell from rank 8 out of the top 20.
    registry = _registry(tmp_path, {"a:1": "Hotell og overnatting"}, bulk=400)
    try:
        assert compound_splits(registry, "datahotell") == ()
    finally:
        registry.close()


def test_matching_a_part_is_weaker_than_matching_the_word(tmp_path: Path) -> None:
    # A title that says the whole word must outrank one that says half of it,
    # in any field. When a title part outscored a description match on the word
    # itself, five single-word benchmark queries fell from rank 1 to rank 2.
    splits = {"oppdrettslaks": ("oppdrett", "laks")}
    whole = score_document(["oppdrettslaks"], {"description": ["oppdrettslaks"]}, splits=splits)
    part = score_document(["oppdrettslaks"], {"title": ["laks"]}, splits=splits)
    assert whole and part
    assert whole[0].weight > part[0].weight


def test_a_split_match_satisfies_its_own_requirement(tmp_path: Path) -> None:
    # A requirement is satisfied by the question's word, not the catalogue's.
    # Keying it on the stored token dropped exactly the rows the split found.
    registry = _registry(tmp_path, {
        "a:1": "Matfisk. Salg av laks og ørret",
        "a:2": "Oppdrett av fisk i sjø",
    })
    try:
        registry.ensure_observation_dataset(
            dataset_id="a:3", title="Salg av laks", publisher_name="t",
            access_path="https://data.ssb.no/api/v0/no/table/99", license=None,
        )
        registry.conn.commit()
        build_search_index(registry)
        found = [h.dataset_id for h in search(registry, "oppdrettslaks salg", limit=10)]
        assert "a:3" in found or "a:1" in found
    finally:
        registry.close()


def test_a_short_word_is_never_split(tmp_path: Path) -> None:
    registry = _registry(tmp_path, {"a:1": "Bolig og pris"})
    try:
        assert compound_splits(registry, "bolig") == ()
        assert compound_splits(registry, "laks") == ()
    finally:
        registry.close()
