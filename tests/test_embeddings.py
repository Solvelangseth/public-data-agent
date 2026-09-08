from __future__ import annotations

from pathlib import Path

import pytest

from public_data_agent.embeddings import EmbeddedCandidate, rank_candidates
from public_data_agent.registry import Registry


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


def test_a_subject_and_a_question_are_told_apart() -> None:
    """The two retrieve differently, so which one a query is decides the ranking."""

    from public_data_agent.embeddings import looks_like_a_question

    for subject in ("byggekostnader", "arbeidsledighet", "lønn etter yrke",
                    "utslipp klimagasser", "fødsler medisinsk fødselsregister"):
        assert not looks_like_a_question(subject), subject
    for question in ("hva koster en bolig i Oslo", "hvor mange bor det i Bergen",
                     "hvilken bydel i Oslo har flest innbyggere",
                     "hvor mye CO2 slipper Norge ut", "er dette et spørsmål?"):
        assert looks_like_a_question(question), question


def test_one_common_word_does_not_make_a_subject_a_question() -> None:
    """"stor" appears in subjects too; it takes more than one marker."""

    from public_data_agent.embeddings import looks_like_a_question

    assert not looks_like_a_question("husholdninger størrelse")
    assert not looks_like_a_question("store foretak")


def test_routing_uses_semantic_alone_for_a_question() -> None:
    """Lexical ranking is worth +24 points on a subject and costs 5 on a
    question, so it is applied to one and not the other."""

    from public_data_agent.embeddings import rank_for_query

    lexical, semantic = ["L1", "L2", "L3"], ["S1", "S2", "S3"]
    asked = rank_for_query(lexical, semantic, "hvor mange bor det i Bergen", limit=3)
    assert asked == ["S1", "S2", "S3"]
    named = rank_for_query(lexical, semantic, "byggekostnader", limit=6)
    assert set(named) == {"L1", "L2", "L3", "S1", "S2", "S3"}


def test_two_models_can_index_the_same_corpus(tmp_path: Path) -> None:
    """Keyed on dataset_id alone, indexing a second model overwrote the first,
    so two models could never be compared on the same corpus -- which is the
    only way to find out whether one is better."""

    from public_data_agent.embeddings import pack

    registry = Registry(tmp_path / "r.sqlite")
    registry.conn.execute(
        """
        INSERT INTO datasets (id, source_id, ingest_reason, source_name,
            source_endpoints_json, missing_fields_json, payload_hash,
            first_ingested_at, last_ingested_at, last_seen_at, last_changed_at, title)
        VALUES ('a', 's', 't', 'S', '[]', '{}', 'h', 't', 't', 't', 't', 'Folkemengde')
        """
    )
    registry.conn.commit()
    for model in ("model-one", "model-two"):
        registry.upsert_embedding(dataset_id="a", model=model, vector=pack([1.0, 0.0]),
                                  dim=2, text_hash="h")
    assert registry.embedding_count() == 2
    assert registry.embedding_count("model-one") == 1
    assert registry.embedded_hashes("model-two") == {"a": "h"}
    # A model that has never run must not see another model's work as its own.
    assert registry.embedded_hashes("model-three") == {}
    registry.close()


def test_a_vector_is_refused_when_the_text_has_changed(tmp_path: Path) -> None:
    """Storing a vector for text no longer on the row would rank a resource by
    a description it does not have."""

    import json

    from public_data_agent.embeddings import export_texts, import_vectors

    registry = Registry(tmp_path / "r.sqlite")
    registry.conn.execute(
        """
        INSERT INTO datasets (id, source_id, ingest_reason, source_name,
            source_endpoints_json, missing_fields_json, payload_hash,
            first_ingested_at, last_ingested_at, last_seen_at, last_changed_at, title)
        VALUES ('a', 's', 't', 'S', '[]', '{}', 'h', 't', 't', 't', 't', 'Folkemengde')
        """
    )
    registry.conn.commit()

    texts = tmp_path / "texts.jsonl"
    assert export_texts(registry, texts)["written"] == 1
    exported = json.loads(texts.read_text(encoding="utf-8").strip())
    assert exported["dataset_id"] == "a" and exported["text_hash"]

    vectors = tmp_path / "vectors.jsonl"
    vectors.write_text(
        json.dumps({"dataset_id": "a", "text_hash": exported["text_hash"], "vector": [1.0, 0.0]})
        + "\n"
        + json.dumps({"dataset_id": "a", "text_hash": "stale", "vector": [0.0, 1.0]})
        + "\n"
        + json.dumps({"dataset_id": "gone", "text_hash": "x", "vector": [0.0, 1.0]})
        + "\n",
        encoding="utf-8",
    )
    result = import_vectors(registry, vectors, model="elsewhere")
    assert result == {"stored": 1, "stale": 1, "unknown": 1, "model": "elsewhere"}
    registry.close()
