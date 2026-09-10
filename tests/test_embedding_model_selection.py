"""Which embedding index a query is compared against.

Selecting by vector width alone was enough while one model was stored at each
width. Storing `text-embedding-3-large` truncated to 1536 alongside
`text-embedding-3-small` breaks that: the two are the same width and mean
entirely different things, and comparing across them does not error, it just
ranks badly.
"""

from __future__ import annotations

from pathlib import Path

from public_data_agent.embeddings import pack, semantic_ranking
from public_data_agent.registry import Registry


class _Provider:
    """Returns a fixed vector, and says which model it speaks for."""

    def __init__(self, model: str, vector: list[float]) -> None:
        self.model, self.vector = model, vector

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.vector for _ in texts]


def _store(registry: Registry, dataset_id: str, model: str, vector: list[float]) -> None:
    registry.ensure_observation_dataset(
        dataset_id=dataset_id, title=dataset_id, publisher_name="t",
        access_path=None, license=None,
    )
    registry.upsert_embedding(
        dataset_id=dataset_id, model=model, vector=pack(vector),
        dim=len(vector), text_hash="h",
    )


def test_two_models_of_the_same_width_are_not_mixed(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    try:
        _store(registry, "fixture:small", "text-embedding-3-small", [1.0, 0.0])
        _store(registry, "fixture:large", "text-embedding-3-large", [0.0, 1.0])
        registry.conn.commit()

        # Each provider must see only its own index, even though both indexes
        # hold vectors of the same width.
        small = semantic_ranking(
            registry, _Provider("text-embedding-3-small", [1.0, 0.0]), "q", limit=10
        )
        large = semantic_ranking(
            registry, _Provider("text-embedding-3-large", [0.0, 1.0]), "q", limit=10
        )
        assert [d for d, _ in small] == ["fixture:small"]
        assert [d for d, _ in large] == ["fixture:large"]
    finally:
        registry.close()


def test_an_explicit_model_still_wins(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    try:
        _store(registry, "fixture:small", "text-embedding-3-small", [1.0, 0.0])
        _store(registry, "fixture:large", "text-embedding-3-large", [0.0, 1.0])
        registry.conn.commit()
        ranked = semantic_ranking(
            registry,
            _Provider("text-embedding-3-large", [1.0, 0.0]),
            "q",
            limit=10,
            model="text-embedding-3-small",
        )
        assert [d for d, _ in ranked] == ["fixture:small"]
    finally:
        registry.close()
