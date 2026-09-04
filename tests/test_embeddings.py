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


def test_fusion_prefers_what_both_rankers_like() -> None:
    from public_data_agent.embeddings import fuse

    # "c" is third lexically but first semantically; "a" is the reverse.
    # Both appear in both lists, so both outrank ids only one ranker saw.
    assert fuse(["a", "b", "c"], ["c", "d", "a"], limit=4) == ["a", "c", "b", "d"]


def test_fusion_breaks_ties_toward_the_lexical_order() -> None:
    from public_data_agent.embeddings import fuse

    # Nothing is shared, so every id has the same fused score; the lexical
    # ranker is the tiebreaker rather than dictionary order.
    assert fuse(["b", "a"], ["d", "c"], limit=4) == ["b", "d", "a", "c"]


def test_vectors_round_trip_through_storage() -> None:
    from public_data_agent.embeddings import pack, unpack

    values = [0.5, -0.25, 0.0]
    assert [round(v, 6) for v in unpack(pack(values))] == values


def test_embedded_text_uses_stored_fields_and_nothing_else() -> None:
    """Keywords and themes carry vocabulary a title often lacks."""

    from public_data_agent.embeddings import embedding_text

    text = embedding_text(
        {
            "title": "Personer i arbeidsstyrken",
            "description": None,
            "publisher_name": "Statistisk sentralbyrå",
            "payload_json": '{"theme": [{"title": {"nb": "Arbeidsledighet"}}]}',
        }
    )
    assert "Personer i arbeidsstyrken" in text
    assert "Statistisk sentralbyrå" in text
    assert "Arbeidsledighet" in text
    # Nothing is added that was not stored.
    assert "None" not in text


def test_index_build_is_incremental_on_text_hash(tmp_path) -> None:
    from public_data_agent.embeddings import build_index
    from public_data_agent.registry import Registry

    class CountingProvider:
        def __init__(self) -> None:
            self.calls = 0

        def embed(self, texts):
            self.calls += len(texts)
            return [[1.0, 0.0] for _ in texts]

    registry = Registry(tmp_path / "r.sqlite")
    try:
        registry.conn.execute(
            """
            INSERT INTO datasets (
                id, source_id, ingest_reason, source_name, source_endpoints_json,
                missing_fields_json, payload_hash, first_ingested_at, last_ingested_at,
                last_seen_at, last_changed_at, title
            ) VALUES ('a', 's', 'test', 'S', '[]', '{}', 'h', 't', 't', 't', 't', 'Folkemengde')
            """
        )
        registry.conn.commit()
        provider = CountingProvider()
        first = build_index(registry, provider, model="m")
        assert first["embedded"] == 1 and provider.calls == 1
        # Unchanged text must not be paid for twice.
        second = build_index(registry, provider, model="m")
        assert second["embedded"] == 0 and second["skipped"] == 1
        assert provider.calls == 1
    finally:
        registry.close()
