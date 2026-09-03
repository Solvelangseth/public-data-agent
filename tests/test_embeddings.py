from __future__ import annotations

import pytest

from public_data_agent.embeddings import EmbeddedCandidate, rank_candidates


class FakeEmbeddings:
    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


def test_rank_candidates_is_deterministic_on_similarity_and_id() -> None:
    candidates = [
        EmbeddedCandidate("b", "B", (1.0, 0.0)),
        EmbeddedCandidate("a", "A", (1.0, 0.0)),
        EmbeddedCandidate("c", "C", (0.0, 1.0)),
    ]
    ranked = rank_candidates("query", candidates, FakeEmbeddings())
    assert [item[0].dataset_id for item in ranked] == ["a", "b", "c"]
    assert ranked[0][1] == 1.0


def test_rank_candidates_rejects_dimension_mismatch() -> None:
    with pytest.raises(ValueError, match="dimensions"):
        rank_candidates("query", [EmbeddedCandidate("a", "A", (1.0,))], FakeEmbeddings())
