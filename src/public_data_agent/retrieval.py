"""One entry point for finding data that can answer a question.

Everything here is a measured choice against `data/fetchable_gold.json`, whose
labels say which table actually answers each of 88 questions. The progression,
recall@5 then MRR:

    lexical alone            0.442   0.327
    + semantic ranking       0.709   0.577
    + routing by phrasing    0.779   0.622
    + subject over breakdown 0.791   0.627
    + observations lane      0.860   0.763

The steps are kept separate so each can be re-measured, and so a caller without
an embedding provider still gets the lexical half rather than nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from public_data_agent.embeddings import rank_for_query, semantic_ranking
from public_data_agent.fetch import classify_access_path
from public_data_agent.registry import Registry
from public_data_agent.resource_index import demote_breakdown_only, rank_within_coverage
from public_data_agent.search import search_report

DEPTH = 50


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


@dataclass
class Retrieved:
    """A ranking, and how it was produced."""

    query: str
    observations: list[str] = field(default_factory=list)
    catalogue: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "observations": self.observations,
            "catalogue": self.catalogue,
            "steps": self.steps,
        }


def _capability(registry: Registry, dataset_id: str, cache: dict[str, str]) -> str:
    if dataset_id not in cache:
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
) -> Retrieved:
    """Rank what could answer a question, fetchable results kept apart.

    Without a provider this is lexical only, which is worth stating plainly:
    lexical alone finds the right table for 23% of naturally phrased questions
    against 81% for the full stack. A provider is not an optimisation.
    """

    steps: list[str] = []
    lexical = [hit.dataset_id for hit in search_report(registry, query, limit=depth).hits]
    steps.append(f"lexical search returned {len(lexical)}")

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

    reordered = demote_breakdown_only(registry, ranked, query)
    if reordered != ranked:
        steps.append("demoted tables split by a query word below tables about it")
    ranked = reordered

    covered = rank_within_coverage(registry, ranked, query)
    if covered != ranked:
        steps.append("lifted resources recorded as covering a value the query names")
    ranked = covered

    cache: dict[str, str] = {}
    observations = [d for d in ranked if _capability(registry, d, cache) == "observations"]
    # A record that cannot return a number does not belong in the lane whose
    # job is returning numbers; it belongs in the other one, where saying "this
    # exists but I cannot retrieve it" is a real answer.
    catalogue = [d for d in ranked if _capability(registry, d, cache) != "observations"]
    steps.append(f"split into {len(observations)} fetchable and {len(catalogue)} descriptive")

    return Retrieved(
        query=query,
        observations=observations[:limit],
        catalogue=catalogue[:limit],
        steps=steps,
    )
