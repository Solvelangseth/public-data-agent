"""Matching a plural question to a singular title.

NVDB names a register with a bare noun -- "Bru", "Gjerde", "Rekkverk" -- and a
question asks about several of them. Without folding the register is unreachable
by the plural anyone would type.

The scope of the rule is the point, and it was arrived at by measurement rather
than by taste: folding every field, or every title, is linguistically right and
costs a question on both labelled sets by letting far more tables compete.
"""

from __future__ import annotations

import json
from pathlib import Path

from public_data_agent.harvest import harvest
from public_data_agent.registry import Registry
from public_data_agent.search import fold_inflection, score_document, search
from public_data_agent.sources.fixture import FixtureSource

FIXTURES = Path(__file__).parent / "fixtures"


def test_plural_endings_fold_and_singular_ones_do_not() -> None:
    # Bokmål and Nynorsk plural, and the definite plural, reach one form.
    assert fold_inflection("bruer") == "bru"
    assert fold_inflection("passasjerer") == fold_inflection("passasjerar") == "passasjer"
    assert fold_inflection("vegene") == "veg"
    # Singular endings are deliberately absent: folding "nasjonale" to
    # "nasjonal" and "prøver" to "prøve" cost a question on both sets.
    assert fold_inflection("nasjonale") == "nasjonale"
    assert fold_inflection("prøve") == "prøve"
    # A fold must leave a real stem behind, not a fragment.
    assert fold_inflection("er") == "er"
    assert fold_inflection("bane") == "bane"


def test_het_is_derivational_not_inflectional() -> None:
    # `leseferdighet` is already the base form; reading its "et" as a definite
    # ending produces "leseferdigh", which is not what any other form reaches.
    assert fold_inflection("leseferdighet") == "leseferdighet"
    assert fold_inflection("leseferdigheter") == "leseferdighet"
    assert fold_inflection("muligheter") == "mulighet"


def test_a_plural_query_matches_a_one_word_title() -> None:
    matches = score_document(["bruer"], {"title": ["bru"]})
    assert [m.field for m in matches] == ["title"]
    # The stored spelling comes back, never the folded form: a caller reading
    # why a result matched should see the word the resource publishes.
    assert matches[0].token == "bru"
    # And it is weaker evidence than the word itself.
    exact = score_document(["bru"], {"title": ["bru"]})
    assert matches[0].weight < exact[0].weight


def test_a_multi_word_title_does_not_fold() -> None:
    # This is what keeps `leiepriser` from matching every table that says
    # `leiepris`, which measured worse on both labelled sets.
    assert score_document(["leiepriser"], {"title": ["leiepris", "bolig"]}) == []
    assert score_document(["leiepris"], {"title": ["leiepris", "bolig"]}) != []


def test_only_the_title_folds() -> None:
    assert score_document(["bruer"], {"keyword": ["bru"]}) == []
    assert score_document(["bruer"], {"description": ["bru"]}) == []


def test_a_singular_title_is_reachable_by_its_plural_end_to_end(tmp_path: Path) -> None:
    payloads = [
        json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        for name in ("ssb-strandsone.json", "helsedata-ssb.json", "sparse.json")
    ]
    registry = Registry(tmp_path / "registry.sqlite")
    try:
        harvest(registry, FixtureSource(payloads))
        registry.ensure_observation_dataset(
            dataset_id="nvdb:60", title="Bru", publisher_name="Statens vegvesen",
            access_path="https://nvdbapiles.atlas.vegvesen.no/vegobjekter/60", license=None,
        )
        registry.conn.commit()
        assert "nvdb:60" in [hit.dataset_id for hit in search(registry, "bruer", limit=10)]
    finally:
        registry.close()
