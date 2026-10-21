"""One entry point for finding data that can answer a question.

Everything here is a measured choice against `data/fetchable_gold.json`, whose
labels say which table actually answers each of 100 questions (88 plus 12
added 2026-09-14 for dairy, nature-protection areas, Oslo statbank, and
Norges Bank). The progression below is the original 88, recall@5 then MRR:

    lexical alone            0.442   0.327
    + semantic ranking       0.709   0.577
    + routing by phrasing    0.779   0.622
    + subject over breakdown 0.791   0.627
    + observations lane      0.860   0.763

A coverage lift on top of that measured 0.802/0.676 and was removed.

The steps are kept separate so each can be re-measured, and so a caller without
an embedding provider still gets the lexical half rather than nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from public_data_agent.embeddings import rank_for_query, semantic_ranking
from public_data_agent.fetch import classify_access_path, is_retrievable
from public_data_agent.registry import Registry
from public_data_agent.resource_index import demote_breakdown_only
from public_data_agent.rerank import RERANK_KEEP, RERANK_LIFT, Reranker, rerank
from public_data_agent.rewrite import QueryRewriter, terms_for
from public_data_agent.search import search_report

DEPTH = 50
# How many of a rewritten term's results are interleaved, and how far down the
# main ranking they go. Fusing the two instead measured 0.802 against 0.860:
# a rewrite is a second opinion about the subject, not a second vote on a
# ranking, and RRF treats it as the latter.
REWRITE_LEAD = 3
# How far into a rewritten term's own ranking to look. Ten is what was measured;
# the terms are alternatives, so this is per term rather than in total.
REWRITE_DEPTH = 10


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


@dataclass
class Retrieved:
    """A ranking, and how it was produced."""

    query: str
    observations: list[str] = field(default_factory=list)
    catalogue: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    # Query terms no retrieved record stores. Reported, never used to refuse:
    # the index holds titles and field values, so a term absent from it may
    # still be a dimension value inside a matched table.
    uncovered: list[str] = field(default_factory=list)
    # Lexical scores where a result had one. A result found only by embedding
    # has none, and inventing a number for it would misreport how it was found.
    relevance: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "observations": self.observations,
            "catalogue": self.catalogue,
            "steps": self.steps,
            "uncovered": self.uncovered,
        }


def _capability(registry: Registry, dataset_id: str, cache: dict[str, str]) -> str:
    """What this resource can return, preferring what was verified over what a
    URL looks like.

    `classify_access_path` reads a pattern; `resource_capability` records what a
    fetch actually returned. Where they disagree the record wins. A register's
    stored access path is its collection endpoint, which the classifier rightly
    calls unfetchable -- a million companies is not one request -- while the
    resource is reachable by naming a subject. Classifying from the URL alone
    hid Enhetsregisteret from every query, including the literal word
    "Enhetsregisteret".
    """

    if dataset_id not in cache:
        recorded = (registry.get_capability(dataset_id) or {}).get("capability")
        if recorded:
            cache[dataset_id] = recorded
        else:
            row = registry.get_dataset(dataset_id) or {}
            cache[dataset_id] = classify_access_path(row.get("access_path"))["kind"]
    return cache[dataset_id]


def find(
    registry: Registry,
    query: str,
    *,
    provider: EmbeddingProvider | None = None,
    limit: int = 10,
    depth: int = DEPTH,
    rewriter: QueryRewriter | None = None,
    rewrite_model: str | None = None,
    reranker: Reranker | None = None,
    rerank_keep: int = RERANK_KEEP,
    rerank_lift: int = RERANK_LIFT,
    rewrite_lead: int = REWRITE_LEAD,
    rewrite_take: int | None = None,
) -> Retrieved:
    """Rank what could answer a question, fetchable results kept apart.

    Without a provider this is lexical only, which is worth stating plainly:
    lexical alone finds the right table for 23% of naturally phrased questions
    against 81% for the full stack. A provider is not an optimisation.
    """

    steps: list[str] = []
    report = search_report(registry, query, limit=depth)
    lexical = [hit.dataset_id for hit in report.hits]
    relevance = {hit.dataset_id: hit.relevance for hit in report.hits}
    steps.append(f"lexical search returned {len(lexical)}")

    def rank(text: str) -> list[str]:
        hits = [hit.dataset_id for hit in search_report(registry, text, limit=depth).hits]
        if provider is None:
            return hits
        semantic = [d for d, _ in semantic_ranking(registry, provider, text, limit=depth)]
        return rank_for_query(hits, semantic, text, limit=depth)

    if provider is None:
        ranked = lexical
        steps.append("no embedding provider; semantic ranking skipped")
    else:
        semantic = [d for d, _ in semantic_ranking(registry, provider, query, limit=depth)]
        ranked = rank_for_query(lexical, semantic, query, limit=depth)
        steps.append(
            "ranked semantically alone (query reads as a question)"
            if ranked == semantic[:depth]
            else "fused lexical and semantic (query names a subject)"
        )

    if rewriter is not None:
        # Each term is searched on its own. They are alternative names for the
        # subject, not a conjunction, so one bad term must not exclude the rest.
        terms = terms_for(registry, rewriter, query, model=rewrite_model)
        alternative: list[str] = []
        for term in terms:
            alternative.extend(rank(term)[:REWRITE_DEPTH])
        alternative = list(dict.fromkeys(alternative))
        if alternative:
            # Interleaved rather than merged: the head of the original ranking
            # is kept, the rewrite's best few go directly behind it, and the
            # rest of the original follows. Deduplication keeps the earlier
            # position, so a result both agree on is not pushed down.
            #
            # How much of the head to keep and how many rewrite hits to insert
            # were one number doing two jobs. They are separate because they
            # answer different questions, and because the second one is where
            # `regnskapstall aksjeselskap` is lost: the rewrite lane ranks
            # 07371 sixth and three were being taken.
            take = rewrite_take if rewrite_take is not None else rewrite_lead
            ranked = list(
                dict.fromkeys(
                    ranked[:rewrite_lead] + alternative[:take] + ranked
                )
            )[:depth]
        steps.append(
            f"searched the catalogue's words for this question: {', '.join(terms)}"
            if terms
            else "query rewriter proposed no terms; ranking unchanged"
        )

    reordered = demote_breakdown_only(registry, ranked, query)
    if reordered != ranked:
        steps.append("demoted tables split by a query word below tables about it")
    ranked = reordered

    # A coverage lift was tried here and measured worse: recall@5 0.802 against
    # 0.860, MRR 0.676 against 0.763, engaging on 28 of 86 questions and adding
    # six misses. With a complete index a common word like "norge" is a value in
    # hundreds of resources, so lifting everything that holds one scrambles a
    # good ranking. `rank_within_coverage` is kept for a caller that wants a
    # coverage filter, which is a different question from relevance.
    #
    # Tried again 2026-09-23, this time interleaving `search_resources` (which
    # weights a value by how few resources carry it) rather than lifting every
    # coverer, since 6 of the 10 remaining tuned misses do record the query's
    # rare word as a value. Measured worse again. Embeddings only, tuned set:
    # recall@5 0.867 at every lead of 1-3, against 0.867, and MRR 0.741 -> 0.692.
    # Full stack, placing the hits below the head at position 5 or 8 so they
    # cannot displace a good answer and the reranker still sees them: recall@5
    # 0.898 unchanged in both, MRR 0.769 -> 0.756 and 0.761, one question gained
    # (bruttonasjonalprodukt, absent -> 3) and one lost (Oslo bydeler, 5 -> 7).
    # A value match says a resource *holds* the thing, which does not order
    # resources by how well they answer; that is what the title lane already
    # measures. The value index stays where it pays, in `search_resources` and
    # the coverage filter.

    cache: dict[str, str] = {}
    observations = [d for d in ranked if is_retrievable(_capability(registry, d, cache))]
    # A record that cannot return data does not belong in the lane whose job is
    # returning it; it belongs in the other one, where saying "this exists but I
    # cannot retrieve it" is a real answer. The test is whether anything can be
    # fetched, not whether it happens to be a statistic -- a company or a
    # building answers a question just as a table does.
    catalogue = [d for d in ranked if not is_retrievable(_capability(registry, d, cache))]
    steps.append(f"split into {len(observations)} fetchable and {len(catalogue)} descriptive")

    if reranker is not None:
        # Applied to the fetchable lane and after the split, because that lane
        # is what a caller reads and reordering it is the only thing that shows
        # up in an answer. The model sees titles, not data, and answers with
        # positions, so the worst it can do is order the same results badly.
        reordered = rerank(
            registry, reranker, query, observations,
            keep=rerank_keep, lift=rerank_lift,
        )
        if reordered != observations:
            steps.append("a model reordered the shortlist by what answers the question")
        observations = reordered

    return Retrieved(
        query=query,
        observations=observations[:limit],
        catalogue=catalogue[:limit],
        steps=steps,
        uncovered=list(report.coverage.missing),
        relevance=relevance,
    )
