"""Nynorsk and Bokmål spellings of the same word.

SSB writes each table in whichever written norm its authors used, so the
catalogue holds `Overnattingar` in 24 titles and `Overnattinger` in 4. A
question using one spelling could not see the tables using the other.

The rule is a swap between endings, never a removal, and that is what keeps it
safe: removing `-er` turns `leiepriser` into `leiepris` and lets every rent
table compete, which measured worse on both labelled sets. Swapping it produces
`leieprisar`, which nothing publishes, so it matches nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

from public_data_agent.harvest import harvest
from public_data_agent.registry import Registry
from public_data_agent.search import search, spelling_variants
from public_data_agent.sources.fixture import FixtureSource

FIXTURES = Path(__file__).parent / "fixtures"


def test_both_norms_reach_the_same_word() -> None:
    assert set(spelling_variants("passasjerer")) == {"passasjerer", "passasjerar"}
    assert set(spelling_variants("passasjerar")) == {"passasjerar", "passasjerer"}
    assert set(spelling_variants("gjestene")) == {"gjestene", "gjestane"}
    assert set(spelling_variants("offentleg")) == {"offentleg", "offentlig"}
    assert set(spelling_variants("løpande")) == {"løpande", "løpende"}


def test_a_swap_never_reaches_a_bare_stem() -> None:
    # This is the whole safety argument. `leiepriser` may equate with
    # `leieprisar`, which nothing publishes, but never with `leiepris`, which
    # many tables publish and which cost a question when folding produced it.
    assert "leiepris" not in spelling_variants("leiepriser")
    assert "bru" not in spelling_variants("bruer")


def test_a_short_word_is_left_alone() -> None:
    # "Sande" is a municipality. Without a minimum stem it would swap to
    # "sende", and a question about the place would match the verb.
    assert spelling_variants("sande") == ("sande",)
    assert spelling_variants("ar") == ("ar",)


def test_a_word_with_no_variant_is_unchanged() -> None:
    assert spelling_variants("bolig") == ("bolig",)
    assert spelling_variants("bru") == ("bru",)


def test_a_bokmal_query_finds_a_nynorsk_title(tmp_path: Path) -> None:
    payloads = [
        json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        for name in ("ssb-strandsone.json", "helsedata-ssb.json", "sparse.json")
    ]
    registry = Registry(tmp_path / "registry.sqlite")
    try:
        harvest(registry, FixtureSource(payloads))
        registry.ensure_observation_dataset(
            dataset_id="ssbtable:14178",
            title="Overnattingar, etter innkvarteringstype og gjestene sitt bustadland",
            publisher_name="Statistisk sentralbyrå",
            access_path="https://data.ssb.no/api/v0/no/table/14178",
            license=None,
        )
        registry.conn.commit()
        found = [hit.dataset_id for hit in search(registry, "overnattinger", limit=10)]
        assert "ssbtable:14178" in found
        # And the other direction, which is the same rule read backwards.
        assert "ssbtable:14178" in [
            hit.dataset_id for hit in search(registry, "overnattingar", limit=10)
        ]
    finally:
        registry.close()


def test_the_published_spelling_is_what_is_reported(tmp_path: Path) -> None:
    # A caller reading why a result matched should see the word the resource
    # publishes, not the spelling the question happened to use.
    payloads = [json.loads((FIXTURES / "sparse.json").read_text(encoding="utf-8"))]
    registry = Registry(tmp_path / "registry.sqlite")
    try:
        harvest(registry, FixtureSource(payloads))
        registry.ensure_observation_dataset(
            dataset_id="ssbtable:14178", title="Overnattingar etter innkvarteringstype",
            publisher_name="SSB", access_path="https://data.ssb.no/api/v0/no/table/14178",
            license=None,
        )
        registry.conn.commit()
        hit = next(h for h in search(registry, "overnattinger", limit=10)
                   if h.dataset_id == "ssbtable:14178")
        assert any(m.token == "overnattingar" for m in hit.matches)
    finally:
        registry.close()
