"""Provider-neutral embedding retrieval primitives."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Protocol, Sequence


class EmbeddingProvider(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class EmbeddedCandidate:
    dataset_id: str
    text: str
    vector: tuple[float, ...]


def rank_candidates(
    query: str,
    candidates: Sequence[EmbeddedCandidate],
    provider: EmbeddingProvider,
    *,
    limit: int = 10,
) -> list[tuple[EmbeddedCandidate, float]]:
    """Rank candidates by cosine similarity; values are not factual answers."""
    if not candidates:
        return []
    query_vector = provider.embed([query])[0]
    scored = [(candidate, _cosine(query_vector, candidate.vector)) for candidate in candidates]
    scored.sort(key=lambda item: (-item[1], item[0].dataset_id))
    return scored[:limit]


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimensions must match")
    denominator = sqrt(sum(value * value for value in left) * sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0
